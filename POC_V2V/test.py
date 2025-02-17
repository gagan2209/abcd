# import asyncio
# import websockets
# import json
# import uuid
# import requests
# from googletrans import Translator
#
# translator = Translator()
#
# # NeuralSpace API Configuration
# BASE = "https://voice.neuralspace.ai/api/v2/languages?type=stream"
# API_KEY = "sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829"
#
# headers = {"Authorization": API_KEY}
# response = requests.get(BASE, headers=headers)
# print(f"Languages available: {response.json().get('data', {}).get('languages', [])}")
#
# language = "ar"
# max_chunk_size = 10 # Reduced from 10
# vad_threshold = 0.9  # Adjusted for sensitivity
# disable_partial = "false"
# audio_format = "pcm_16k"
# DURATION = 600
#
# # Fetch authentication token
# TOKEN_URL = f"https://voice.neuralspace.ai/api/v2/token?duration={DURATION}"
# response = requests.get(TOKEN_URL, headers=headers)
# TOKEN = response.json().get("data", {}).get("token")
# if not TOKEN:
#     raise ValueError("Failed to retrieve API token.")
# print(f"Received Token: {TOKEN}")
#
# # Generate unique session ID as string
# session_id = str(uuid.uuid4())  # Ensure string format
# print(f"Session ID: {session_id}")
#
# # WebSocket URL for NeuralSpace
# NS_WEBSOCKET_URL = (
#     f"wss://voice.neuralspace.ai/voice/stream/live/transcribe/{language}/{TOKEN}/{session_id}"
#     f"?max_chunk_size={max_chunk_size}&vad_threshold={vad_threshold}&disable_partial={disable_partial}&format={audio_format}"
# )
# print(f"Connecting to NeuralSpace WebSocket: {NS_WEBSOCKET_URL}")
#
# # Async Queue for audio chunks
# q = asyncio.Queue()
#
# async def process_audio(ws):
#     """Send audio chunks from queue to NeuralSpace."""
#     try:
#         while True:
#             data = await q.get()
#             # print(f"Sending {len(data)} bytes to NS")
#             await ws.send(data)
#     except asyncio.CancelledError:
#         print("Audio processing task cancelled.")
#     except Exception as e:
#         print(f"Error in process_audio: {e}")
#
# async def receive_responses(ws):
#     """Receive and print transcriptions from NeuralSpace."""
#     # print('Called response function')
#
#     try:
#         async for message in ws:
#             # print("Raw response received:", message)
#             try:
#                 response = json.loads(message)
#                 msg = response['text']
#                 print(f"Transcription Response: {msg}")
#                 translate_t = await translator.translate(msg, src="ar", dest="en")
#                 print(f"Translated Text:- {translate_t.text}")
#             except json.JSONDecodeError as e:
#                 print("Failed to decode JSON:", e)
#     except websockets.exceptions.ConnectionClosed as e:
#         print(f"Connection closed: code={e.code}, reason={e.reason}")
#     except Exception as e:
#         print(f"Error in receive_responses: {e}")
#
# async def handler(websocket, path=None):
#     """Handle incoming WebSocket connections from the browser."""
#     print("Client connected.")
#     try:
#         async for message in websocket:
#             # print(f"Received {len(message)} bytes from client.")
#             await q.put(message)
#     except websockets.exceptions.ConnectionClosed:
#         print("Client disconnected.")
#     except Exception as e:
#         print(f"Error in handler: {e}")
#
# async def main():
#     """Main function to start WebSocket server and NeuralSpace processing."""
#     try:
#         async with websockets.connect(NS_WEBSOCKET_URL) as ns_ws:
#             print("Connected to NeuralSpace WebSocket.")
#             server = await websockets.serve(handler, "localhost", 8000)
#             print("WebSocket server started at ws://localhost:8000/stream")
#             await asyncio.gather(
#                 process_audio(ns_ws),
#                 receive_responses(ns_ws),
#                 server.wait_closed()
#             )
#     except Exception as e:
#         print(f"Main connection error: {e}")
#
# if __name__ == "__main__":
#     asyncio.run(main())
#
#

import asyncio
import websockets
import json
import uuid
import requests
from googletrans import Translator
from pydub import AudioSegment  # pip install pydub (ffmpeg must be installed)

translator = Translator()

# NeuralSpace API Configuration
BASE = "https://voice.neuralspace.ai/api/v2/languages?type=stream"
API_KEY = "sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829"

headers = {"Authorization": API_KEY}
response = requests.get(BASE, headers=headers)
print(f"Languages available: {response.json().get('data', {}).get('languages', [])}")

language = "en"
max_chunk_size = 10  # Reduced from 10
vad_threshold = 0.9  # Adjusted for sensitivity
disable_partial = "True"
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
session_id = str(uuid.uuid4())  # Ensure string format
print(f"Session ID: {session_id}")

# WebSocket URL for NeuralSpace
NS_WEBSOCKET_URL = (
    f"wss://voice.neuralspace.ai/voice/stream/live/transcribe/{language}/{TOKEN}/{session_id}"
    f"?max_chunk_size={max_chunk_size}&vad_threshold={vad_threshold}&disable_partial={disable_partial}&format={audio_format}"
)
print(f"Connecting to NeuralSpace WebSocket: {NS_WEBSOCKET_URL}")

# Async Queue for audio chunks to forward to NeuralSpace
q = asyncio.Queue()

# Global bytearray to accumulate received raw PCM data (assumed 16-bit, little-endian)
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

transcript_accumulator = ""
translate_accumulator =""
counter = 0

async def receive_responses(ws):
    """Receive and print transcriptions from NeuralSpace."""
    global transcript_accumulator, counter,translate_accumulator  # Declare globals to modify them inside the function
    try:
        async for message in ws:
            try:
                response = json.loads(message)
                msg = response['text']
                translate_t = await translator.translate(msg, src="ar", dest="en")
                transcript_accumulator += msg
                translate_accumulator += translate_t.text
                counter += 1
                if counter % 2 == 0:
                    print(f"Transcripted Text: {transcript_accumulator}")
                    print(f"Translated Text: {translate_accumulator}")
                # Translate the message

                # print(f"Translated Text: {translate_t.text}")
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
            # Append the received audio data to the global pcm_data buffer
            pcm_data.extend(message)
            # Also forward the data to NeuralSpace via the queue
            await q.put(message)
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected.")
    except Exception as e:
        print(f"Error in handler: {e}")


async def main():
    """Main function to start WebSocket server and NeuralSpace processing."""
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
        # Once the server and connections are closed, store the accumulated PCM data as MP3.
        if pcm_data:
            try:
                print("Converting received PCM audio to MP3...")
                # Create an AudioSegment from raw PCM data.
                # Adjust these parameters if your audio differs:
                # sample_width=2 (16-bit), frame_rate=16000 (16KHz), channels=1 (mono)
                audio_segment = AudioSegment(
                    data=pcm_data,
                    sample_width=2,
                    frame_rate=16000,
                    channels=1
                )
                audio_segment.export("output.mp3", format="mp3")
                print("Saved MP3 as output.mp3")
            except Exception as e:
                print(f"Error converting to MP3: {e}")
        else:
            print("No PCM audio data received; nothing to convert.")


if __name__ == "__main__":
    asyncio.run(main())

























# import asyncio
# import websockets
# import websocket
# from pydub import AudioSegment
# from queue import Queue
# import uuid
# import requests
# import json
#
# API_KEY = "sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829"
# headers = {"Authorization": API_KEY}
#
# language = "en"
# max_chunk_size = 3
# vad_threshold = 0.5
# disable_partial = "false"
# audio_format = "pcm_16k"
# DURATION = 600
#
# # Get the authentication token
# TOKEN_URL = f"https://voice.neuralspace.ai/api/v2/token?duration={DURATION}"
# response = requests.get(TOKEN_URL, headers=headers)
# TOKEN = response.json()['data']['token']
# session_id = uuid.uuid4()
#
# # WebSocket connection to NeuralSpace
#
# ws = websocket.create_connection(f"wss://voice.neuralspace.ai/voice/stream/live/transcribe/{language}/{TOKEN}/{session_id}?max_chunk_size={max_chunk_size}&vad_threshold={vad_threshold}&disable_partial={disable_partial}&format={audio_format}")
#
# q = Queue()  # Global queue to store audio bytes
#
# async def send_audio(q, ws):
#     """Send audio from queue to NeuralSpace WebSocket."""
#     while True:
#         data = await asyncio.to_thread(q.get())  # Get data from queue in an async-friendly way
#         ws.send_binary(data)
#
# async def receive_response(ws):
#     """Receive responses from NeuralSpace WebSocket."""
#     while True:
#         try:
#             resp = ws.recv()
#             resp = json.loads(resp)
#             print(resp)  # Print transcription result
#         except websocket.WebSocketConnectionClosedException:
#             print("NeuralSpace WebSocket closed.")
#             break
#
# async def handler(webs):
#     """Handle WebSocket audio streaming from client."""
#     print("Client connected")
#     audio_data = bytearray()
#
#     try:
#         # Start sending and receiving tasks
#         asyncio.create_task(send_audio(q, ws))
#         asyncio.create_task(receive_response(ws))
#
#         async for message in webs:
#             print(f"Received {len(message)} bytes")
#             audio_data.extend(message)  # Collect audio chunks
#             q.put(message)  # Add message to queue
#
#     except webs.exceptions.ConnectionClosedError:
#         audio_data.clear()
#         print("Client disconnected")
#     except Exception as e:
#         print(f"Error: {e}")
#
# async def main():
#     async with websockets.serve(handler, "localhost", 8000):
#         print("WebSocket server started at ws://localhost:8000/stream")
#         await asyncio.Future()
#
# if __name__ == "__main__":
#     asyncio.run(main())


