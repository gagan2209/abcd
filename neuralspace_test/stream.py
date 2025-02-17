import streamlit as st
import pyaudio
import numpy as np
import requests
import json
import threading
from queue import Queue
import neuralspace as ns
import websocket


headers = {
    "Authorization": "sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829"
}

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

# PyAudio Configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024

# Initialize PyAudio
audio = pyaudio.PyAudio()

st.title("Vice to Voice")

# Start/Stop Buttons
start_button = st.button("Start Talking")
stop_button = st.button("Stop Talking")

if "recording" not in st.session_state:
    st.session_state.recording = False

if start_button:
    st.session_state.recording = True

if stop_button:
    st.session_state.recording = False

q = Queue()

def listen(in_data,frame_count,time_info,status):
    q.put(in_data)
    return (None,pyaudio.paContinue)

def send_audio(q,ws):
    while True:
        data = q.get()
        ws.send_binary(data)

vai = ns.VoiceAI(api_key="sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829")
pa = pyaudio.PyAudio()

with vai.stream('ar') as ws:
    stream = pa.open(
        rate=16000,
        channels=1,
        format=pyaudio.paInt16,
        frames_per_buffer=4096,
        input=True,
        output=False,
        stream_callback=listen,
    )

    t = threading.Thread(target=send_audio,args=(q,ws))
    t.start()
    st.write('Receiving')
    while True:
        resp = ws.recv()
        resp = json.loads(resp)
        text = resp['text']
        if resp['full']:
            st.write(' '*120)
            st.write(f"{text}",flush=True)
        else:
            if len(text) > 120:
                text = f'...{text[-115:]}'
                st.write(f"{text}",flush=True,end = '')


