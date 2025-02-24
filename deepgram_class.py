import asyncio
import json
import requests
import uvicorn
import websockets
import httpx
import re
import logging
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents, DeepgramClientOptions, SpeakWebSocketEvents, SpeakWSOptions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Voice2Voice:
    def __init__(self):
        self.config = DeepgramClientOptions(options={"keepalive": "true"})
        self.CHANNELS = 1
        self.RATE = 16000
        self.options = LiveOptions(
            model="nova-2",
            language="en-US",
            encoding="linear16",
            channels=self.CHANNELS,
            sample_rate=self.RATE,
            endpointing=300,
            vad_events=True,
            interim_results=True,
            utterance_end_ms="1000"
        )
        self.persona = "dlkmmlskdmclksdmclkfsdmclkm"
        self.domain_name = "mfma"
        self.app = FastAPI()
        self.session_id = "383883803803"

    async def get_audio_for_transcription(self, websocket: WebSocket, input_audio_store_queue: asyncio.Queue):
        print("entered get_audio")
        try:
            while True:
                message = await websocket.receive()
                if "bytes" in message and message["bytes"] is not None:
                    data = message["bytes"]
                    float_data = np.frombuffer(data, dtype=np.float32)
                    float_data = np.clip(float_data, -1.0, 1.0)
                    int16_data = (float_data * 32767).astype(np.int16).tobytes()
                    await input_audio_store_queue.put(int16_data)
        except WebSocketDisconnect:
            print("Client Disconnected from Websocket")
        except Exception as e:
            print(f"Error: {e}")

    async def send_audio_for_transcription(self, dg_connection, input_audio_store_queue: asyncio.Queue):
        try:
            while True:
                data = await input_audio_store_queue.get()
                await dg_connection.send(data)
        except asyncio.CancelledError:
            print("Transcription process cancelled")
        except Exception as e:
            print(f"Error: {e}")

    async def call_exei_query_api(self, user_input: str, response_store_queue: asyncio.Queue):
        url = "https://qa-chat.exei.ai/stream_voice"
        payload = {
            "session_id": self.session_id,
            "user_input": user_input,
            "persona": self.persona,
            "domain_name": self.domain_name
        }
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, json=payload) as response:
                    pattern = r"'chunk':\s*'([^']*)'"
                    async for line in response.aiter_lines():
                        line = line.strip()
                        match = re.search(pattern, line)
                        if match:
                            chunk_text = match.group(1)
                            await response_store_queue.put(chunk_text)
        except Exception as e:
            print(f"Error in Exei API: {e}")

    async def receive_transcript(self, dg_connection, transcript_store_queue: asyncio.Queue, response_store_queue: asyncio.Queue):
        accumulated_transcript = ""

        async def on_message(result, **kwargs):
            nonlocal accumulated_transcript
            try:
                transcript_chunk = result.channel.alternatives[0].transcript
                if result.is_final and transcript_chunk:
                    accumulated_transcript += transcript_chunk.strip() + " "
                    if accumulated_transcript.strip():
                        await transcript_store_queue.put(accumulated_transcript.strip())
                        asyncio.create_task(self.call_exei_query_api(accumulated_transcript.strip(), response_store_queue))
                        accumulated_transcript = ""
            except Exception as e:
                logger.error(f"Error in on_message: {e}")

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

        while True:
            await asyncio.sleep(1)

    async def produce_audio_of_response(self, dg_connection, response_store_queue, output_audio_store_queue):
        async def on_binary_data(self, data, **kwargs):
            await output_audio_store_queue.put(data)

        dg_connection.on(SpeakWebSocketEvents.AudioData, on_binary_data)
        options = SpeakWSOptions(model="aura-asteria-en", encoding="linear16", sample_rate=24000)
        await dg_connection.start(options)

        while True:
            try:
                tts_text = await response_store_queue.get()
                await dg_connection.send_text(tts_text)
                await dg_connection.flush()
                await dg_connection.wait_for_complete()
            except Exception as e:
                print(f"Error: {e}")

    async def send_tts_audio(self, websocket: WebSocket, output_audio_store_queue: asyncio.Queue):
        try:
            while True:
                data = await output_audio_store_queue.get()
                await websocket.send_bytes(data)
        except Exception as e:
            logger.error(f"Error sending TTS audio: {e}")

    async def websocket_endpoint(self, websocket: WebSocket):
        await websocket.accept()
        input_audio_store_queue = asyncio.Queue()
        transcript_store_queue = asyncio.Queue()
        response_store_queue = asyncio.Queue()
        output_audio_store_queue = asyncio.Queue()

        deepgram = DeepgramClient("49630c797e6d4eede50979dfc25c9e629af77b10", self.config)
        dg_connection_listen = deepgram.listen.asyncwebsocket.v("1")
        dg_connection_speak = deepgram.speak.asyncwebsocket.v("1")
        await dg_connection_listen.start(self.options)

        tasks = [
            asyncio.create_task(self.get_audio_for_transcription(websocket, input_audio_store_queue)),
            asyncio.create_task(self.send_audio_for_transcription(dg_connection_listen, input_audio_store_queue)),
            asyncio.create_task(self.receive_transcript(dg_connection_listen, transcript_store_queue, response_store_queue)),
            asyncio.create_task(self.produce_audio_of_response(dg_connection_speak, response_store_queue, output_audio_store_queue)),
            asyncio.create_task(self.send_tts_audio(websocket, output_audio_store_queue))
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for task in pending:
            task.cancel()
        await websocket.close()

app_instance = Voice2Voice()
app = app_instance.app
app.websocket("/ws")(app_instance.websocket_endpoint)

if __name__ == "__main__":
    uvicorn.run("deepgram_1:app", host="0.0.0.0", port=8000, reload=True)
