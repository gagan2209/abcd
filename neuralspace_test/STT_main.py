import neuralspace as ns
import asyncio
import websockets
import numpy as np



async def handler(websocket):  # Make sure it's async
    print(f"Client connected")
    try:
        while True:
            audio_chunk = await websocket.recv() # await is crucial
            if isinstance(audio_chunk, str):
                print("Received non-binary data, ignoring.")
                continue
            audio_array = np.frombuffer(audio_chunk, dtype=np.int16)

            print(f"Received chunk of {len(audio_array)} samples")

            # ... Your audio processing logic here ...

    except websockets.exceptions.ConnectionClosedError:
        print("Client disconnected")
    except Exception as e:
        print(f"An error occurred: {e}")


async def main():
    async with websockets.serve(handler, "localhost", 8000):
        print("WebSocket server started at ws://localhost:8000")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())