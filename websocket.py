import os
import json
import asyncio
import websockets
from fastapi import FastAPI, WebSocket
import uvicorn
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"

app = FastAPI()

@app.websocket("/ws/transcribe")
async def transcribe(websocket: WebSocket):
    await websocket.accept()
    print("Frontend connected")

    try:
        async with websockets.connect(
            OPENAI_WS_URL,
            additional_headers=[("Authorization", f"Bearer {OPENAI_API_KEY}")]
        ) as ws_openai:

            # 🔑 Start a response request immediately so OpenAI streams deltas
            await ws_openai.send(json.dumps({"type": "response.create"}))

            async def forward_frontend_audio():
                async for message in websocket.iter_text():
                    data = json.loads(message)

                    if data["type"] == "input_audio_buffer.append":
                        # The audio data from the frontend is now Base64 encoded
                        # so we can forward it directly to OpenAI.
                        msg = {
                            "type": "input_audio_buffer.append",
                            "audio": data["audio"], # <-- No more conversion needed
                        }
                        await ws_openai.send(json.dumps(msg))

                    elif data["type"] == "input_audio_buffer.commit":
                        await ws_openai.send(json.dumps({"type": "input_audio_buffer.commit"}))
                        # 🔑 Ask for transcript of what’s in the buffer
                        await ws_openai.send(json.dumps({"type": "response.create"}))


            async def receive_transcript():
                async for message in ws_openai:
                    try:
                        data = json.loads(message)
                        if data.get("type") in [
                            "response.output_text.delta",
                            "response.output_text.completed",
                        ]:
                             await websocket.send_json(data)
                    except json.JSONDecodeError:
                        continue

            await asyncio.gather(forward_frontend_audio(), receive_transcript())

    except Exception as e:
        print(f"Backend error: {e}")
        await websocket.close(code=1011, reason="OpenAI API connection failed")

if __name__ == "__main__":
    uvicorn.run("websocket:app", host="127.0.0.1", port=8000, reload=True)