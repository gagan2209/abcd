# import asyncio
# import websockets
#
# from amazon_transcribe.client import TranscribeStreamingClient
# from amazon_transcribe.handlers import TranscriptResultStreamHandler
# from amazon_transcribe.model import TranscriptEvent
#
#
# class MyEventHandler(TranscriptResultStreamHandler):
#     async def handle_transcript_event(self, transcript_event: TranscriptEvent):
#         # This handler can be implemented to handle transcriptions as needed.
#         # Here's an example to get started.
#         results = transcript_event.transcript.results
#         for result in results:
#             for alt in result.alternatives:
#                 print(alt.transcript)
#
#
#
# async def websocket_stream(websocket):
#     # This function handles receiving audio from the client WebSocket.
#     while True:
#         try:
#             # Receive raw audio data from the WebSocket connection
#             audio_chunk = await websocket.recv()
#             # print(f"receive audio: {len(audio_chunk)}")
#             yield audio_chunk, None  # Return audio data, no status
#         except websockets.ConnectionClosed:
#             print("Connection closed")
#             break
#
# async def write_chunks(stream, websocket):
#     # This connects the raw audio chunks generator coming from the WebSocket
#     # and passes them along to the transcription stream.
#     async for chunk, status in websocket_stream(websocket):
#         # print("sending chunk...")
#         await stream.input_stream.send_audio_event(audio_chunk=chunk)
#     await stream.input_stream.end_stream()
#
#
# async def websocket_handler(websocket, path):
#     # Setup up our client with our chosen AWS region
#     client = TranscribeStreamingClient(region="us-east-2")
#
#     # Start transcription to generate our async stream
#     stream = await client.start_stream_transcription(
#         language_code="en-US",
#         media_sample_rate_hz=16000,
#         media_encoding="pcm"
#     )
#
#     # Instantiate our handler and start processing events
#     handler = MyEventHandler(stream.output_stream)
#     await asyncio.gather(write_chunks(stream, websocket), handler.handle_events())
#
#
# async def basic_transcribe():
#     # Setup up our client with our chosen AWS region
#     client = TranscribeStreamingClient(region="us-east-2")
#
#     # Start transcription to generate our async stream
#     stream = await client.start_stream_transcription(
#         language_code="en-US",
#         media_sample_rate_hz=16000,
#         media_encoding="pcm"
#     )
#
#     # Instantiate our handler and start processing events
#     handler = MyEventHandler(stream.output_stream)
#     await asyncio.gather(write_chunks(stream), handler.handle_events())
#
#
# async def main():
#     async with websockets.serve(websocket_handler, "0.0.0.0", 8000):
#         await asyncio.Future()  # Run forever
#
#
# # Run the WebSocket server
# asyncio.run(main())
#


from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from fastapi.responses import HTMLResponse  # Import this to return HTML response
from amazon_transcribe.model import TranscriptEvent
import uvicorn
import asyncio


# class MyEventHandler(TranscriptResultStreamHandler):
#     def __init__(self, output_stream, websocket: WebSocket):
#         super().__init__(output_stream)
#         self.websocket = websocket
#         self.last_transcript = None  # Track the last sent transcript
#
#     async def handle_transcript_event(self, transcript_event: TranscriptEvent):
#         # Handle the transcription event and send the transcript result to the frontend
#         results = transcript_event.transcript.results
#         for result in results:
#             for alt in result.alternatives:
#                 transcript_text = alt.transcript
#
#                 # Skip sending if the transcript is very similar to the last one
#                 if self.last_transcript and self.is_similar(self.last_transcript, transcript_text):
#                     continue  # Don't send similar text again
#
#                 # Send only the final results
#                 if not result.is_partial:  # Check for final result
#                     print(f"Sending transcript: {transcript_text}")
#                     await self.websocket.send_text(transcript_text)
#                     self.last_transcript = transcript_text  # Update for the next event
#
#     def is_similar(self, old_text: str, new_text: str) -> bool:
#         # Simple similarity check (you can improve this as needed)
#         return old_text.strip().lower() == new_text.strip().lower()

class MyEventHandler(TranscriptResultStreamHandler):
    def __init__(self, output_stream, websocket: WebSocket):
        super().__init__(output_stream)
        self.websocket = websocket
        self.last_transcript = ""  # Store the last transcript

    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        results = transcript_event.transcript.results
        for result in results:
            for alt in result.alternatives:
                transcript_text = alt.transcript
                print(transcript_text)

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


async def websocket_stream(websocket: WebSocket):
    while True:
        try:
            audio_chunk = await websocket.receive_bytes()
            yield audio_chunk, None
        except WebSocketDisconnect:
            print("Connection closed")
            break


async def write_chunks(stream, websocket: WebSocket):
    async for chunk, status in websocket_stream(websocket):
        await stream.input_stream.send_audio_event(audio_chunk=chunk)
    await stream.input_stream.end_stream()


async def websocket_handler(websocket: WebSocket):
    client = TranscribeStreamingClient(region="us-east-2")
    stream = await client.start_stream_transcription(
        language_code="en-IN",
        media_sample_rate_hz=16000,
        media_encoding="pcm"
    )

    handler = MyEventHandler(stream.output_stream, websocket)
    await asyncio.gather(write_chunks(stream, websocket), handler.handle_events())


app = FastAPI()
origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@CORSMiddleware
@app.websocket("/stream")
async def transcribe(websocket: WebSocket):
    await websocket.accept()
    try:
        await websocket_handler(websocket)
    except WebSocketDisconnect:
        print("WebSocket connection closed")


# Serve static files (HTML file)
app.add_route("/", lambda request: HTMLResponse(open("templates/index2.html").read()))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


