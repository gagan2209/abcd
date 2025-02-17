from fastapi import FastAPI, WebSocket
import requests
import asyncio
from googletrans import Translator
from queue import Queue
import json
import uuid
import threading
import websockets

translator = Translator()
app = FastAPI()

#################################### API ENDPOINTS ####################################

TAFASEEL_API_URL = "https://tafaseel-ai-poc.xceloretech.com/query"

#################################### NEURALSPACE CONFIGURATION ####################################

neuralspace_api_key = "sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829"
language = "ar"
max_chunk_size = 2
vad_threshold = 0.5
disable_partial = "False"
audio_format = "pcm_16k"

def get_neuralspace_token():
    duration = 600     # 600 seconds -> 10 minutes for each user
    token_url = f"https://voice.neuralspace.ai/api/v2/token?duration={duration}"
    headers = {
        "Authorization": neuralspace_api_key
    }
    response = requests.get(token_url, headers=headers)
    response.raise_for_status()
    token = response.json()['data']['token']
    return token

###################################### SEND AUDIO FROM QUEUE TO NEURALSPACE WEBSOCKET ######################################

async def send_audio(q, neuralspace_ws):
    """
    Continuously sends audio data from the queue to the NeuralSpace WebSocket.
    """
    try:
        while True:
            data = q.get()
            if data is None:  # Stop signal
                break
            await neuralspace_ws.send(data)
    except Exception as e:
        print(f"Error sending audio: {e}")

################################### TRANSLATE AND SEND TEXT ###################################

async def translate_text(text):
    translation = await asyncio.to_thread(translator.translate, text, src="ar", dest="en")
    return translation.text

async def get_tafaseel_response(text):
    payload = {"query": text}
    response = requests.post(TAFASEEL_API_URL, json=payload)
    return response.json().get("response", "No response from Tafaseel.")

###################################### WEBSOCKET STT ######################################

# @app.websocket('/stt')
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     print(" WebSocket connection established.")
#
#     try:
#         # Get NeuralSpace WebSocket token
#         token = get_neuralspace_token()
#         session_id = uuid.uuid4()
#         neuralspace_ws_url = f"wss://voice.neuralspace.ai/voice/stream/live/transcribe/{language}/{token}/{session_id}?max_chunk_size={max_chunk_size}&vad_threshold={vad_threshold}&disable_partial={disable_partial}&format={audio_format}"
#         print(f" Connecting to NeuralSpace: {neuralspace_ws_url}")
#         async with websockets.connect(neuralspace_ws_url) as neuralspace_ws:
#             print('Neuralspace websockets connected!!')
#             q = Queue()
#
#             # Start a separate thread to send audio from queue
#             thread = threading.Thread(target=lambda: asyncio.run(send_audio(q, neuralspace_ws)), daemon=True)
#             thread.start()
#
#             while True:
#                 data = await websocket.receive_bytes()  # Receive audio from client
#                 print(f"Received {len(data)} bytes of audio from client")
#                 q.put(data)  # Push audio to queue for streaming
#
#                 response = await neuralspace_ws.recv() # Receive transcribed text
#                 print(response)
#                 resp = json.loads(response)
#                 text = resp.get('text', '')
#
#                 if text:
#                     print(f" Received Arabic: {text}")
#
#                     translated_text = await translate_text(text)
#                     print(f" Translated English: {translated_text}")
#
#                     # tafaseel_response = await get_tafaseel_response(translated_text)
#                     # print(f" Tafaseel AI Response: {tafaseel_response}")
#                     #
#                     # await websocket.send_text(tafaseel_response)  # Send response back to client
#
#     except Exception as e:
#         print(f"Error: {e}")
#
#     finally:
#         print('WebSocket connection closed')
#         q.put(None)  # Stop audio streaming thread
#         await websocket.close()

@app.websocket('/stt')
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connection established.")

    try:
        # Get NeuralSpace WebSocket token
        token = get_neuralspace_token()
        session_id = uuid.uuid4()
        neuralspace_ws_url = f"wss://voice.neuralspace.ai/voice/stream/live/transcribe/{language}/{token}/{session_id}?max_chunk_size={max_chunk_size}&vad_threshold={vad_threshold}&disable_partial={disable_partial}&format={audio_format}"

        async with websockets.connect(neuralspace_ws_url) as neuralspace_ws:
            print("NeuralSpace WebSocket connected!!")

            while True:
                data = await websocket.receive_bytes()  # Receive audio from client
                print(f"Received {len(data)} bytes of audio from client")

                await neuralspace_ws.send(data)  # Send audio to NeuralSpace
                try:
                    response = await asyncio.wait_for(neuralspace_ws.recv(), timeout=2)
                    print(f"Raw NeuralSpace Response: {response}")
                    resp = json.loads(response)
                    text = resp.get('text', '')

                    if text:
                        print(f"Received Arabic: {text}")

                        translated_text = await translate_text(text)
                        print(f"Translated English: {translated_text}")

                        tafaseel_response = await get_tafaseel_response(translated_text)
                        print(f"Tafaseel AI Response: {tafaseel_response}")

                        await websocket.send_text(tafaseel_response)  # Send response back to client

                except asyncio.TimeoutError:
                    print("No text response from NeuralSpace yet...")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        print(' WebSocket connection closed')
        await websocket.close()

