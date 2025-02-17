from denoiser import pretrained
from df.enhance import enhance
from df.enhance import init_df
import torch
import torchaudio
import io
import numpy as np

denoised_model = pretrained.dns64().cuda()
vad_model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', trust_repo=True)
(get_speech_ts, _, _, _, _) = utils  # Get the function for detecting speech timestamps

# Initialize DeepFilterNet model for enhancement
df_model, df_state, _ = init_df()


def audio_processing(audio_blob,user_id,samplerate):
    results = []

    with torch.no_grad():
        waveform, sr = torchaudio.load(io.BytesIO(audio_blob))

        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        resampled_wav = torchaudio.functional.resample(waveform, sr, 16000)

        # # Append the last segment of the previous waveform for this user to the current one
        # if user_id in selfuser_segments and self.user_segments[user_id] is not None:
        #     resampled_wav = torch.cat((self.user_segments[user_id], resampled_wav), dim=1)

        # Enhance and process waveform
        audio_tensor = resampled_wav.clone().detach()
        waveform = enhance(audio=audio_tensor, model=df_model, df_state=df_state, atten_lim_db=10, pad=True)
        waveform = waveform.squeeze().cpu().numpy()

        # Voice activity detection
        speech_timestamps = get_speech_ts(waveform, vad_model, sampling_rate=16000)

        # Save the last segment for the next chunk for this user (e.g., last 150ms of data)
        # overlap_duration = 0.1  # 150 ms
        # num_samples_overlap = int(16000 * overlap_duration)
        # self.user_segments[user_id] = resampled_wav[:, -num_samples_overlap:]

    if speech_timestamps:
        enhanced_segments = []
        for i, ts in enumerate(speech_timestamps):
            speech_segment = waveform[ts['start']:ts['end']]
            speech_tensor = torch.from_numpy(speech_segment).float()

            if samplerate != df_state.sr():
                with torch.no_grad():  # no_grad for resampling
                    speech_tensor = torchaudio.functional.resample(speech_tensor, orig_freq=samplerate,
                                                                   new_freq=df_state.sr())

            # Optional: Enhance the speech using DeepFilterNet
            # with torch.no_grad():
            #     enhanced_tensor = enhance(df_model, df_state, speech_tensor.unsqueeze(0), pad=False, atten_lim_db=30)

            enhanced_audio = torchaudio.functional.resample(speech_tensor.squeeze(), orig_freq=df_state.sr(),
                                                            new_freq=samplerate)
            enhanced_segments.append(enhanced_audio)

        input_audio = torch.cat(enhanced_segments)
        audio_array = input_audio.data.cpu().numpy().flatten()
        rms = np.sqrt(np.mean(audio_array ** 2))

    #     if rms > 0.018:
    #         try:
    #             # Temporary file handling
    #             unique_prefix = f"audio_{uuid.uuid4()}_"
    #             with tempfile.NamedTemporaryFile(prefix=unique_prefix, suffix=".wav", delete=True) as temp_wav_file:
    #                 # Save the audio tensor to the temporary WAV file
    #                 torchaudio.save(temp_wav_file.name, input_audio.unsqueeze(0), sample_rate=16000)
    #
    #
    #
    #         finally:
    #             temp_wav_file.close()
    #
    #         if room not in user_history:
    #             user_history[room] = {}
    #
    #         if user_id not in user_history[room]:
    #             user_history[room][user_id] = {}
    #
    #         # Parallelize language processing
    #         with concurrent.futures.ThreadPoolExecutor() as executor:
    #             future_1 = executor.submit(self.process_language, target_language_1, transcription, user_id,
    #                                        source_language, user_history, client, room)
    #             future_2 = executor.submit(self.process_language, target_language_2, transcription, user_id,
    #                                        source_language, user_history, client, room)
    #
    #             # Collect the results from both languages
    #             results.append(future_1.result())
    #             results.append(future_2.result())
    #
    #         # Save processed audio
    #         with io.BytesIO() as output_f:
    #             sf.write(output_f, audio_array, samplerate=16000, format='wav')
    #             processed_data_3 = output_f.getvalue()
    #
    #         # Determine the input language name
    #         input_language = {'hi': 'Hindi', 'en': 'English', 'ar': 'Arabic'}.get(source_language, 'Unknown')
    #
    #         results.append([{
    #             'language_name': input_language,
    #             'captions': transcription,
    #             'audio_result': processed_data_3,
    #             'self_text': transcription,
    #         }])
    #         del audio_tensor, speech_tensor, input_audio
    #
    #
    # else:
    #     print('No vocals detected')
    #     del audio_tensor

    return results

