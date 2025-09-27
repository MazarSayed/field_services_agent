import os
import json
import asyncio
import logging
import aiohttp
import websockets
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Missing OpenAI API key.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_transcription_session():
    """Create ephemeral token for OpenAI Realtime transcription."""
    url = "https://api.openai.com/v1/realtime/transcription_sessions"
    payload = {
        "input_audio_format": "pcm16",
        "input_audio_transcription": {
            "model": "gpt-4o-transcribe",
            "language": "en",
            "prompt": (
                "Transcribe the incoming audio in real time. "
                "Remove filler words like 'um', 'uh', 'you know', and repeated phrases. "
                "Make the transcript clean, coherent, and readable in context. "
                "Keep speaker's meaning intact and add punctuation for clarity."
            )
        },
        "turn_detection": {"type": "server_vad", "silence_duration_ms": 1000}
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v2"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()
            return data["client_secret"]["value"]


async def handle_client(client_ws):
    """Forward audio from browser to OpenAI and send transcription back."""
    ephemeral_token = await create_transcription_session()
    ws_url = "wss://api.openai.com/v1/realtime"
    headers = [("Authorization", f"Bearer {ephemeral_token}"), ("OpenAI-Beta", "realtime=v1")]

    async with websockets.connect(ws_url, additional_headers=headers) as openai_ws:
        async def forward_to_openai():
            async for message in client_ws:
                await openai_ws.send(message)

        async def forward_to_client():
            async for message in openai_ws:
                await client_ws.send(message)

        await asyncio.gather(forward_to_openai(), forward_to_client())

async def main():
    async with websockets.serve(handle_client, "0.0.0.0", 8000):
        logger.info("WebSocket relay server running at ws://0.0.0.0:8000")
        await asyncio.Future()  # keep running

if __name__ == "__main__":
    asyncio.run(main())
