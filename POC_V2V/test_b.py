import asyncio
import websockets
import json
import uuid
import requests
import io
import wave
import numpy as np
import torch
import torchaudio
from googletrans import Translator
from pydub import AudioSegment  # Used here for saving audio if needed
# Import the NeuralSpace TTS API library (adjust this to your actual module)
import neuralspace as ns
from df.enhance import init_df
from df.enhance import enhance
import soundfile as sf



vad_model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', trust_repo=True)
(get_speech_ts, _, _, _, _) = utils  # Get the function for detecting speech timestamps

# Initialize DeepFilterNet model for enhancement
df_model, df_state, _ = init_df()
#############################################################################################################
# Global Variables and Initialization
translator = Translator()
vai = ns.VoiceAI(api_key='sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829')

BASE = "https://voice.neuralspace.ai/api/v2/languages?type=stream"
API_KEY = "sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829"
headers = {"Authorization": API_KEY}
response = requests.get(BASE, headers=headers)
print(f"Languages available: {response.json().get('data', {}).get('languages', [])}")

language = "en-in"
max_chunk_size = 10
vad_threshold = 0.9
disable_partial = "True"
audio_format = "pcm_16k"
DURATION = 600

# Fetch transcription token
TOKEN_URL = f"https://voice.neuralspace.ai/api/v2/token?duration={DURATION}"
response = requests.get(TOKEN_URL, headers=headers)
TOKEN = response.json().get("data", {}).get("token")
if not TOKEN:
    raise ValueError("Failed to retrieve API token.")
print(f"Received Token: {TOKEN}")

session_id = str(uuid.uuid4())
print(f"Session ID: {session_id}")

NS_WEBSOCKET_URL = (
    f"wss://voice.neuralspace.ai/voice/stream/live/transcribe/{language}/{TOKEN}/{session_id}"
    f"?max_chunk_size={max_chunk_size}&vad_threshold={vad_threshold}&disable_partial={disable_partial}&format={audio_format}"
)
print(f"Connecting to NeuralSpace WebSocket: {NS_WEBSOCKET_URL}")

q = asyncio.Queue()  # Queue for audio chunks to forward to NeuralSpace transcription

# Global accumulator for received raw PCM audio (processed)
pcm_data = bytearray()

transcript_accumulator = ""
translate_accumulator = ""
counter = 0


##############################################
# Helper functions

def wrap_pcm_in_wav(raw_pcm_bytes, num_channels=1, sample_width=2, framerate=16000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(framerate)
        wf.writeframes(raw_pcm_bytes)
    buf.seek(0)
    return buf


def audio_processing(audio_blob):
    """
    Process incoming raw PCM audio blob:
      - Wrap it as a WAV file.
      - Load the audio (averaging channels if necessary) and resample to 16kHz.
      - Optionally perform enhancement (currently passed through).
      - Return processed audio as raw PCM bytes (16-bit, 16kHz, mono).
    """
    wav_file = wrap_pcm_in_wav(audio_blob, num_channels=1, sample_width=2, framerate=16000)
    waveform, sr = torchaudio.load(wav_file)
    if waveform.shape[0] > 1:
        waveform = torch.mean(waveform, dim=0, keepdim=True)
    if sr != 16000:
        waveform = torchaudio.functional.resample(waveform, sr, 16000)
    # Enhancement step (if you have an enhance() function, insert it here)
    processed_waveform = waveform  # Here, simply passing through

    processed_waveform = processed_waveform.squeeze().cpu().numpy()
    processed_waveform = np.clip(processed_waveform, -1.0, 1.0)
    int16_data = (processed_waveform * 32767).astype(np.int16)
    return int16_data.tobytes()


##############################################
# WebSocket Handlers

async def process_audio(ws):
    """Send audio chunks from queue to NeuralSpace transcription."""
    try:
        while True:
            data = await q.get()
            await ws.send(data)
    except asyncio.CancelledError:
        print("Audio processing task cancelled.")
    except Exception as e:
        print(f"Error in process_audio: {e}")


async def receive_responses(ws):
    """Receive transcription responses from NeuralSpace."""
    global transcript_accumulator, translate_accumulator, counter
    try:
        async for message in ws:
            try:
                response = json.loads(message)
                msg = response['text']
                translate_t = await translator.translate(msg, src="en", dest="en")
                transcript_accumulator += msg + " "
                translate_accumulator += translate_t.text + " "
                counter += 1
                if counter % 2 == 0:
                    print(f"Transcripted Text: {transcript_accumulator}")
                    print(f"Translated Text: {translate_accumulator}")
            except json.JSONDecodeError as e:
                print("Failed to decode JSON:", e)
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Transcription connection closed: code={e.code}, reason={e.reason}")
    except Exception as e:
        print(f"Error in receive_responses: {e}")


async def transcription_handler(websocket, path=None):
    """Handle incoming audio from the browser for transcription.
    Process the raw blob using audio_processing before forwarding it.
    """
    global pcm_data
    print("Transcription client connected.")
    try:
        async for message in websocket:
            # Process the incoming raw PCM blob.
            loop = asyncio.get_event_loop()
            processed_audio = await loop.run_in_executor(None, audio_processing, message)
            pcm_data.extend(processed_audio)
            await q.put(processed_audio)
    except websockets.exceptions.ConnectionClosed:
        print("Transcription client disconnected.")
    except Exception as e:
        print(f"Error in transcription_handler: {e}")


async def tts_handler(websocket, path=None):
    """
    When a client connects to the TTS endpoint, continuously check for updated translated text.
    When new text is available, call the TTS API and stream the resulting audio (as binary data)
    back to the client.
    """
    global translate_accumulator
    print("TTS client connected.")
    last_sent_text = ""
    try:
        while True:
            await asyncio.sleep(1)  # check every second
            if translate_accumulator and translate_accumulator != last_sent_text:
                data = {
                    "text": translate_accumulator,
                    "speaker_id": "en-male-Oscar-english-neutral",
                    "stream": True,
                    "sample_rate": 16000,
                    "config": {
                        "pace": 1.0,
                        "volume": 1.0,
                        "pitch_shift": 0,
                        "pitch_scale": 1.0
                    }
                }
                try:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, vai.synthesize, data)
                    await websocket.send(result)
                    print("Sent TTS audio chunk to client.")
                    last_sent_text = translate_accumulator
                except Exception as e:
                    print(f"TTS synthesis error: {e}")
    except websockets.exceptions.ConnectionClosed:
        print("TTS client disconnected.")
    except Exception as e:
        print(f"Error in tts_handler: {e}")


##############################################
# Main Async Routine

async def main():
    """Start both transcription and TTS WebSocket servers and the NeuralSpace transcription client."""
    try:
        async with websockets.connect(NS_WEBSOCKET_URL) as ns_ws:
            print("Connected to NeuralSpace transcription WebSocket.")
            transcription_server = await websockets.serve(transcription_handler, "localhost", 8000)
            print("Transcription WebSocket server started at ws://localhost:8000/stream")
            tts_server = await websockets.serve(tts_handler, "localhost", 8001)
            print("TTS WebSocket server started at ws://localhost:8001/tts")
            await asyncio.gather(
                process_audio(ns_ws),
                receive_responses(ns_ws),
                transcription_server.wait_closed(),
                tts_server.wait_closed()
            )
    except Exception as e:
        print(f"Main connection error: {e}")
    finally:
        if pcm_data:
            try:
                print("Converting received PCM audio to MP3...")
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
