import neuralspace as ns

vai = ns.VoiceAI(api_key="sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829")
# print(vai.)
# or,
# vai = ns.VoiceAI(api_key='YOUR_API_KEY')

# Fetch TTS voices
ls = vai.voices()

for x in ls:
    for k,v in x.items():
        if k == 'language' and v == 'ar':
            print(x['name'])




# curl --location 'https://voice.neuralspace.ai/api/v2/tts' \
# --header "Authorization: sk_fb0b6af94e89fe36afc3a0913b766f0794b28681c1b96716220f5fe395450829" \
# --header 'Content-Type: application/json' \
# --data '{
#     "stream": "True",
#     "text": "مرحبا بالعالم",
#     "speaker_id": "ar-male-Omar-saudi-neutral"
# }' \
# --output -
