import asyncio
import json
import threading
import queue
import pyaudio
import neuralspace as ns
from googletrans import Translator  # Import the synchronous Translator

# Initialize VoiceAI
vai = ns.VoiceAI(api_key="sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829")
pa = pyaudio.PyAudio()
translator = Translator()
q = queue.Queue()

# Callback function for PyAudio to fill up the queue
def listen(in_data, frame_count, time_info, status):
    q.put(in_data)
    return (None, pyaudio.paContinue)

# Transfer audio data from queue to WebSocket
def send_audio(q, ws):
    while True:
        data = q.get()
        ws.send_binary(data)

# Asynchronous function to translate Arabic text to English
async def translate_text(text):
    # Run the synchronous translate method in a separate thread using asyncio.to_thread
    translation = await asyncio.to_thread(translator.translate, text, src="ar", dest="en")
    return translation.text  # Return the translated text

# Open WebSocket connection
with vai.stream('ar') as ws:
    # Start PyAudio stream
    stream = pa.open(
        rate=16000,
        channels=1,
        format=pyaudio.paInt16,
        frames_per_buffer=4096,
        input=True,
        output=False,
        stream_callback=listen,
        # min_chunk_size = 10,
        # vad_threshold = 0.3
    )

    # Start sending audio bytes on a new thread
    t = threading.Thread(target=send_audio, args=(q, ws))
    t.start()
    print('Listening...')

    # Start receiving results on the current thread
    while True:
        resp = ws.recv()
        resp = json.loads(resp)
        text = resp['text']

        # Schedule the async translation function within the event loop
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
