"""
voice_input.py — Command transcription for Maez via faster-whisper
OBSBOT Meet 2 at hw:1,0, 32000Hz stereo. Resamples to 16kHz mono for Whisper.
"""

import logging
import time
from math import gcd
from typing import Optional

import numpy as np
from scipy.signal import resample_poly

logger = logging.getLogger("maez")

HARDWARE_RATE = 32000
HARDWARE_CHANNELS = 2
MODEL_RATE = 16000
CHUNK_SIZE = 2048
SILENCE_THRESHOLD = 0.015
SILENCE_DURATION = 1.5
MAX_RECORD_SECONDS = 20

_RESAMPLE_GCD = gcd(MODEL_RATE, HARDWARE_RATE)
_RESAMPLE_UP = MODEL_RATE // _RESAMPLE_GCD
_RESAMPLE_DOWN = HARDWARE_RATE // _RESAMPLE_GCD


class VoiceTranscriber:
    def __init__(self, mic_device_index: Optional[int] = None):
        self.mic_device_index = mic_device_index
        self._model = None
        self._initialized = False

    def initialize(self) -> bool:
        try:
            from faster_whisper import WhisperModel
            logger.info("Loading Whisper base.en (CPU)...")
            self._model = WhisperModel("base.en", device="cpu", compute_type="int8",
                                        download_root="/home/rohit/maez/models/whisper")
            self._initialized = True
            logger.info("Whisper ready (CPU)")
            return True
        except Exception as e:
            logger.error("Whisper init failed: %s", e)
            return False

    def listen_and_transcribe(self) -> Optional[str]:
        if not self._initialized:
            return None
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            device_index = self.mic_device_index if self.mic_device_index is not None else self._find_mic(pa)

            stream = pa.open(
                rate=HARDWARE_RATE,
                channels=HARDWARE_CHANNELS,
                format=pyaudio.paInt16,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=CHUNK_SIZE,
            )

            logger.debug("Recording command (hw rate=%d, %dch)...", HARDWARE_RATE, HARDWARE_CHANNELS)
            frames = []
            silence_start = None
            start_time = time.time()

            while True:
                chunk = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                audio_int = np.frombuffer(chunk, dtype=np.int16)

                # Stereo to mono
                if HARDWARE_CHANNELS == 2:
                    audio_int = audio_int.reshape(-1, 2).mean(axis=1).astype(np.int16)

                # Convert to float32 normalized
                audio_chunk = audio_int.astype(np.float32) / 32768.0
                frames.append(audio_chunk)
                rms = np.sqrt(np.mean(audio_chunk ** 2))

                if rms > SILENCE_THRESHOLD:
                    silence_start = None
                else:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start > SILENCE_DURATION:
                        break
                if time.time() - start_time > MAX_RECORD_SECONDS:
                    break

            stream.stop_stream()
            stream.close()
            pa.terminate()

            if not frames:
                return None
            audio = np.concatenate(frames)

            if len(audio) < HARDWARE_RATE * 0.3:
                return None

            # Resample 32kHz → 16kHz for Whisper
            audio = resample_poly(audio, _RESAMPLE_UP, _RESAMPLE_DOWN).astype(np.float32)

            logger.debug("Transcribing %.1fs of audio...", len(audio) / MODEL_RATE)
            segments, _ = self._model.transcribe(audio, language="en",
                                                  beam_size=1, vad_filter=True)
            text = ' '.join(seg.text.strip() for seg in segments).strip()
            if text:
                logger.info("Transcribed: '%s'", text)
            return text if text else None
        except Exception as e:
            logger.error("Transcription error: %s", e)
            return None

    def _find_mic(self, pa) -> int:
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            name = info['name']
            if info['maxInputChannels'] > 0 and ('O2' in name or 'OBSBOT' in name or 'hw:1,0' in name):
                logger.info("OBSBOT at [%d]: %s", i, name)
                return i
        for i in range(pa.get_device_count()):
            if pa.get_device_info_by_index(i)['maxInputChannels'] > 0:
                return i
        return 0


_transcriber: Optional[VoiceTranscriber] = None


def initialize(mic_device_index: Optional[int] = None) -> bool:
    logger.info("voice_input: unified pipeline in wake_word.py owns the mic. This module is a no-op.")
    return True


def listen_and_transcribe() -> Optional[str]:
    logger.warning("listen_and_transcribe called directly — use unified pipeline in wake_word.py instead")
    return None


def test():
    print("Voice input test — speak after prompt")
    if not initialize():
        print("FAILED")
        return False
    print("Speak a test command now...\n")
    text = listen_and_transcribe()
    if text:
        print(f"\nSUCCESS: '{text}'")
    else:
        print("\nNo speech detected")
    return text is not None


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    test()
