import neuralspace as ns



vai = ns.VoiceAI(api_key='sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829')

data = {
    "text": "كيف حالك",
    "speaker_id": "ar-female-Mira-saudi-neutral",
    "stream": True,  # or True if you want raw bytes
    "sample_rate": 16000,
    "config": {
        "pace": 1.0,
        "volume": 1.0,
        "pitch_shift": 0,
        "pitch_scale": 1.0
    }
}

# Generate audio from the provided text
try:
    result = vai.synthesize(data=data)
    # print(f'Output:\n{result}')
    # with open("output.mp3", "wb") as f:
    #     f.write(result)

    print(type(result))
    print(f"Result: {result}")
    # print("audio saved")
except ValueError as e:
    print(f'Error: {e}')
