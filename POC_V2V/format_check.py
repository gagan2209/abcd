import asyncio
import websockets
import os
import io
from pydub import AudioSegment

async def handler(websocket):
    print("Client connected")
    audio_data = io.BytesIO()

    try:
        async for chunk in websocket:
            if isinstance(chunk, bytes):
                audio_data.write(chunk)
                print(f"Received chunk of {len(chunk)} bytes")
            else:
                print("Received non-binary data, ignoring.")

    except websockets.exceptions.ConnectionClosedError:
        print("Client disconnected")
    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        audio_data.seek(0)  # <-- Reset to the beginning of the stream

        if audio_data.getbuffer().nbytes > 0: # Check the size *after* resetting
            try:
                audio = AudioSegment.from_file(audio_data, format="webm", sample_rate=48000, channels=1) # Adjust if needed
                audio.export("recording.mp3", format="mp3")
                print("Audio saved as recording.mp3")
            except Exception as e:
                print(f"Error converting to mp3: {e}")
        else:
            print("No audio data received.")

async def main():
    async with websockets.serve(handler, "localhost", 8000):
        print("WebSocket server started at ws://localhost:8000")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())