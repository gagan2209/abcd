import requests
import os
import websocket
import asyncio
from googletrans import Translator 

translator = Translator()

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
print(TOKEN)
# create websocket connection


## Parameters ############################3333
language = "ar"
max_chunk_size = 2
vad_threshold = 0.5
disable_partial = "False"
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
    frames_per_buffer=2048,
    input=True,
    output=False,
    stream_callback=listen
)

async def translate_text(text):
    # Run the synchronous translate method in a separate thread using asyncio.to_thread
    translation = await asyncio.to_thread(translator.translate, text, src="ar", dest="en")
    return translation.text  # Return the translated text


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
        # print(resp['text'])
        text = resp['text']
        future = asyncio.ensure_future(translate_text(text))

        # Use an event loop to get the result asynchronously
        loop = asyncio.get_event_loop()
        translated_text = loop.run_until_complete(future)

        # Output formatting
        if resp['full']:
            print('\r' + ' ' * 120, end='', flush=True)
            print(f'\rArabic: {text}', flush=True)
            print(f'English: {translated_text}')
        else:
            if len(text) > 120:
                text = f'...{text[-115:]}'
            print(f'\r{text}', end='', flush=True)
            print(translated_text)


except KeyboardInterrupt as e:
    print("Closing stream and websocket connection.")
    stream.close()
    ws.close()



