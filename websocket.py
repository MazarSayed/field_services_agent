import os
import json
import asyncio
import threading
import queue
import base64
import websockets
from fastapi import FastAPI, WebSocket
import uvicorn

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-transcribe"

app = FastAPI()

class TranscriptionService:
    def __init__(self):
        self.audio_queue = queue.Queue()
        self.is_recording = False

    def start_audio_thread(self):
        import pyaudio

        def capture_audio():
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024,
            )
            print("🎙 Recording started")
            while self.is_recording:
                data = stream.read(1024, exception_on_overflow=False)
                self.audio_queue.put(data)
            stream.stop_stream()
            stream.close()
            p.terminate()
            print("🎙 Recording stopped")

        self.is_recording = True
        threading.Thread(target=capture_audio, daemon=True).start()

    async def websocket_loop(self, websocket: WebSocket):
        await websocket.accept()
        print("Frontend connected")
        
        auth_header = {
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }

        try:
            async with websockets.connect(OPENAI_WS_URL, additional_headers=auth_header) as ws_openai:
                async def send_audio():
                    while self.is_recording or not self.audio_queue.empty():
                        if not self.audio_queue.empty():
                            audio = self.audio_queue.get()
                            msg = {
                                "type": "input_audio_buffer.append",
                                "audio": base64.b64encode(audio).decode("utf-8")
                            }
                            await ws_openai.send(json.dumps(msg))
                        await asyncio.sleep(0.01)
                    await ws_openai.send(json.dumps({"type": "input_audio_buffer.commit"}))
        
                async def receive_transcript():
                    async for message in ws_openai:
                        try:
                            data = json.loads(message)
                            if data.get("type") in [
                                "conversation.item.input_audio_transcription.delta",
                                "conversation.item.input_audio_transcription.completed"
                            ]:
                                await websocket.send_json(data)
                        except json.JSONDecodeError:
                            continue
        
                await asyncio.gather(send_audio(), receive_transcript())

        except Exception as e:
            print(f"An error occurred with the OpenAI WebSocket: {e}")
            # Shorten the reason string to avoid the ProtocolError
            await websocket.close(code=1011, reason="OpenAI API key invalid or connection failed")

transcription_service = TranscriptionService()

@app.websocket("/ws/transcribe")
async def transcribe(websocket: WebSocket):
    transcription_service.start_audio_thread()
    await transcription_service.websocket_loop(websocket)

if __name__ == "__main__":
    uvicorn.run("websocket:app", host="127.0.0.1", port=8000, reload=True)