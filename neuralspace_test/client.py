import asyncio
import websockets
import pyaudio

# WebSocket server URL
WS_URL = "ws://localhost:8000/stt"

# Audio parameters
RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK = 2048  # Adjust for smooth streaming

async def send_audio():
    async with websockets.connect(WS_URL) as websocket:
        print("✅ Connected to WebSocket.")

        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )

        print("🎤 Speak into the microphone...")

        try:
            while True:
                data = stream.read(CHUNK, exception_on_overflow=False)
                print(f"🎧 Sending {len(data)} bytes of audio")  # Debug print
                await websocket.send(data)  # Send audio

                # Try to receive response asynchronously (non-blocking)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2)
                    print("Response:", response)
                except asyncio.TimeoutError:
                    print("No response received yet...")  # Don't block if no response

        except KeyboardInterrupt:
            print("Stopping...")
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()

asyncio.run(send_audio())
