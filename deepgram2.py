from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import wave
import os
import asyncio
import numpy as np
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Create a directory to store audio files if it doesn't exist
AUDIO_DIR = "audio_files"
os.makedirs(AUDIO_DIR, exist_ok=True)

connection_id = 0  # For unique filenames

############################################### DEEPGRAM CONFIG ###########################################################
config = DeepgramClientOptions(
    options={"keepalive": "true"}
)

CHANNELS = 1
RATE = 16000
options = LiveOptions(
    model="nova-2",
    language="en-US",
    encoding="linear16",
    channels=CHANNELS,
    sample_rate=RATE,
    endpointing=300,
    vad_events=True,
    interim_results=True,
    utterance_end_ms="1000"
)

def convert_float32_to_int16(raw_bytes: bytes) -> bytes:
    """
    Convert a bytes object containing little-endian float32 samples (range -1.0 to 1.0)
    to a bytes object of int16 samples using NumPy.
    """
    # Convert raw bytes to a NumPy array of float32 values
    float_samples = np.frombuffer(raw_bytes, dtype=np.float32)

    # Clip the values to the range [-1.0, 1.0]
    clipped_samples = np.clip(float_samples, -1.0, 1.0)

    # Scale to int16 range and convert the data type
    int16_samples = (clipped_samples * 32767).astype(np.int16)

    return int16_samples.tobytes()

async def get_audio_for_transcription(websocket: WebSocket, input_audio_store_queue:asyncio.Queue):
    print("Entered get audio function")
    try:
        while True:
            raw_audio = await websocket.receive_bytes()
            print(f"Received raw audio chunk of size {len(raw_audio)} bytes")
            int16_audio = convert_float32_to_int16(raw_audio)
            await input_audio_store_queue.put(int16_audio)

    except WebSocketDisconnect:
        print("websocket Disconnected")

    except Exception as e:
        print(f"Error occurred --> {e}")


async def send_audio_for_transcription(dg_connection,input_audio_store_queue: asyncio.Queue):
    try:
        while True:
            data = await input_audio_store_queue.get()
            await dg_connection.send(data)

    except asyncio.CancelledError:
        print("Transcription task cancelled")

    except Exception as e:
        print(f"Error occurred --> {e}")


async def receive_transcript(dg_connection, transcript_store_list: list[str],session_id:str):
    print('Entered receive transcript')
    async def on_message(self, result, **kwargs):
        sentence = result.channel.alternatives[0].transcript
        if len(sentence) > 0:
            print(f"Transcript: {sentence}, session_id --> {session_id}")
            transcript_store_list.append(sentence)

    async def on_error(error, **kwargs):
        print(f"Deepgram Error: {error}")
        logger.error(f"Deepgram Error: {error}")

    dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
    dg_connection.on(LiveTranscriptionEvents.Error, on_error)



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    input_audio_store_queue = asyncio.Queue()
    transcript_store_list = []
    deepgram = DeepgramClient("49630c797e6d4eede50979dfc25c9e629af77b10", config)
    dg_connection_listen = deepgram.listen.asyncwebsocket.v("1")

    await dg_connection_listen.start(options)

    # session_id = s_id["session_id"]
    session_id = "383883803803"
    try:
        task_get_audio_for_transcription = asyncio.create_task(get_audio_for_transcription(websocket, input_audio_store_queue))
        task_send_audio_for_transcription = asyncio.create_task(send_audio_for_transcription(dg_connection_listen, input_audio_store_queue))
        task_receive_transcript = asyncio.create_task(receive_transcript(dg_connection_listen, transcript_store_list,session_id))
        # task_produce_audio_of_response = asyncio.create_task(produce_audio_of_response(dg_connection_speak, response_store_queue, output_audio_store_queue))
        # task_audio_send_to_user = asyncio.create_task(send_tts_audio(websocket, output_audio_store_queue))
        # tasks = [task_get_audio_for_transcription, task_send_audio_for_transcription, task_receive_transcript,
        #          task_produce_audio_of_response, task_audio_send_to_user]
        tasks = [task_get_audio_for_transcription,task_send_audio_for_transcription,task_receive_transcript]

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for task in pending:
            task.cancel()

    except Exception as e:
        print(f"Error: {e}")


    finally:
        await websocket.close()

    # Write the int16 PCM data to a WAV file.
    # Make sure to set the sample rate to match the client's capture rate.
    # For many browsers, the AudioContext sample rate is 48000 Hz.
    # filename = os.path.join(AUDIO_DIR, f"audio_{connection_id}.wav")
    # with wave.open(filename, 'wb') as wf:
    #     wf.setnchannels(1)  # Mono audio (adjust if needed)
    #     wf.setsampwidth(2)  # 16-bit sample width
    #     wf.setframerate(48000)  # 48000 Hz sample rate (match this to your AudioContext.sampleRate)
    #     int16_audio = convert_float32_to_int16(audio_data)
    #     wf.writeframes(int16_audio)
    # print(f"Audio saved to {filename}")




if __name__ == "__main__":
    uvicorn.run("deepgram2:app", host="0.0.0.0", port=8000, reload=True)
