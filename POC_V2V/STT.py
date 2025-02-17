import asyncio
import websockets
import json
import uuid
import requests
from googletrans import Translator
from pydub import AudioSegment  # pip install pydub (and install ffmpeg)

translator = Translator()

# NeuralSpace API Configuration
BASE = "https://voice.neuralspace.ai/api/v2/languages?type=stream"
API_KEY = "sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829"

headers = {"Authorization": API_KEY}
response = requests.get(BASE, headers=headers)
print(f"Languages available: {response.json().get('data', {}).get('languages', [])}")

language = "ar"
max_chunk_size = 10
vad_threshold = 0.9  # Adjusted for sensitivity
disable_partial = "false"
audio_format = "pcm_16k"
DURATION = 600

# Fetch authentication token
TOKEN_URL = f"https://voice.neuralspace.ai/api/v2/token?duration={DURATION}"
response = requests.get(TOKEN_URL, headers=headers)
TOKEN = response.json().get("data", {}).get("token")
if not TOKEN:
    raise ValueError("Failed to retrieve API token.")
print(f"Received Token: {TOKEN}")

# Generate unique session ID as string
session_id = str(uuid.uuid4())
print(f"Session ID: {session_id}")

# WebSocket URL for NeuralSpace
NS_WEBSOCKET_URL = (
    f"wss://voice.neuralspace.ai/voice/stream/live/transcribe/{language}/{TOKEN}/{session_id}"
    f"?max_chunk_size={max_chunk_size}&vad_threshold={vad_threshold}&disable_partial={disable_partial}&format={audio_format}"
)
print(f"Connecting to NeuralSpace WebSocket: {NS_WEBSOCKET_URL}")

# Async Queue for audio chunks (to send to NeuralSpace)
q = asyncio.Queue()

# Global bytearray to accumulate raw PCM audio for MP3 conversion
pcm_data = bytearray()


async def process_audio(ws):
    """Send audio chunks from queue to NeuralSpace."""
    try:
        while True:
            data = await q.get()
            await ws.send(data)
    except asyncio.CancelledError:
        print("Audio processing task cancelled.")
    except Exception as e:
        print(f"Error in process_audio: {e}")


async def receive_responses(ws):
    """Receive and print transcriptions from NeuralSpace."""
    try:
        async for message in ws:
            try:
                response = json.loads(message)
                msg = response['text']
                print(f"Transcription Response: {msg}")
                translate_t = await translator.translate(msg, src="ar", dest="en")
                print(f"Translated Text: {translate_t.text}")
            except json.JSONDecodeError as e:
                print("Failed to decode JSON:", e)
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection closed: code={e.code}, reason={e.reason}")
    except Exception as e:
        print(f"Error in receive_responses: {e}")


async def handler(websocket, path=None):
    """Handle incoming WebSocket connections from the browser."""
    global pcm_data
    print("Client connected.")
    try:
        async for message in websocket:
            # Accumulate raw PCM data for later MP3 conversion
            pcm_data.extend(message)
            # Forward the data to NeuralSpace
            await q.put(message)
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected.")
    except Exception as e:
        print(f"Error in handler: {e}")


async def main():
    """Main function to start the WebSocket server and NeuralSpace processing."""
    try:
        async with websockets.connect(NS_WEBSOCKET_URL) as ns_ws:
            print("Connected to NeuralSpace WebSocket.")
            server = await websockets.serve(handler, "localhost", 8000)
            print("WebSocket server started at ws://localhost:8000/stream")
            await asyncio.gather(
                process_audio(ns_ws),
                receive_responses(ns_ws),
                server.wait_closed()
            )
    except Exception as e:
        print(f"Main connection error: {e}")
    finally:
        # Once the server is done, convert the accumulated PCM to MP3.
        if pcm_data:
            print("Converting raw PCM data to MP3...")
            # Create an AudioSegment from raw PCM data.
            # Assumptions: 16-bit (sample_width=2), 16kHz (frame_rate=16000), mono (channels=1).
            audio_segment = AudioSegment(
                data=pcm_data,
                sample_width=2,
                frame_rate=16000,
                channels=1
            )
            audio_segment.export("output.mp3", format="mp3")
            print("Saved MP3 as output.mp3")
        else:
            print("No PCM audio data received; nothing to convert.")


if __name__ == "__main__":
    asyncio.run(main())
