import asyncio
import neuralspace as ns
import json
import websockets
import uuid
import httpx
import requests
import re


API_KEY = "sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829"
# Connect to NEURALSPACE VoiceAI
vai = ns.VoiceAI(api_key=API_KEY)

# NEURALSPACE Configuration
BASE = "https://voice.neuralspace.ai/api/v2/languages?type=stream"
headers = {"Authorization": API_KEY}
language = "en"
min_chunk_size = 2
vad_threshold = 0.5
disable_partial = "True"
audio_format = "pcm_16k"
DURATION = 600


# Get transcription token from NeuralSpace (Valid for 10 minutes (600 seconds))

TOKEN_URL = f"https://voice.neuralspace.ai/api/v2/token?duration={DURATION}"
response = requests.get(TOKEN_URL, headers=headers)
TOKEN = response.json().get("data", {}).get("token")
if not TOKEN:
    raise ValueError("Failed to retrieve API token.")


# Generate Session ID for each transcription session
session_id = str(uuid.uuid4())

try:
    NS_WEBSOCKET_URL = (
        f"wss://voice.neuralspace.ai/voice/stream/live/transcribe/{language}/{TOKEN}/{session_id}"
        f"?max_chunk_size={min_chunk_size}&vad_threshold={vad_threshold}"
        f"&disable_partial={disable_partial}&format={audio_format}"
    )
except Exception as e:
    print(e)

# Queue for storing audio chunks from browser
chunk_store_queue = asyncio.Queue()
# Queue for storing text chunks from Exei Voice API call
response_store_queue = asyncio.Queue()



# Call the Exei API with the stored text chunks in the queue
async def call_exei_api(session_id: str, user_input: str, persona: str, domain_name: str):
    url = "https://qa-chat.exei.ai/stream_voice"
    payload = {
        "session_id": session_id,
        "user_input": user_input,
        "persona": persona,
        "domain_name": domain_name
    }
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST",url,json=payload) as response:
                 pattern = r"'chunk':\s*'([^']*)'"
                 async for line in response.aiter_lines():
                     line = line.strip()
                     if not line:
                            continue

                     match = re.search(pattern,line)
                     if match:
                         chunk_text = match.group(1)
                         print(chunk_text)
                         await response_store_queue.put(chunk_text)
                     else:
                         continue
    except Exception as e:
        print(e)


async def process_audio(ws):
    """ Getting audio chunks from the queue (chunk_store_queue) ans pass it to
        NeuralSpace Voice AI to get transcriptions of the audio chunks
        ws -- > websocket
    """
    try:
        while True:
            data = await chunk_store_queue.get()
            await ws.send(data)
    except asyncio.CancelledError:
        print('Audio Processing Task cancelled')
    except Exception as e:
        print("Error in Transcription: ",e)


async def receive_response(ws):
    """
        Receives transcription responses from NeuralSpace.
        For each transcription received, it launches a task to call the Exei API.
    """
    global session_id
    try:
        async for message in ws:
            try:
                response_data = json.loads(message)
                msg = response_data['text']
                print(msg)
                # asyncio.create_task(call_voice_api(session_id,msg,persona,domain_name))
                asyncio.create_task(call_exei_api(session_id, msg, "**Company Overview:**Xcelore is a fast-growing, AI-driven innovation hub that builds and enhances digital products and platforms for a modern world. With bases in Noida and the Netherlands, Xcelore specializes in high-impact digital product engineering, cloud solutions, and AI-driven innovations for startups and enterprises across diverse industries. Their mission is to help businesses excel in the digital realm while pushing the boundaries of technological advancement and innovation.**Industry:**Xcelore operates in the Digital Technology Services & Product Engineering space, with expertise in:1. Generative AI R&D and PoC Lab2. AI-Led Product Development3. Digital Product Engineering4. Kotlin Multiplatform & Kotlin Server-side Development5. Offshore Development Teams**Unique Aspects:**1. Design-First, Cloud-Native, Agile & Fullstack approach2. Commitment to providing value with transparency, empathy & complete ownership3. Emphasis on AI-driven innovation and cutting-edge technology4. Focus on delivering intelligent, future-ready digital experiences**Driving Force:**Xcelore aims to disrupt the Digital Technology Services & Product Engineering space by integrating AI and next-gen technology into its solutions, enhancing efficiency, automation, and user engagement.**Core Values:**1. Excellence and Exploration2. T.I.E (Trust, Integrity, and Empathy)3. Continuous Learning and Sharing4. Fun-filled culture with work-life balance5. Ownership with Responsible Freedom**Communication Channels:**1. Phone: +91 81784 97981 (India) | +31 616884242 (Netherlands)2. Email: sales@xcelore.com, inbound@xcelore.com3. WhatsApp: +91 81784 979814. Social Media: LinkedIn, Twitter, Facebook, Instagram**Services:**1. Generative AI Solutions2. AI-Led Product Development3. Conversational AI & Chatbots4. ML Ops5. Digital Product Engineering6. Product Discovery & Design7. Web & Mobile App Development8. Microservices Development9. Cloud and DevOps Services10. Kotlin Development (Multiplatform, Server-side, Android, and Migration)11. Cloud & DevOps as a Service12. Cloud Managed Services13. Audits, Assessments & Consulting14. Cloud Migration & Modernization**AI-Powered Key Products:**1. **Exei – Virtual Assistant:** 24/7 AI-driven support for enhanced customer engagement and operational efficiency.2. **Xcelight – Business Intelligence:** Transforms CCTV systems into powerful business insight tools for efficiency and decision-making.3. **Translore – Real-Time Audio Translation:** Instant, accurate translations for seamless global communication.**Unique Initiatives:**1. Generative AI R&D and PoC Lab2. Offshore Development Teams3. Kotlin Multiplatform & Kotlin Server-side Development**Experience & Success:**- 40+ years of cumulative leadership experience- 100+ team members- 75+ global clients across 10+ industries- 200+ successful projects**Growth Partner Network:**Xcelore invites businesses to join its Growth Partner network, fostering collaborative success in business growth and digital transformation.**Terms of Service & Privacy Policy:**Xcelore's Terms of Service and Privacy Policy can be found on their website, outlining service conditions and data protection measures.At Xcelore, AI meets digital innovation, delivering intelligent solutions for businesses seeking performance enhancements, cost reductions, and superior user experiences. We don’t just develop digital solutions—we create future-ready intelligent experiences that keep businesses ahead of the curve.", "xcelore"))
            except json.JSONDecodeError as e:
                print('failed to decode JSON',e)

    except websockets.ConnectionClosed as e:
        print("Connection Closed")

    except Exception as e:
        print(e)

async def transcription_handler(websocket,path = None):
    """
        Handles incoming audio data from the browser.
        Stores the audio chunks in (chunk_store_queue)
    """
    try:
        async for message in websocket:
            await chunk_store_queue.put(message)
    except websockets.exceptions.ConnectionClosed:
        print('Connection Closed...currently Not receiving audio from browser')
    except Exception as e:
        print(e)


async def text_to_speech(websocket,path = None):
    try:
        while True:
            chunk_text = await response_store_queue.get()
            data = {
                "text": chunk_text,
                "speaker_id": "en-male-Oscar-english-neutral",
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
                result = await loop.run_in_executor(None,vai.synthesize,data)
                await websocket.send(result)
            except Exception as e:
                print(e)
    except websockets.exceptions.ConnectionClosed:
                print('Text to speech connection closed')
    except Exception as e:
                print(e)


async def main():
    """
    1) Connect to NeuralSpace Transcription Webscoket
    2) Take the audio chunks from browser (Establish Websocket)
    3) Start Text to Speech Websocket

    """
    try:
        async with websockets.connect(NS_WEBSOCKET_URL) as ns_ws:
            transcription_server = await websockets.serve(transcription_handler, "0.0.0.0", 8000 )
            print("Transcription WebSocket server started at ws://localhost:8000/stream")
            tts_server = await websockets.serve(text_to_speech,"0.0.0.0",8001)
            print("TTS WebSocket server started at ws://localhost:8001/tts")
            await asyncio.gather(
                process_audio(ns_ws),
                receive_response(ns_ws),
                transcription_server.wait_closed(),
                tts_server.wait_closed()
            )

    except Exception as e:
        print(e)


if __name__ == "__main__":
    asyncio.run(main())








