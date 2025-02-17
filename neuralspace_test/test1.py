import json
import threading
from queue import Queue

import pyaudio
import neuralspace as ns
from googletrans import Translator
import asyncio

translator = Translator()
q = Queue()

# callback for pyaudio to fill up the queue
def listen(in_data, frame_count, time_info, status):
    q.put(in_data)
    return (None, pyaudio.paContinue)

# transfer from queue to websocket
def send_audio(q, ws):
    while True:
        data = q.get()
        ws.send_binary(data)


# initialize VoiceAI
vai = ns.VoiceAI(api_key = "sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829")
pa = pyaudio.PyAudio()



# open websocket connection
with vai.stream('ar') as ws:
    # start pyaudio stream
    stream = pa.open(
        rate=16000,
        channels=1,
        format=pyaudio.paInt16,
        frames_per_buffer=4096,
        input=True,
        output=False,
        stream_callback=listen,
    )
    # start sending audio bytes on a new thread
    t = threading.Thread(target=send_audio, args=(q, ws))
    t.start()
    print('Listening...')
    # start receiving results on the current thread
    

    while True:
        resp = ws.recv()
        resp = json.loads(resp)
        text = resp['text']
        
        # Run the async translation function synchronously
        translate_t = asyncio.run(translator.translate(text, src="ar", dest="en")).text  

        # Optional output formatting; new lines on every 'full' utterance
        if resp['full']:
            print('\r' + ' ' * 120, end='', flush=True)
            print(f'\r{text}', flush=True)
            print(translate_t)
        else:
            if len(text) > 120:
                text = f'...{text[-115:]}'
            print(f'\r{text}', end='', flush=True)
            print(translate_t)

