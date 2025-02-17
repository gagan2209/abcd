import asyncio
from queue import Queue

import json
import requests
import uvicorn
import websockets
import httpx
import re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents, DeepgramClientOptions, SpeakWebSocketEvents, SpeakWSOptions
import logging
import numpy as np
from requests import session


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


##################################### DEEPGRAM CONFIG #######################################

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
Persona = "dlkmmlskdmclksdmclkfsdmclkm"
domain_name = "mfma"

app = FastAPI()

s_id = {}
current_utterance = ""
user_input = ""

# async def get_audio_for_transcription(websocket: WebSocket, input_audio_store_queue: asyncio.Queue):
#     """  Continuously read audio chunk from the browser and store it into asyncio Queue
#
#         :return --> Error if any
#     """
#     print("entered get_audio")
#     try:
#         while True:
#             data = await websocket.receive_bytes()
#             float_data = np.frombuffer(data, dtype=np.float32)
#
#             float_data = np.clip(float_data, -1.0, 1.0)
#
#             int16_data = (float_data * 32767).astype(np.int16)
#             int16_data = int16_data.tobytes()
#
#             await input_audio_store_queue.put(int16_data)
#     except WebSocketDisconnect:
#         print("Client Disconnected from Websocket")
#     except Exception as e:
#         print(f"Error feggrg: {e}")


async def get_audio_for_transcription(websocket: WebSocket, input_audio_store_queue: asyncio.Queue):
    """Continuously read audio chunks from the browser and store them into an asyncio Queue."""
    print("entered get_audio")
    try:
        while True:
            message = await websocket.receive()
            # Check if the message is binary
            if "bytes" in message and message["bytes"] is not None:
                data = message["bytes"]
                # Process the binary data as 32-bit floats
                float_data = np.frombuffer(data, dtype=np.float32)
                float_data = np.clip(float_data, -1.0, 1.0)
                int16_data = (float_data * 32767).astype(np.int16)
                int16_data = int16_data.tobytes()
                await input_audio_store_queue.put(int16_data)
            elif "text" in message:
                # Optionally process or log text messages
                print("Received text message (ignoring for audio processing):", message["text"])
            else:
                print("Received message with unexpected format:", message)
    except WebSocketDisconnect:
        print("Client Disconnected from Websocket")
    except Exception as e:
        print(f"Error feggrg: {e}")


async def send_audio_for_transcription(dg_connection,input_audio_store_queue: asyncio.Queue):
    """ Deque Audio chunks  and send them to DeepGram for transcription
        :return --> Error if any
    """


    try:
        while True:
            data = await input_audio_store_queue.get()
            await dg_connection.send(data)

    except asyncio.CancelledError:
        print("Transcription process cancelled")
    except Exception as e:
        print(f"Error: {e}")


async def call_exei_query_api(session_id: str, user_input: str, persona: str, domain_name: str,response_store_queue: asyncio.Queue):

    """ Calls the exei api with the user_input as transcription from deepgram  and streams text chunks as response from the exei,
        results are stored in response_store_queue.

        :return -- >
    """
    url = "https://qa-chat.exei.ai/stream_voice"
    payload = {
        "session_id": session_id,
        "user_input": user_input,
        "persona": persona,
        "domain_name": domain_name
    }

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST",url,json = payload) as response:
                 pattern = r"'chunk':\s*'([^']*)'"
                 async for line in response.aiter_lines():
                     line = line.strip()
                     if not line:
                         continue
                     match = re.search(pattern,line)
                     if match:
                         chunk_text = match.group(1)
                         print(f"Response from Exei: {chunk_text}")
                         await response_store_queue.put(chunk_text)
                     else:
                         continue

    except Exception as e:
        print(f"Error in Exei API: {e}")


# async def receive_transcript(dg_connection, transcript_store_queue: asyncio.Queue, response_store_queue: asyncio.Queue, session_id: str):
#     """
#     Receive transcript and call exei api and store it in response_store queue
#     :param dg_connection: Establish connection to deepgram
#     :param transcript_store_queue: Queue to store transcription
#     :param response_store_queue: Queue to store response from the Exei
#     :param session_id: session_id
#     :return: Error if any
#     """
#
#     try:
#         async def on_message(self, result, **kwargs):
#             print("Entered receive function ")
#             global current_utterance, user_input
#             try:
#                 current_transcript  = result.channel.alternatives[0].transcript
#                 if result.is_final:
#                     if current_utterance not in user_input:
#                         user_input += current_transcript + " "
#                 if current_utterance == "" and len(user_input) != 0:
#                     print(f"Transcription: {user_input}")
#                     await transcript_store_queue.put(user_input)
#                     asyncio.create_task(call_exei_query_api(session_id, user_input, Persona, domain_name, response_store_queue))
#                     logger.info(f"session_id: {session_id}, transcription: {user_input}")
#             except Exception as e:
#                 print(f"Error in on_message: {e}")
#                 logger.error(f"Error in on_message: {e}")
#
#         async def on_error(self, error, **kwargs):
#             print(f"Deepgram Error: {error}")
#             logger.error(f"Deepgram Error: {error}")
#
#         dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
#         dg_connection.on(LiveTranscriptionEvents.Error, on_error)
#
#         # Keep the function running
#         while True:
#             await asyncio.sleep(1)
#
#     except Exception as e:
#         print(f"Error in receive_transcript: {e}")
#         logger.error(f"Error in receive_transcript: {e}")
#

async def receive_transcript(dg_connection, transcript_store_queue: asyncio.Queue, response_store_queue: asyncio.Queue,
                             session_id: str):
    """
    Receive transcript from Deepgram, accumulate transcript chunks, and when a final result is received,
    send the accumulated transcript to the transcription store queue and trigger the Exei API call.
    """
    accumulated_transcript = ""  # Local variable to accumulate transcript text

    async def on_message(result, **kwargs):
        nonlocal accumulated_transcript
        try:
            # Extract the current transcript chunk from Deepgram result
            transcript_chunk = result.channel.alternatives[0].transcript
            if result.is_final:
                # Append the final chunk to our accumulated transcript (trim any extra spaces)
                if transcript_chunk:
                    accumulated_transcript += transcript_chunk.strip() + " "

                # Once a final result is reached, send the transcript for further processing
                if accumulated_transcript.strip():
                    print(f"Final transcript: {accumulated_transcript.strip()}")
                    await transcript_store_queue.put(accumulated_transcript.strip())
                    # Trigger the Exei API call asynchronously
                    asyncio.create_task(
                        call_exei_query_api(session_id, accumulated_transcript.strip(), Persona, domain_name,
                                            response_store_queue))
                    # Reset the accumulated transcript for the next utterance
                    accumulated_transcript = ""
            else:
                # Optionally handle interim results, e.g., log or update UI
                print(f"Interim transcript: {transcript_chunk}")
        except Exception as e:
            print(f"Error in on_message: {e}")
            logger.error(f"Error in on_message: {e}")

    async def on_error(error, **kwargs):
        print(f"Deepgram Error: {error}")
        logger.error(f"Deepgram Error: {error}")

    # Register event callbacks with the Deepgram connection
    dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
    dg_connection.on(LiveTranscriptionEvents.Error, on_error)

    # Keep the function running indefinitely
    while True:
        await asyncio.sleep(1)


async def produce_audio_of_response(dg_connection,response_store_queue,output_audio_store_queue):
    try:
        async def on_binary_data(self,data, **kwargs):
            try:
                await output_audio_store_queue.put(data)
            except Exception as e:
                print(f"Error: {e}")

        dg_connection.on(SpeakWebSocketEvents.AudioData, on_binary_data)
        options = SpeakWSOptions(
            model="aura-asteria-en",
            encoding="linear16",
            sample_rate=24000,

        )
        await dg_connection.start(options)
        if not await dg_connection.start(options):
            print("Failed to start connection")
            return
        while True:
            try:
                tts_text = await response_store_queue.get()

                await dg_connection.send_text(tts_text)
                await dg_connection.flush()
                await dg_connection.wait_for_complete()


            except Exception as e:
                print(f"Error: {e}")


    except Exception as e:
        print(f"Error: {e}")

    finally:
        await dg_connection.finish()

async def send_tts_audio(websocket: WebSocket, output_audio_store_queue: asyncio.Queue):
    try:
        while True:
            data = await output_audio_store_queue.get()
            await websocket.send_bytes(data)
    except Exception as e:
        logger.error(f"Error sending TTS audio: {e}")



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    input_audio_store_queue = asyncio.Queue()
    transcript_store_queue = asyncio.Queue()
    response_store_queue = asyncio.Queue()
    output_audio_store_queue = asyncio.Queue()


    deepgram = DeepgramClient("49630c797e6d4eede50979dfc25c9e629af77b10",config)
    dg_connection_listen = deepgram.listen.asyncwebsocket.v("1")
    dg_connection_speak = deepgram.speak.asyncwebsocket.v("1")


    await dg_connection_listen.start(options)

    # session_id = s_id["session_id"]
    session_id = "383883803803"

    try:
        task_get_audio_for_transcription = asyncio.create_task(get_audio_for_transcription(websocket,input_audio_store_queue))
        task_send_audio_for_transcription = asyncio.create_task(send_audio_for_transcription(dg_connection_listen,input_audio_store_queue))
        task_receive_transcript = asyncio.create_task(receive_transcript(dg_connection_listen,transcript_store_queue,response_store_queue,session_id))
        task_produce_audio_of_response = asyncio.create_task(produce_audio_of_response(dg_connection_speak,response_store_queue,output_audio_store_queue))
        task_audio_send_to_user = asyncio.create_task(send_tts_audio(websocket, output_audio_store_queue))
        tasks = [task_get_audio_for_transcription, task_send_audio_for_transcription, task_receive_transcript,task_produce_audio_of_response, task_audio_send_to_user]

        done,pending = await asyncio.wait(tasks,return_when=asyncio.FIRST_EXCEPTION)
        for task in pending:
            task.cancel()

    except Exception as e:
            print(f"Error: {e}")


    finally:
        await websocket.close()


if __name__ == "__main__":
    uvicorn.run("deepgram_1:app",host="0.0.0.0", port=8000,reload=True)

















