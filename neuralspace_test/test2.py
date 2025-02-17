
import requests
import os
import websocket

# list languages    
BASE = "https://voice.neuralspace.ai/api/v2/languages?type=stream"


headers = {
    "Authorization": "sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829"
}
response = requests.get(BASE, headers=headers)

assert response.status_code == 200

print(f"languages available are : {response.json()['data']['languages']}")

# short-lived token
DURATION = 600
TOKEN_URL = f"https://voice.neuralspace.ai/api/v2/token?duration={DURATION}"

response = requests.get(TOKEN_URL, headers=headers)

assert response.status_code == 200

TOKEN = response.json()['data']['token']

# create websocket connection
language = "ar"

max_chunk_size = 3
vad_threshold = 0.5
disable_partial = "false"
audio_format = "pcm_16k"

import uuid
session_id = uuid.uuid4()
ws = websocket.create_connection(f"wss://voice.neuralspace.ai/voice/stream/live/transcribe/{language}/{TOKEN}/{session_id}?max_chunk_size={max_chunk_size}&vad_threshold={vad_threshold}&disable_partial={disable_partial}&format={audio_format}")

# get audio from microphone
from queue import Queue
import pyaudio
import threading

q = Queue()
pa = pyaudio.PyAudio()

def listen(in_data, frame_count, time_info, status):
    q.put(in_data)
    return (None, pyaudio.paContinue)

stream = pa.open(
    rate=16000,
    channels=1,
    format=pyaudio.paInt16,
    frames_per_buffer=4096,
    input=True,
    output=False,
    stream_callback=listen
)

# send audio asynchronously using threading
def send_audio(q, ws):
    try:
        while True:
            data = q.get()
            ws.send_binary(data)
    except KeyboardInterrupt as e:
        print("closing sending audio thread.")

t = threading.Thread(target=send_audio, args=(q,ws))
t.start()
print("Listening and sending audio data through websocket.")

# recieve results
import json
try:
    while True:
        resp = ws.recv()
        resp = json.loads(resp)
        print(resp['text'])
except KeyboardInterrupt as e:
    print("Closing stream and websocket connection.")
    stream.close()
    ws.close()