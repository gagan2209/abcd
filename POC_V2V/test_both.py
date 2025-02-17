# import asyncio
# import websockets
# import json
# import uuid
# import requests
# from googletrans import Translator
# from pydub import AudioSegment  # Used here for saving audio if needed
# # Import the NeuralSpace TTS API library (adjust this to your actual module)
# import neuralspace as ns
# # from denoiser import pretrained
# import httpx
# #############################################################################################################
#
#
# # Initialize translators and TTS API
# translator = Translator()
# vai = ns.VoiceAI(api_key='sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829')
#
# # NeuralSpace transcription configuration
# BASE = "https://voice.neuralspace.ai/api/v2/languages?type=stream"
# API_KEY = "sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829"
#
# headers = {"Authorization": API_KEY}
# response = requests.get(BASE, headers=headers)
# print(f"Languages available: {response.json().get('data', {}).get('languages', [])}")
#
# language = "en"
# min_chunk_size = 5
# vad_threshold = 0.9
# disable_partial = "True"
# audio_format = "pcm_16k"
# DURATION = 600
#
# # Fetch transcription token
# TOKEN_URL = f"https://voice.neuralspace.ai/api/v2/token?duration={DURATION}"
# response = requests.get(TOKEN_URL, headers=headers)
# TOKEN = response.json().get("data", {}).get("token")
# if not TOKEN:
#     raise ValueError("Failed to retrieve API token.")
# print(f"Received Token: {TOKEN}")
#
# # Generate unique session ID for transcription
# session_id = str(uuid.uuid4())
# print(f"Session ID: {session_id}")
#
# # WebSocket URL for NeuralSpace transcription
# NS_WEBSOCKET_URL = (
#     f"wss://voice.neuralspace.ai/voice/stream/live/transcribe/{language}/{TOKEN}/{session_id}"
#     f"?max_chunk_size={min_chunk_size}&vad_threshold={vad_threshold}&disable_partial={disable_partial}&format={audio_format}"
# )
# print(f"Connecting to NeuralSpace WebSocket: {NS_WEBSOCKET_URL}")
#
# # Async Queue for audio chunks to forward to NeuralSpace transcription
# q = asyncio.Queue()
#
# # Global accumulator for received raw PCM audio (if you wish to store it)
# pcm_data = bytearray()
#
# # Global accumulators for transcript and its translation
# # transcript_accumulator = ""
# # translate_accumulator = ""
# counter = 0
#
#
# async def process_audio(ws):
#     """Send audio chunks from queue to NeuralSpace transcription."""
#     try:
#         while True:
#             data = await q.get()
#             await ws.send(data)
#     except asyncio.CancelledError:
#         print("Audio processing task cancelled.")
#     except Exception as e:
#         print(f"Error in process_audio: {e}")
#
# async def receive_responses(ws):
#     """Receive transcription responses from NeuralSpace."""
#     # global transcript_accumulator, translate_accumulator, counter
#     global  counter
#
#     try:
#         async for message in ws:
#             try:
#                 response = json.loads(message)
#                 msg = response['text']
#
#                 translate_t = await translator.translate(msg, src="en", dest="ar")
#                 transcript_accumulator = ""
#                 translate_accumulator = ""
#                 transcript_accumulator += msg + " "
#                 translate_accumulator += translate_t.text + " "
#                 counter += 1
#
#                 if counter % 2 == 0:
#                     print(f"Transcripted Text: {transcript_accumulator}")
#                     print(f"Translated Text: {translate_accumulator}")
#             except json.JSONDecodeError as e:
#                 print("Failed to decode JSON:", e)
#     except websockets.exceptions.ConnectionClosed as e:
#         print(f"Transcription connection closed: code={e.code}, reason={e.reason}")
#     except Exception as e:
#         print(f"Error in receive_responses: {e}")
#
#
#
#
#
# async def transcription_handler(websocket, path=None):
#     """Handle incoming audio from the browser for transcription."""
#     global pcm_data
#     print("Transcription client connected.")
#     try:
#         async for message in websocket:
#             # Accumulate raw PCM audio
#             pcm_data.extend(message)
#             # Forward to NeuralSpace transcription via queue
#             await q.put(message)
#     except websockets.exceptions.ConnectionClosed:
#         print("Transcription client disconnected.")
#     except Exception as e:
#         print(f"Error in transcription_handler: {e}")
#
#
# async def tts_handler(websocket, path=None):
#     """
#     When a client connects to the TTS endpoint, continuously check for updated translated text.
#     When new text is available, call the TTS API and stream the resulting audio (as binary data)
#     back to the client.
#     """
#     global translate_accumulator
#     print("TTS client connected.")
#     last_sent_text = ""
#     try:
#         while True:
#             await asyncio.sleep(1)  # check every second
#             # If there's new text that hasn't been processed yet, synthesize TTS
#             if translate_accumulator and translate_accumulator != last_sent_text:
#                 data = {
#                     "text": translate_accumulator,
#                     "speaker_id": "ar-male-Omar-saudi-neutral",
#                     "stream": True,  # request raw byte streaming
#                     "sample_rate": 16000,
#                     "config": {
#                         "pace": 0.75,
#                         "volume": 1.0,
#                         "pitch_shift": 0,
#                         "pitch_scale": 1.0
#                     }
#                 }
#                 try:
#                     # Since vai.synthesize is synchronous, run it in an executor.
#                     loop = asyncio.get_event_loop()
#                     result = await loop.run_in_executor(None, vai.synthesize, data)
#                     # Assume result is a bytes object containing the audio data.
#                     # Stream the audio bytes to the TTS client.
#                     await websocket.send(result)
#                     print("Sent TTS audio chunk to client.")
#                     last_sent_text = translate_accumulator
#                 except Exception as e:
#                     print(f"TTS synthesis error: {e}")
#     except websockets.exceptions.ConnectionClosed:
#         print("TTS client disconnected.")
#     except Exception as e:
#         print(f"Error in tts_handler: {e}")
#
#
#
# async def main():
#     """Start both transcription and TTS WebSocket servers and the NeuralSpace transcription client."""
#     try:
#         # Connect to NeuralSpace transcription websocket
#         async with websockets.connect(NS_WEBSOCKET_URL) as ns_ws:
#             print("Connected to NeuralSpace transcription WebSocket.")
#             # Start the transcription WebSocket server on port 8000 (for audio input)
#             transcription_server = await websockets.serve(transcription_handler, "localhost", 8000)
#             print("Transcription WebSocket server started at ws://localhost:8000/stream")
#             # Start the TTS WebSocket server on port 8001 (for TTS output)
#             tts_server = await websockets.serve(tts_handler, "localhost", 8001)
#             print("TTS WebSocket server started at ws://localhost:8001/tts")
#             await asyncio.gather(
#                 process_audio(ns_ws),
#                 receive_responses(ns_ws),
#                 transcription_server.wait_closed(),
#                 tts_server.wait_closed()
#             )
#     except Exception as e:
#         print(f"Main connection error: {e}")
#     finally:
#         # Optionally, store the accumulated PCM data as an MP3 if desired.
#         if pcm_data:
#             try:
#                 print("Converting received PCM audio to MP3...")
#                 audio_segment = AudioSegment(
#                     data=pcm_data,
#                     sample_width=2,
#                     frame_rate=16000,
#                     channels=1
#                 )
#                 audio_segment.export("output.mp3", format="mp3")
#                 print("Saved MP3 as output.mp3")
#             except Exception as e:
#                 print(f"Error converting to MP3: {e}")
#         else:
#             print("No PCM audio data received; nothing to convert.")
#
#
# if __name__ == "__main__":
#     asyncio.run(main())


# import asyncio
# import websockets
# import json
# import uuid
# import requests
# import httpx
# from googletrans import Translator
# from pydub import AudioSegment  # For saving audio (optional)
# # Import your NeuralSpace TTS API library (adjust as needed)
# import neuralspace as ns
#
# #############################################################################################################
# # INITIALIZATION & CONFIGURATION
# #############################################################################################################
#
# # Initialize translator and NeuralSpace TTS API
# translator = Translator()
# vai = ns.VoiceAI(api_key='sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829')
#
# # NeuralSpace transcription configuration
# BASE = "https://voice.neuralspace.ai/api/v2/languages?type=stream"
# API_KEY = "sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829"
# headers = {"Authorization": API_KEY}
#
# # (Optional) List available languages
# response = requests.get(BASE, headers=headers)
# print(f"Languages available: {response.json().get('data', {}).get('languages', [])}")
#
# # Transcription settings (adjust as needed)
# language = "en"
# min_chunk_size = 3
# vad_threshold = 0.5
# disable_partial = "True"
# audio_format = "pcm_16k"
# DURATION = 600
#
# # Get transcription token from NeuralSpace
# TOKEN_URL = f"https://voice.neuralspace.ai/api/v2/token?duration={DURATION}"
# response = requests.get(TOKEN_URL, headers=headers)
# TOKEN = response.json().get("data", {}).get("token")
# if not TOKEN:
#     raise ValueError("Failed to retrieve API token.")
# print(f"Received Token: {TOKEN}")
#
# # Generate a unique session ID for this transcription session.
# session_id = str(uuid.uuid4())
# print(f"Session ID: {session_id}")
#
# # Build the WebSocket URL for NeuralSpace transcription.
# NS_WEBSOCKET_URL = (
#     f"wss://voice.neuralspace.ai/voice/stream/live/transcribe/{language}/{TOKEN}/{session_id}"
#     f"?max_chunk_size={min_chunk_size}&vad_threshold={vad_threshold}"
#     f"&disable_partial={disable_partial}&format={audio_format}"
# )
# print(f"Connecting to NeuralSpace WebSocket: {NS_WEBSOCKET_URL}")
#
# # Create an asynchronous queue to forward audio chunks.
# q = asyncio.Queue()
#
# # Global accumulator for raw PCM audio (if you wish to save it later)
# pcm_data = bytearray()
#
# # Global variable to hold the response from your model API (for TTS conversion)
# model_response = ""
#
# # Counter for demonstration purposes
# counter = 0
#
# #############################################################################################################
# # HELPER FUNCTION TO CALL THE FASTAPI MODEL ENDPOINT
# #############################################################################################################
# async def call_voice_api(session_id: str, user_input: str, persona: str,domain_name: str) -> str:
#     """
#     Asynchronously calls the FastAPI endpoint (running at http://localhost:8002/voice)
#     with the provided session_id, user_input, and persona.
#     Returns the 'response' string from the API.
#     """
#     url = "https://qa-chat.exei.ai/stream_voice" # Adjust URL if necessary.
#     payload = {"session_id": session_id, "user_input": user_input, "persona": persona,"domain_name":domain_name}
#     async with httpx.AsyncClient() as client:
#         response = await client.post(url, json=payload)
#     print(type(response))
#     response_json = response.json()
#     return response_json.get("response", "")
#
# #############################################################################################################
# # WEBSOCKET HANDLERS & CORE FUNCTIONS
# #############################################################################################################
# async def process_audio(ws):
#     """
#     Continuously get audio chunks from the async queue and forward them
#     to the NeuralSpace transcription WebSocket.
#     """
#     try:
#         while True:
#             data = await q.get()
#             await ws.send(data)
#     except asyncio.CancelledError:
#         print("Audio processing task cancelled.")
#     except Exception as e:
#         print(f"Error in process_audio: {e}")
#
# async def receive_responses(ws):
#     """
#     Receives transcription responses from NeuralSpace.
#     For each transcription received, call the FastAPI model API.
#     The model API’s response is then stored in a global variable for TTS conversion.
#     """
#     global counter, model_response, session_id
#     try:
#         async for message in ws:
#             try:
#                 # Decode the JSON message from NeuralSpace.
#                 response = json.loads(message)
#                 msg = response['text']  # This is the speech-to-text transcription.
#                 counter += 1
#                 print(f"Received transcription: {msg}")
#
#                 # Call your model API with the transcription text.
#                 # The persona can be a fixed string or dynamically set.
#                 api_response = await call_voice_api(session_id, msg, "**Company Overview:**Xcelore is a fast-growing, AI-driven innovation hub that builds and enhances digital products and platforms for a modern world. With bases in Noida and the Netherlands, Xcelore specializes in high-impact digital product engineering, cloud solutions, and AI-driven innovations for startups and enterprises across diverse industries. Their mission is to help businesses excel in the digital realm while pushing the boundaries of technological advancement and innovation.**Industry:**Xcelore operates in the Digital Technology Services & Product Engineering space, with expertise in:1. Generative AI R&D and PoC Lab2. AI-Led Product Development3. Digital Product Engineering4. Kotlin Multiplatform & Kotlin Server-side Development5. Offshore Development Teams**Unique Aspects:**1. Design-First, Cloud-Native, Agile & Fullstack approach2. Commitment to providing value with transparency, empathy & complete ownership3. Emphasis on AI-driven innovation and cutting-edge technology4. Focus on delivering intelligent, future-ready digital experiences**Driving Force:**Xcelore aims to disrupt the Digital Technology Services & Product Engineering space by integrating AI and next-gen technology into its solutions, enhancing efficiency, automation, and user engagement.**Core Values:**1. Excellence and Exploration2. T.I.E (Trust, Integrity, and Empathy)3. Continuous Learning and Sharing4. Fun-filled culture with work-life balance5. Ownership with Responsible Freedom**Communication Channels:**1. Phone: +91 81784 97981 (India) | +31 616884242 (Netherlands)2. Email: sales@xcelore.com, inbound@xcelore.com3. WhatsApp: +91 81784 979814. Social Media: LinkedIn, Twitter, Facebook, Instagram**Services:**1. Generative AI Solutions2. AI-Led Product Development3. Conversational AI & Chatbots4. ML Ops5. Digital Product Engineering6. Product Discovery & Design7. Web & Mobile App Development8. Microservices Development9. Cloud and DevOps Services10. Kotlin Development (Multiplatform, Server-side, Android, and Migration)11. Cloud & DevOps as a Service12. Cloud Managed Services13. Audits, Assessments & Consulting14. Cloud Migration & Modernization**AI-Powered Key Products:**1. **Exei – Virtual Assistant:** 24/7 AI-driven support for enhanced customer engagement and operational efficiency.2. **Xcelight – Business Intelligence:** Transforms CCTV systems into powerful business insight tools for efficiency and decision-making.3. **Translore – Real-Time Audio Translation:** Instant, accurate translations for seamless global communication.**Unique Initiatives:**1. Generative AI R&D and PoC Lab2. Offshore Development Teams3. Kotlin Multiplatform & Kotlin Server-side Development**Experience & Success:**- 40+ years of cumulative leadership experience- 100+ team members- 75+ global clients across 10+ industries- 200+ successful projects**Growth Partner Network:**Xcelore invites businesses to join its Growth Partner network, fostering collaborative success in business growth and digital transformation.**Terms of Service & Privacy Policy:**Xcelore's Terms of Service and Privacy Policy can be found on their website, outlining service conditions and data protection measures.At Xcelore, AI meets digital innovation, delivering intelligent solutions for businesses seeking performance enhancements, cost reductions, and superior user experiences. We don’t just develop digital solutions—we create future-ready intelligent experiences that keep businesses ahead of the curve.", "xcelore")
#                 print(f"Model API response: {api_response}")
#
#                 # Update the global variable to be used by the TTS handler.
#                 model_response = api_response
#             except json.JSONDecodeError as e:
#                 print("Failed to decode JSON:", e)
#     except websockets.exceptions.ConnectionClosed as e:
#         print(f"Transcription connection closed: code={e.code}, reason={e.reason}")
#     except Exception as e:
#         print(f"Error in receive_responses: {e}")
#
# async def transcription_handler(websocket, path=None):
#     """
#     Handles incoming audio data from the browser.
#     Audio chunks are accumulated (if desired) and forwarded via an async queue.
#     """
#     global pcm_data
#     print("Transcription client connected.")
#     try:
#         async for message in websocket:
#             # Accumulate raw PCM audio (for optional saving)
#             pcm_data.extend(message)
#             # Forward the audio chunk to NeuralSpace via the queue.
#             await q.put(message)
#     except websockets.exceptions.ConnectionClosed:
#         print("Transcription client disconnected.")
#     except Exception as e:
#         print(f"Error in transcription_handler: {e}")
#
# async def tts_handler(websocket, path=None):
#     """
#     When a TTS client connects, this function continuously checks for new
#     model responses (obtained from the transcription and API call).
#     When a new response is available, it uses NeuralSpace TTS to synthesize speech
#     and streams the audio back to the client.
#     """
#     global model_response
#     print("TTS client connected.")
#     last_sent_text = ""
#     try:
#         while True:
#             await asyncio.sleep(1)  # Poll every second.
#             if model_response and model_response != last_sent_text:
#                 # Prepare the data for TTS synthesis.
#                 data = {
#                     "text": model_response,
#                     "speaker_id": "en-male-Oscar-english-neutral",
#                     "stream": True,  # Request raw byte streaming.
#                     "sample_rate": 16000,
#                     "config": {
#                         "pace": 0.75,
#                         "volume": 1.0,
#                         "pitch_shift": 0,
#                         "pitch_scale": 1.0
#                     }
#                 }
#                 try:
#                     # Call the TTS synthesis (running synchronously in an executor).
#                     loop = asyncio.get_event_loop()
#                     result = await loop.run_in_executor(None, vai.synthesize, data)
#                     # Send the synthesized audio bytes back to the TTS client.
#                     await websocket.send(result)
#                     print("Sent TTS audio chunk to client.")
#                     last_sent_text = model_response
#                 except Exception as e:
#                     print(f"TTS synthesis error: {e}")
#     except websockets.exceptions.ConnectionClosed:
#         print("TTS client disconnected.")
#     except Exception as e:
#         print(f"Error in tts_handler: {e}")
#
# #############################################################################################################
# # MAIN FUNCTION TO START WEBSOCKET SERVERS & PROCESSING
# #############################################################################################################
# async def main():
#     """
#     Main function that:
#       - Connects to NeuralSpace transcription WebSocket.
#       - Starts the transcription WebSocket server (receiving audio from browser).
#       - Starts the TTS WebSocket server (streaming TTS audio back to the browser).
#       - Launches tasks to process audio and transcription responses.
#     """
#     try:
#         async with websockets.connect(NS_WEBSOCKET_URL) as ns_ws:
#             print("Connected to NeuralSpace transcription WebSocket.")
#             # Start a WebSocket server for receiving audio (transcription).
#             transcription_server = await websockets.serve(transcription_handler, "localhost", 8000)
#             print("Transcription WebSocket server started at ws://localhost:8000/stream")
#             # Start a WebSocket server for TTS output.
#             tts_server = await websockets.serve(tts_handler, "localhost", 8001)
#             print("TTS WebSocket server started at ws://localhost:8001/tts")
#             await asyncio.gather(
#                 process_audio(ns_ws),
#                 receive_responses(ns_ws),
#                 transcription_server.wait_closed(),
#                 tts_server.wait_closed()
#             )
#     except Exception as e:
#         print(f"Main connection error: {e}")
#     finally:
#         # Optionally, save the accumulated raw PCM audio to an MP3 file.
#         if pcm_data:
#             try:
#                 print("Converting received PCM audio to MP3...")
#                 audio_segment = AudioSegment(
#                     data=pcm_data,
#                     sample_width=2,
#                     frame_rate=16000,
#                     channels=1
#                 )
#                 audio_segment.export("output.mp3", format="mp3")
#                 print("Saved MP3 as output.mp3")
#             except Exception as e:
#                 print(f"Error converting to MP3: {e}")
#         else:
#             print("No PCM audio data received; nothing to convert.")
#
# if __name__ == "__main__":
#     asyncio.run(main())



import asyncio
import websockets
import json
import uuid
import requests
import httpx
from googletrans import Translator
from pydub import AudioSegment  # Used here for saving audio if needed
# Import the NeuralSpace TTS API library (adjust this to your actual module)
import neuralspace as ns
import re

#############################################################################################################
# INITIALIZATION & CONFIGURATION
#############################################################################################################

# Initialize translator and NeuralSpace TTS API
translator = Translator()
vai = ns.VoiceAI(api_key='sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829')

# NeuralSpace transcription configuration
BASE = "https://voice.neuralspace.ai/api/v2/languages?type=stream"
API_KEY = "sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829"
headers = {"Authorization": API_KEY}

# (Optional) List available languages
response = requests.get(BASE, headers=headers)
print(f"Languages available: {response.json().get('data', {}).get('languages', [])}")

# Transcription settings (adjust as needed)
language = "en"
min_chunk_size = 5
vad_threshold = 0.9
disable_partial = "True"
audio_format = "pcm_16k"
DURATION = 600

# Get transcription token from NeuralSpace
TOKEN_URL = f"https://voice.neuralspace.ai/api/v2/token?duration={DURATION}"
response = requests.get(TOKEN_URL, headers=headers)
TOKEN = response.json().get("data", {}).get("token")
if not TOKEN:
    raise ValueError("Failed to retrieve API token.")
print(f"Received Token: {TOKEN}")

# Generate a unique session ID for this transcription session.
session_id = str(uuid.uuid4())
print(f"Session ID: {session_id}")

# Build the WebSocket URL for NeuralSpace transcription.
NS_WEBSOCKET_URL = (
    f"wss://voice.neuralspace.ai/voice/stream/live/transcribe/{language}/{TOKEN}/{session_id}"
    f"?max_chunk_size={min_chunk_size}&vad_threshold={vad_threshold}"
    f"&disable_partial={disable_partial}&format={audio_format}"
)
print(f"Connecting to NeuralSpace WebSocket: {NS_WEBSOCKET_URL}")

# Create an asynchronous queue to forward audio chunks to NeuralSpace.
q = asyncio.Queue()

# Create a global asyncio.Queue to hold streaming text responses from your model API.
model_queue = asyncio.Queue()

# Global accumulator for raw PCM audio (if you wish to save it later)
pcm_data = bytearray()

# A counter (for demonstration, e.g. number of transcriptions received)
counter = 0


#############################################################################################################
# HELPER FUNCTION TO CALL THE STREAMING MODEL API
#############################################################################################################
async def call_voice_api(session_id: str, user_input: str, persona: str, domain_name: str):
    """
    Calls the external model API (https://qa-chat.exei.ai/voice) with the given parameters.
    This endpoint streams JSON responses (each containing a "chunk" key). As soon as each
    chunk is received, it is parsed and pushed into the global model_queue.
    """
    url = "https://qa-chat.exei.ai/stream_voice"
    payload = {
        "session_id": session_id,
        "user_input": user_input,
        "persona": persona,
        "domain_name": domain_name
    }
    try:
        # Use httpx.AsyncClient with no timeout (or adjust timeout as needed)
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", url, json=payload) as response:
                # Process the streaming response line by line.

                pattern = r"'chunk':\s*'([^']*)'"

                async for line in response.aiter_lines():
                    line = line.strip()  # Remove any leading/trailing whitespace
                    if not line:
                        continue  # Skip empty lines

                    # Apply regex to extract the chunk text.
                    match = re.search(pattern, line)
                    if match:
                        chunk_text = match.group(1)
                        print(chunk_text)
                        # Immediately push this chunk into the model_queue.
                        await model_queue.put(chunk_text)
                    else:
                        print(f"No text extracted")

    except Exception as e:
        print(f"Error calling voice API: {e}")


#############################################################################################################
# WEBSOCKET HANDLERS & CORE FUNCTIONS
#############################################################################################################
async def process_audio(ws):
    """
    Continuously get audio chunks from the async queue and forward them
    to the NeuralSpace transcription WebSocket.
    """
    try:
        while True:
            data = await q.get()
            await ws.send(data)
    except asyncio.CancelledError:
        print("Audio processing task cancelled.")
    except Exception as e:
        print(f"Error in process_audio: {e}")


async def receive_responses(ws):
    """
    Receives transcription responses from NeuralSpace.
    For each transcription received, it launches a task to call the streaming model API.
    """
    global counter, session_id
    try:
        async for message in ws:
            try:
                response_data = json.loads(message)
                msg = response_data['text']  # The transcription text
                counter += 1
                print(f"Received transcription: {msg}")

                # Launch the model API call as a separate task so we can process streaming chunks.
                # Replace "default" and "your_domain_here" with your actual persona and domain_name.
                asyncio.create_task(call_voice_api(session_id, msg, "**Company Overview:**Xcelore is a fast-growing, AI-driven innovation hub that builds and enhances digital products and platforms for a modern world. With bases in Noida and the Netherlands, Xcelore specializes in high-impact digital product engineering, cloud solutions, and AI-driven innovations for startups and enterprises across diverse industries. Their mission is to help businesses excel in the digital realm while pushing the boundaries of technological advancement and innovation.**Industry:**Xcelore operates in the Digital Technology Services & Product Engineering space, with expertise in:1. Generative AI R&D and PoC Lab2. AI-Led Product Development3. Digital Product Engineering4. Kotlin Multiplatform & Kotlin Server-side Development5. Offshore Development Teams**Unique Aspects:**1. Design-First, Cloud-Native, Agile & Fullstack approach2. Commitment to providing value with transparency, empathy & complete ownership3. Emphasis on AI-driven innovation and cutting-edge technology4. Focus on delivering intelligent, future-ready digital experiences**Driving Force:**Xcelore aims to disrupt the Digital Technology Services & Product Engineering space by integrating AI and next-gen technology into its solutions, enhancing efficiency, automation, and user engagement.**Core Values:**1. Excellence and Exploration2. T.I.E (Trust, Integrity, and Empathy)3. Continuous Learning and Sharing4. Fun-filled culture with work-life balance5. Ownership with Responsible Freedom**Communication Channels:**1. Phone: +91 81784 97981 (India) | +31 616884242 (Netherlands)2. Email: sales@xcelore.com, inbound@xcelore.com3. WhatsApp: +91 81784 979814. Social Media: LinkedIn, Twitter, Facebook, Instagram**Services:**1. Generative AI Solutions2. AI-Led Product Development3. Conversational AI & Chatbots4. ML Ops5. Digital Product Engineering6. Product Discovery & Design7. Web & Mobile App Development8. Microservices Development9. Cloud and DevOps Services10. Kotlin Development (Multiplatform, Server-side, Android, and Migration)11. Cloud & DevOps as a Service12. Cloud Managed Services13. Audits, Assessments & Consulting14. Cloud Migration & Modernization**AI-Powered Key Products:**1. **Exei – Virtual Assistant:** 24/7 AI-driven support for enhanced customer engagement and operational efficiency.2. **Xcelight – Business Intelligence:** Transforms CCTV systems into powerful business insight tools for efficiency and decision-making.3. **Translore – Real-Time Audio Translation:** Instant, accurate translations for seamless global communication.**Unique Initiatives:**1. Generative AI R&D and PoC Lab2. Offshore Development Teams3. Kotlin Multiplatform & Kotlin Server-side Development**Experience & Success:**- 40+ years of cumulative leadership experience- 100+ team members- 75+ global clients across 10+ industries- 200+ successful projects**Growth Partner Network:**Xcelore invites businesses to join its Growth Partner network, fostering collaborative success in business growth and digital transformation.**Terms of Service & Privacy Policy:**Xcelore's Terms of Service and Privacy Policy can be found on their website, outlining service conditions and data protection measures.At Xcelore, AI meets digital innovation, delivering intelligent solutions for businesses seeking performance enhancements, cost reductions, and superior user experiences. We don’t just develop digital solutions—we create future-ready intelligent experiences that keep businesses ahead of the curve", "xcelore"))
            except json.JSONDecodeError as e:
                print("Failed to decode JSON:", e)
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Transcription connection closed: code={e.code}, reason={e.reason}")
    except Exception as e:
        print(f"Error in receive_responses: {e}")


async def transcription_handler(websocket, path=None):
    """
    Handles incoming audio data from the browser.
    Audio chunks are accumulated (for optional saving) and forwarded via an async queue.
    """
    global pcm_data
    print("Transcription client connected.")
    try:
        async for message in websocket:
            # Accumulate raw PCM audio (for optional saving)
            pcm_data.extend(message)
            # Forward the audio chunk to NeuralSpace via the async queue.
            await q.put(message)
    except websockets.exceptions.ConnectionClosed:
        print("Transcription client disconnected.")
    except Exception as e:
        print(f"Error in transcription_handler: {e}")


async def tts_handler(websocket, path=None):
    """
    When a TTS client connects, this handler continuously waits for new model API chunks
    from the global model_queue. Each chunk is passed to the TTS synthesis engine
    (NeuralSpace TTS), and the resulting audio is streamed back to the client.
    """
    print("TTS client connected.")
    try:
        while True:
            # Wait for a new text chunk from the model API
            chunk_text = await model_queue.get()
            print(f"Processing TTS for chunk: {chunk_text}")
            data = {
                "text": chunk_text,
                "speaker_id": "ar-male-Omar-saudi-neutral",
                "stream": True,  # Request raw byte streaming.
                "sample_rate": 16000,
                "config": {
                    "pace": 0.75,
                    "volume": 1.0,
                    "pitch_shift": 0,
                    "pitch_scale": 1.0
                }
            }
            try:
                loop = asyncio.get_event_loop()
                # Run the TTS synthesis in an executor since it is synchronous.
                result = await loop.run_in_executor(None, vai.synthesize, data)
                # Send the synthesized TTS audio chunk to the client.
                await websocket.send(result)
                print(f"Sent TTS audio chunk for text: {chunk_text}")
            except Exception as e:
                print(f"TTS synthesis error: {e}")
    except websockets.exceptions.ConnectionClosed:
        print("TTS client disconnected.")
    except Exception as e:
        print(f"Error in tts_handler: {e}")


#############################################################################################################
# MAIN FUNCTION TO START WEBSOCKET SERVERS & PROCESSING
#############################################################################################################
async def main():
    """
    Main function that:
      - Connects to NeuralSpace transcription WebSocket.
      - Starts the transcription WebSocket server (receiving audio from the browser).
      - Starts the TTS WebSocket server (streaming TTS audio back to the browser).
      - Launches tasks to process audio and transcription responses.
    """
    try:
        async with websockets.connect(NS_WEBSOCKET_URL) as ns_ws:
            print("Connected to NeuralSpace transcription WebSocket.")
            # Start a WebSocket server for receiving audio (transcription).
            transcription_server = await websockets.serve(transcription_handler, "localhost", 8000)
            print("Transcription WebSocket server started at ws://localhost:8000/stream")
            # Start a WebSocket server for TTS output.
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
        # Optionally, save the accumulated raw PCM audio to an MP3 file.
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

