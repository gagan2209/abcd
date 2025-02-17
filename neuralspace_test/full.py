import asyncio
import websockets
import json
import requests
from fastapi import FastAPI, WebSocket
from googletrans import Translator
import uuid

app = FastAPI()
translator = Translator()

# NeuralSpace API details
TOKEN_URL = "https://voice.neuralspace.ai/api/v2/token?duration=600"
BASE_WS_URL = "wss://voice.neuralspace.ai/voice/stream/live/transcribe/ar"
HEADERS = {"Authorization": "sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829"}

# Get short-lived token
response = requests.get(TOKEN_URL, headers=HEADERS)
assert response.status_code == 200
TOKEN = response.json()['data']['token']

@app.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    neuralspace_ws_url = f"{BASE_WS_URL}/{TOKEN}/{session_id}?max_chunk_size=2&vad_threshold=0.5&disable_partial=False&format=pcm_16k"
    
    async with websockets.connect(neuralspace_ws_url) as ns_ws:
        try:
            while True:
                audio_data = await websocket.receive_bytes()
                await ns_ws.send(audio_data)  # Send audio to NeuralSpace
                
                response = await ns_ws.recv()
                response_json = json.loads(response)
                transcribed_text = response_json.get("text", "")
                
                if response_json.get("full", False):
                    translated_text = translator.translate(transcribed_text, src="ar", dest="en").text
                    await websocket.send_text(translated_text)  # Send translated text to frontend
                    
                    # Call NeuralSpace TTS (implementation depends on API)
                    tts_audio = await generate_speech(transcribed_text)
                    await websocket.send_bytes(tts_audio)  # Send audio back to frontend

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await websocket.close()

async def generate_speech(text):
    """ Calls NeuralSpace's TTS API to generate speech from text. """
    tts_url = "https://voice.neuralspace.ai/api/v2/tts"
    payload = {"text": text, "language": "ar"}  # Adjust as needed
    response = requests.post(tts_url, json=payload, headers=HEADERS)
    return response.content if response.status_code == 200 else b""
