"""
voice_output.py — Streaming voice output for Maez via RealtimeTTS + Kokoro.

Key difference from old approach:
- OLD: generate full audio → write wav → play entire clip → done
- NEW: stream text → Kokoro generates chunks → plays each as ready → first word in ~200ms

Module-level API preserved: initialize(), speak(), shutdown(), is_speaking()
"""

import logging
import os
import re
import subprocess
import threading
import time
from typing import Optional

os.environ['HF_HUB_OFFLINE'] = '1'

logger = logging.getLogger("maez")

_stream = None
_engine = None
_initialized = False
_speaking = False
_lock = threading.Lock()


def initialize(output_device: Optional[str] = None) -> bool:
    """Initialize RealtimeTTS with Kokoro engine."""
    global _stream, _engine, _initialized

    try:
        from RealtimeTTS import TextToAudioStream, KokoroEngine

        logger.info("Initializing RealtimeTTS + Kokoro streaming...")
        _engine = KokoroEngine(voice='af_heart')
        _stream = TextToAudioStream(
            _engine,
            on_audio_stream_start=_on_start,
            on_audio_stream_stop=_on_stop,
        )
        _initialized = True
        logger.info("VoiceOutput ready — RealtimeTTS streaming")
        return True
    except Exception as e:
        logger.error("VoiceOutput init failed: %s", e)
        return False


def _on_start():
    global _speaking
    _speaking = True
    # Suppress wake word detection during speech
    try:
        from skills.wake_word import set_speaking
        set_speaking(True)
    except Exception:
        pass


def _on_stop():
    global _speaking
    _speaking = False
    try:
        from skills.wake_word import set_speaking
        set_speaking(False)
    except Exception:
        pass


def speak(text: str, priority: bool = False):
    """
    Stream text to speech. Non-blocking — audio plays in background.
    First chunk plays within ~200ms.
    """
    if not _initialized or not text.strip():
        return

    # Clean text for speech
    clean = text.replace('*', '').replace('_', '').replace('[', '').replace(']', '')[:500]
    if not clean.strip():
        return

    def _run():
        try:
            # Split into sentences for chunk-aware streaming
            sentences = re.split(r'(?<=[.!?])\s+', clean.strip())

            def text_gen():
                for sentence in sentences:
                    if sentence.strip():
                        yield sentence.strip() + ' '

            _stream.feed(text_gen())
            _stream.play()
            logger.debug("Spoke: %s", clean[:60])
        except Exception as e:
            logger.error("Speak error: %s", e)

    threading.Thread(target=_run, daemon=True, name='maez-voice').start()


def feed_sentence(text: str):
    """Feed a sentence to the active stream. Starts playback if not already playing."""
    if not _initialized or not text.strip():
        return
    clean = text.replace('*', '').replace('_', '').replace('[', '').replace(']', '')
    if not clean.strip():
        return
    try:
        _stream.feed(clean + ' ')
        if not _speaking:
            threading.Thread(target=_play_safe, daemon=True, name='maez-voice-stream').start()
    except Exception as e:
        logger.error("Feed sentence error: %s", e)


def _play_safe():
    """Play stream — called once, plays until feed buffer is exhausted."""
    try:
        _stream.play()
    except Exception as e:
        logger.error("Play error: %s", e)


def speak_blocking(text: str):
    """Blocking speak — waits until audio finishes. Use for short phrases."""
    if not _initialized or not text.strip():
        return

    clean = text.replace('*', '').replace('_', '').replace('[', '').replace(']', '')[:300]
    try:
        _stream.feed(clean)
        _stream.play()
        logger.debug("Spoke (blocking): %s", clean[:60])
    except Exception as e:
        logger.error("Speak blocking error: %s", e)


def stop():
    """Immediately stop speaking — for barge-in."""
    if _stream and _speaking:
        try:
            _stream.stop()
            logger.info("Voice stopped — barge-in")
        except Exception:
            pass


def is_speaking() -> bool:
    return _speaking


def shutdown():
    """Clean shutdown."""
    global _initialized
    stop()
    _initialized = False
    logger.info("Voice output shutdown")


def test():
    logging.basicConfig(level=logging.INFO)
    print("Testing RealtimeTTS streaming...")
    if not initialize():
        print("FAILED")
        return False
    t0 = time.time()
    print("Speaking...")
    speak("Maez is online. Streaming voice output is now active. The first word plays before the rest is generated.")
    time.sleep(8)
    print(f"Done. Total time: {time.time()-t0:.1f}s")
    shutdown()
    return True


if __name__ == '__main__':
    test()
