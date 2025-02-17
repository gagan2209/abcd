from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.middleware.cors import CORSMiddleware
# from amazon_transcribe.client import TranscribeStreamingClient
# from amazon_transcribe.handlers import TranscriptResultStreamHandler
# from fastapi.responses import HTMLResponse  # Import this to return HTML response
# from amazon_transcribe.model import TranscriptEvent
import uvicorn
import asyncio
import numpy as np

# class MyEventHandler(TranscriptResultStreamHandler):
#     def __init__(self, output_stream, websocket: WebSocket):
#         super().__init__(output_stream)
#         self.websocket = websocket
#         self.last_transcript = ""  # Store the last transcript
#
#     async def handle_transcript_event(self, transcript_event: TranscriptEvent):
#         results = transcript_event.transcript.results
#         for result in results:
#             for alt in result.alternatives:
#                 transcript_text = alt.transcript
#                 print(transcript_text)

    #             # Only send the new part of the transcript that hasn't been sent
    #             if not result.is_partial:  # Only final results
    #                 new_text = self.get_new_text(self.last_transcript, transcript_text)
    #                 if new_text:
    #                     print(f"Sending new transcript part: {new_text}")
    #                     await self.websocket.send_text(new_text)
    #                     self.last_transcript = transcript_text  # Update the last transcript
    #
    # def get_new_text(self, last_text: str, current_text: str) -> str:
    #     # Find the new part of the current text that hasn't been sent yet
    #     if current_text.startswith(last_text):  # If the current text is an extension of the last text
    #         return current_text[len(last_text):].strip()
    #     return current_text  # If it's a completely new sentence, send it all


app = FastAPI()

async def websocket_stream(websocket: WebSocket):
    while True:
        try:
            audio_chunk = await websocket.receive_bytes()
            audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
            yield audio_chunk, None
        except WebSocketDisconnect:
            print("Connection closed")
            break


async def write_chunks(stream, websocket: WebSocket):
    async for chunk, status in websocket_stream(websocket):
        await stream.input_stream.send_audio_event(audio_chunk=chunk)
    await stream.input_stream.end_stream()



# async def websocket_handler(websocket: WebSocket):
#     client = TranscribeStreamingClient(region="us-east-2")
#     stream = await client.start_stream_transcription(
#         language_code="en-IN",
#         media_sample_rate_hz=16000,
#         media_encoding="pcm"
#     )
#
#     handler = MyEventHandler(stream.output_stream, websocket)
#     await asyncio.gather(write_chunks(stream, websocket), handler.handle_events())
#
#
# app = FastAPI()
# origins = [
#     "http://localhost.tiangolo.com",
#     "https://localhost.tiangolo.com",
#     "http://localhost",
#     "http://localhost:8080",
# ]
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
#
# @CORSMiddleware
# @app.websocket("/stream")
# async def transcribe(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         await websocket_handler(websocket)
#     except WebSocketDisconnect:
#         print("WebSocket connection closed")


# # Serve static files (HTML file)
# app.add_route("/", lambda request: HTMLResponse(open("templates/index2.html").read()))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


