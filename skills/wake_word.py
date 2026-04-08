"""
wake_word.py — Wake word detection + transcription for Maez

Pipeline:
  pw-record (fifine mic, PipeWire) → 16kHz mono int16
  → energy VAD (RMS threshold) → accumulate 2s buffer
  → MFCC feature extraction → Hey Maez verifier v3
  → faster-whisper small.en → transcription
  → callback(text)

The verifier is a pure MFCC classifier trained on fifine audio.
No dependency on openwakeword hey_mycroft scores.
"""

import logging
import os
import subprocess
import threading
import time
from collections import deque
from typing import Callable, Optional

import joblib
import numpy as np

os.environ.setdefault('PIPEWIRE_RUNTIME_DIR', '/run/user/1000')
os.environ.setdefault('XDG_RUNTIME_DIR', '/run/user/1000')

logger = logging.getLogger("maez")

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_MS = 80
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)  # 1280

VERIFIER_PATH = "/home/rohit/maez/models/wakeword/hey_maez_verifier.pkl"
FIFINE_NODE = 'alsa_input.usb-3142_fifine_Microphone-00.analog-stereo'

ENERGY_THRESHOLD = 0.02       # RMS above this = voice activity
VERIFIER_CONFIDENCE = 0.4     # single trigger threshold — needs 2 in 3s to confirm
COOLDOWN_SECONDS = 2.0
VERIFIER_BUFFER_SECONDS = 1   # 1 second — "Hey Maez" is ~0.6s
CONFIRM_WINDOW = 3.0          # seconds — need 2 triggers in this window
CONFIRM_COUNT = 2             # triggers needed to confirm

SILENCE_THRESHOLD = 0.003     # matches actual fifine signal level
SILENCE_DURATION = 2.0        # wait 2 seconds of silence before stopping
MIN_RECORD_SECONDS = 2.0     # record at least 2s — commands need time
MAX_RECORD_SECONDS = 15
PRE_ROLL_CHUNKS = 2

_HALLUCINATIONS = {
    "", ".", ",", "!", "?",   # only filter empty/punctuation
}

_is_speaking = False
_speaking_lock = threading.Lock()
_post_speech_cooldown = 0.0  # timestamp until which transcriptions are ignored


def _strip_wake_word(text: str) -> str:
    """Remove wake word prefix from transcription."""
    import re as _re
    return _re.sub(r'^(hey\s+ma[ez][ez][^\s]*\s*,?\s*)', '', text, flags=_re.IGNORECASE).strip()


def extract_verifier_features(audio: np.ndarray, sr: int = 16000) -> np.ndarray:
    """Extract MFCC features for the Hey Maez verifier v3."""
    import librosa

    if audio.dtype != np.float32:
        audio = audio.astype(np.float32) / 32768.0
    audio = np.clip(audio * 4, -1.0, 1.0)

    # Pad or trim to 2 seconds (verifier trained on 2s windows)
    target = sr * 2
    if len(audio) < target:
        audio = np.pad(audio, (0, target - len(audio)))
    else:
        audio = audio[:target]

    mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=20)
    mfcc_mean = np.mean(mfcc, axis=1)
    mfcc_std = np.std(mfcc, axis=1)
    delta = librosa.feature.delta(mfcc)
    delta_mean = np.mean(delta, axis=1)
    delta2 = librosa.feature.delta(mfcc, order=2)
    delta2_mean = np.mean(delta2, axis=1)
    spec_centroid = np.mean(librosa.feature.spectral_centroid(y=audio, sr=sr))
    spec_rolloff = np.mean(librosa.feature.spectral_rolloff(y=audio, sr=sr))
    spec_bandwidth = np.mean(librosa.feature.spectral_bandwidth(y=audio, sr=sr))
    zcr = np.mean(librosa.feature.zero_crossing_rate(audio))
    rms_feat = np.mean(librosa.feature.rms(y=audio))
    chroma = np.mean(librosa.feature.chroma_stft(y=audio, sr=sr), axis=1)

    return np.concatenate([
        mfcc_mean, mfcc_std, delta_mean, delta2_mean,
        [spec_centroid, spec_rolloff, spec_bandwidth, zcr, rms_feat],
        chroma,
    ])


def _load_verifier():
    """Load Hey Maez verifier v3 (MFCC classifier)."""
    if not os.path.exists(VERIFIER_PATH):
        logger.warning("Verifier not found at %s", VERIFIER_PATH)
        return None
    try:
        data = joblib.load(VERIFIER_PATH)
        if isinstance(data, dict):
            model = data['model']
            version = data.get('version', '?')
            logger.info("Hey Maez verifier v%s loaded (MFCC classifier)", version)
        else:
            model = data
            logger.info("Hey Maez verifier loaded (legacy format)")
        return model
    except Exception as e:
        logger.error("Verifier load failed: %s", e)
        return None


def _load_whisper():
    from faster_whisper import WhisperModel
    try:
        model = WhisperModel(
            "small.en", device="cuda", compute_type="float16",
            download_root="/home/rohit/maez/models/whisper",
        )
        logger.info("Whisper small.en loaded (GPU/CUDA)")
    except Exception as e:
        logger.warning("Whisper GPU failed (%s), falling back to CPU", e)
        model = WhisperModel(
            "small.en", device="cpu", compute_type="int8",
            download_root="/home/rohit/maez/models/whisper",
        )
        logger.info("Whisper small.en loaded (CPU fallback)")
    return model


def _transcribe(whisper, audio: np.ndarray) -> Optional[str]:
    if len(audio) < SAMPLE_RATE * 0.5:
        return None

    # Energy gate — skip Whisper if audio is too quiet to be speech
    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms < 0.01:
        logger.debug("[AUDIO] Energy too low for speech (RMS=%.4f), skipping Whisper", rms)
        return None

    segments, info = whisper.transcribe(
        audio, language="en", beam_size=1, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
    )
    seg_list = list(segments)

    # Check no_speech_prob on first segment
    if seg_list and getattr(seg_list[0], 'no_speech_prob', 0) > 0.6:
        logger.debug("[AUDIO] Whisper detected no speech (prob=%.2f), suppressed",
                     seg_list[0].no_speech_prob)
        return None

    text = " ".join(s.text.strip() for s in seg_list).strip()
    if text.lower().strip(".,!? ") in _HALLUCINATIONS:
        logger.debug("Filtered hallucination: '%s'", text)
        return None
    return text if text else None


def _audio_loop(callback: Callable[[str], None], stop_event: threading.Event):
    logger.info("[AUDIO] _audio_loop thread started")
    try:
        _audio_loop_inner(callback, stop_event)
    except Exception as e:
        logger.error("[AUDIO] FATAL: audio loop crashed: %s", e, exc_info=True)


def _audio_loop_inner(callback: Callable[[str], None], stop_event: threading.Event):
    # Load verifier
    verifier = _load_verifier()
    if verifier is None:
        logger.error("No verifier — wake word detection disabled")
        return

    # Load whisper
    try:
        whisper = _load_whisper()
    except Exception as e:
        logger.error("Whisper load failed: %s", e)
        return

    logger.info("Audio loop starting — fifine via PipeWire, %dHz mono", SAMPLE_RATE)

    # Start pw-record
    cmd = [
        'pw-record', '--rate=16000', '--channels=1',
        '--media-type=Audio', '--media-category=Capture',
        '--latency=80ms', f'--target={FIFINE_NODE}', '-',
    ]
    env = {
        **os.environ,
        'PIPEWIRE_RUNTIME_DIR': '/run/user/1000',
        'XDG_RUNTIME_DIR': '/run/user/1000',
    }
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)

    # Audio queue
    audio_queue = []
    queue_lock = threading.Lock()
    chunk_bytes = CHUNK_SAMPLES * 2  # int16 = 2 bytes per sample

    def _reader():
        proc.stdout.read(44)  # skip WAV header
        logger.info("pw-record stream active (fifine)")
        while not stop_event.is_set():
            data = proc.stdout.read(chunk_bytes)
            if not data:
                break
            raw = np.frombuffer(data, dtype=np.int16)
            if len(raw) == 0:
                continue
            with queue_lock:
                audio_queue.append((raw, raw.astype(np.float32) / 32768.0))

    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()
    logger.info("Fifine mic stream open via pw-record")

    # State
    state = "listening"
    pre_roll = deque(maxlen=PRE_ROLL_CHUNKS)
    record_buffer = []
    silence_start = None
    record_start = None

    # Sliding window verifier
    WINDOW_SIZE = 16000       # 1 second window
    SLIDE_STEP = 8000         # slide every 0.5 seconds (50% overlap)
    TRIGGER_COOLDOWN = 3.0

    ring_buffer = np.zeros(SAMPLE_RATE * 5, dtype=np.int16)  # 5 seconds of history
    samples_since_slide = 0
    last_trigger_time = 0.0

    try:
        while not stop_event.is_set():
            with queue_lock:
                if not audio_queue:
                    time.sleep(0.01)
                    continue
                int16_chunk, float_chunk = audio_queue.pop(0)

            if state == "listening":
                pre_roll.append(float_chunk)

                with _speaking_lock:
                    if _is_speaking:
                        continue

                # Always feed into ring buffer
                n = len(int16_chunk)
                ring_buffer = np.roll(ring_buffer, -n)
                ring_buffer[-n:] = int16_chunk
                samples_since_slide += n

                # Every SLIDE_STEP samples, check energy and run verifier
                if samples_since_slide >= SLIDE_STEP:
                    samples_since_slide = 0

                    # Extract current 1-second window
                    window = ring_buffer[-WINDOW_SIZE:]
                    window_float = window.astype(np.float32) / 32768.0
                    window_float = np.clip(window_float * 4, -1.0, 1.0)
                    rms = float(np.sqrt(np.mean(window_float ** 2)))

                    if rms > ENERGY_THRESHOLD:
                        try:
                            features = extract_verifier_features(window)
                            prob = verifier.predict_proba([features])[0][1]
                            now = time.time()

                            if prob > VERIFIER_CONFIDENCE and (now - last_trigger_time) > TRIGGER_COOLDOWN:
                                last_trigger_time = now
                                logger.info("[AUDIO] Hey Maez CONFIRMED (confidence=%.3f)", prob)
                                state = "recording"
                                # No seed — command follows wake word, seed only pollutes
                                record_buffer = []
                                record_start = time.time()
                                silence_start = None
                                logger.info("[AUDIO] Recording started — ring buffer seeded with %d samples (%.1fs)",
                                            len(ring_float), len(ring_float) / SAMPLE_RATE)
                                continue
                            elif prob > 0.1:
                                logger.info("[AUDIO] confidence=%.3f rms=%.4f", prob, rms)
                        except Exception as e:
                            logger.info("[AUDIO] Verifier error: %s", e)

            elif state == "recording":
                record_buffer.append(float_chunk)
                rms = float(np.sqrt(np.mean(float_chunk ** 2)))
                now = time.time()
                elapsed = now - record_start

                # Grace period — don't start silence timer in first 0.5s
                if elapsed < 0.5:
                    silence_start = None
                    continue

                if rms > SILENCE_THRESHOLD:
                    silence_start = None
                elif silence_start is None:
                    silence_start = now
                elif (now - silence_start >= SILENCE_DURATION
                      and elapsed >= MIN_RECORD_SECONDS):
                    audio = np.concatenate(record_buffer)
                    total_samples = len(audio)
                    logger.info("[AUDIO] Recording stopped — %d samples, %.2fs",
                                total_samples, total_samples / 16000)
                    record_buffer = []
                    state = "listening"

                    def _do_transcribe(a=audio):
                        # Post-speech cooldown check
                        if time.time() < _post_speech_cooldown:
                            logger.info("[AUDIO] Ignoring transcription during post-speech cooldown")
                            return

                        dur = len(a) / 16000
                        a_rms = float(np.sqrt(np.mean(a ** 2)))
                        if a_rms > 0.001:
                            gain = 0.3 / a_rms
                            a = np.clip(a * gain, -1.0, 1.0)
                        a_rms_post = float(np.sqrt(np.mean(a ** 2)))
                        logger.info("[AUDIO] Transcribing %.2fs audio, rms=%.4f→%.4f (gain applied)",
                                    dur, a_rms, a_rms_post)
                        try:
                            text = _transcribe(whisper, a)
                            logger.info("[AUDIO] Whisper returned: '%s'", text)
                            if text:
                                text = _strip_wake_word(text)
                                if text:
                                    logger.info('Transcribed: "%s"', text)
                                    try:
                                        callback(text)
                                    except Exception as e:
                                        logger.error("Callback error: %s", e)
                                else:
                                    logger.info("[AUDIO] Only wake word detected, no command")
                            else:
                                logger.info("[AUDIO] No speech detected in audio")
                        except Exception as e:
                            logger.error("[AUDIO] Transcription error: %s", e, exc_info=True)

                    threading.Thread(target=_do_transcribe, daemon=True,
                                     name="maez-transcribe").start()
                    continue

                if now - record_start >= MAX_RECORD_SECONDS:
                    audio = np.concatenate(record_buffer)
                    logger.info("[AUDIO] Max recording reached — %d samples, %.2fs",
                                len(audio), len(audio) / 16000)
                    record_buffer = []
                    state = "listening"

                    def _do_max(a=audio):
                        if time.time() < _post_speech_cooldown:
                            logger.info("[AUDIO] Ignoring transcription during post-speech cooldown")
                            return

                        dur = len(a) / 16000
                        a_rms = float(np.sqrt(np.mean(a ** 2)))
                        if a_rms > 0.001:
                            gain = 0.3 / a_rms
                            a = np.clip(a * gain, -1.0, 1.0)
                        a_rms_post = float(np.sqrt(np.mean(a ** 2)))
                        logger.info("[AUDIO] Transcribing %.2fs audio (max), rms=%.4f→%.4f",
                                    dur, a_rms, a_rms_post)
                        try:
                            text = _transcribe(whisper, a)
                            logger.info("[AUDIO] Whisper returned: '%s'", text)
                            if text:
                                text = _strip_wake_word(text)
                                if text:
                                    logger.info('Transcribed: "%s"', text)
                                    try:
                                        callback(text)
                                    except Exception as e:
                                        logger.error("Callback error: %s", e)
                        except Exception as e:
                            logger.error("[AUDIO] Transcription error: %s", e, exc_info=True)

                    threading.Thread(target=_do_max, daemon=True,
                                     name="maez-transcribe-max").start()

    except Exception as e:
        logger.error("Audio loop error: %s", e)
    finally:
        proc.terminate()

    logger.info("Audio loop stopped")


_thread: Optional[threading.Thread] = None
_stop_event: Optional[threading.Event] = None


def start(callback: Callable[[str], None]) -> bool:
    global _thread, _stop_event
    _stop_event = threading.Event()
    _thread = threading.Thread(
        target=_audio_loop, args=(callback, _stop_event),
        daemon=True, name="maez-audio-loop",
    )
    _thread.start()
    logger.info("Wake word listener started — say 'Hey Maez'")
    return True


def stop():
    global _thread, _stop_event
    if _stop_event:
        _stop_event.set()
    if _thread:
        _thread.join(timeout=5)
    _thread = None
    _stop_event = None
    logger.info("Wake word listener stopped")


def set_speaking(speaking: bool):
    global _is_speaking, _post_speech_cooldown
    with _speaking_lock:
        _is_speaking = speaking
        if not speaking:
            # 1.5s cooldown after speech ends — ignore reverb
            _post_speech_cooldown = time.time() + 1.5
            logger.debug("[AUDIO] MUTE released, cooldown until %.1f", _post_speech_cooldown)


def test():
    logging.basicConfig(level=logging.INFO)
    results = []

    def on_command(text):
        print(f'\n  COMMAND: "{text}"')
        results.append(text)

    print("Say 'Hey Maez' followed by a command")
    print("Listening for 60 seconds...\n")
    start(on_command)
    try:
        time.sleep(60)
    except KeyboardInterrupt:
        pass
    finally:
        stop()
    print(f"\nCommands: {results}")


if __name__ == "__main__":
    test()
