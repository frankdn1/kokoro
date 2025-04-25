import sys
import os
import tempfile
import logging
from pathlib import Path

import torch
from scipy.io.wavfile import write as write_wav

from kokoro import KModel, KPipeline
# Attempt to import get_voices, handle potential differences in kokoro library structure
try:
    from kokoro.common import get_voices
except ImportError:
    # Provide a fallback or raise a more specific error if get_voices isn't found
    logging.warning("Could not import get_voices from kokoro.common. Voice listing might be incomplete.")
    # Define a dummy function or alternative mechanism if needed
    def get_voices():
        logging.error("get_voices function not found in kokoro library. Cannot list voices.")
        return {} # Return empty dict as a fallback

# Import configuration after potential fallback definition
from config import DEVICE, TEMP_AUDIO_DIR, KOKORO_SAMPLE_RATE, logger

# --- Global Variables for Kokoro Service ---
_kokoro_model: KModel | None = None
_kokoro_pipelines: dict[str, KPipeline] = {} # Cache pipelines by language code {lang_code: pipeline}
_available_voices: dict[str, str] = {} # Cache available voices {voice_id: voice_name}

# --- Initialization ---

def init_kokoro():
    """Initializes the Kokoro model, pipelines, and voice list."""
    global _kokoro_model, _available_voices, _kokoro_pipelines

    if _kokoro_model:
        logger.info("Kokoro already initialized.")
        return

    logger.info(f"Initializing Kokoro on device: {DEVICE}...")
    try:
        _kokoro_model = KModel().to(DEVICE).eval()
        logger.info("Kokoro KModel loaded successfully.")

        # Load available voices
        _available_voices = get_voices()
        if not _available_voices:
             logger.warning("No voices loaded. Check Kokoro installation and voice data.")
        else:
             logger.info(f"Loaded {_len(_available_voices)} voices.")

        # Determine unique language codes from loaded voices
        lang_codes = set(voice_id[0] for voice_id in _available_voices.keys())

        # Pre-load pipelines for detected languages
        for lang_code in lang_codes:
            try:
                _kokoro_pipelines[lang_code] = KPipeline(lang_code=lang_code, model=False) # Model=False uses global model
                logger.info(f"Loaded pipeline for lang code '{lang_code}'")
                # Add custom pronunciations if needed (example)
                if lang_code == 'a':
                    _kokoro_pipelines[lang_code].g2p.lexicon.golds['kokoro'] = 'kˈOkəɹO'
                elif lang_code == 'b':
                     _kokoro_pipelines[lang_code].g2p.lexicon.golds['kokoro'] = 'kˈQkəɹQ'
            except Exception as e:
                logger.error(f"Failed to load pipeline for lang code '{lang_code}': {e}", exc_info=True)
                # Continue loading other pipelines

        # Optional: Pre-load all voice data (can increase startup time/memory)
        # logger.info("Pre-loading voice data (this might take a while)...")
        # for voice_id in _available_voices.keys():
        #     lang_code = voice_id[0]
        #     if lang_code in _kokoro_pipelines:
        #         try:
        #             _kokoro_pipelines[lang_code].load_voice(voice_id)
        #         except Exception as e:
        #             logger.error(f"Failed to pre-load voice data for '{voice_id}': {e}")
        # logger.info("Finished pre-loading voice data.")

    except Exception as e:
        logger.error(f"Fatal error during Kokoro initialization: {e}", exc_info=True)
        sys.exit(1) # Exit if core component fails

# --- Service Functions ---

def get_voice_list() -> dict[str, str]:
    """Returns the cached dictionary of available voices."""
    if not _available_voices:
        logger.warning("Attempted to get voice list, but it's empty.")
    return _available_voices

def generate_speech_audio(text: str, voice_id: str, speed: float) -> Path:
    """Generates audio using Kokoro and saves it to a temporary WAV file."""
    global _kokoro_model, _kokoro_pipelines

    if not _kokoro_model:
        raise RuntimeError("Kokoro model not initialized.")

    if voice_id not in _available_voices:
        logger.error(f"Requested voice ID '{voice_id}' not found in available voices.")
        raise ValueError(f"Invalid voice_id: {voice_id}")

    lang_code = voice_id[0]
    if lang_code not in _kokoro_pipelines:
        # This shouldn't happen if init_kokoro loaded all detected lang codes
        logger.error(f"Pipeline for language code '{lang_code}' (for voice '{voice_id}') not found.")
        raise RuntimeError(f"Internal error: Pipeline missing for language code {lang_code}")

    pipeline = _kokoro_pipelines[lang_code]

    try:
        # Ensure voice data is loaded for the specific voice needed
        # load_voice might be idempotent or reload if necessary
        pack = pipeline.load_voice(voice_id)
        logger.debug(f"Ensured voice data is loaded for '{voice_id}'")

        # Generate audio (simplified loop, takes first segment)
        audio_data = None
        segment_count = 0
        for _, ps, _ in pipeline(text, voice_id, speed):
            segment_count += 1
            ref_s = pack[len(ps)-1] # Get speaker embedding
            with torch.no_grad():
                 # Generate on the configured device, move to CPU for numpy conversion
                 audio_tensor = _kokoro_model(ps, ref_s, speed).cpu()
            audio_data = audio_tensor.numpy()
            logger.info(f"Generated audio segment {segment_count} with {len(ps)} tokens for voice '{voice_id}'.")
            break # Use the first generated segment

        if audio_data is None:
            logger.warning(f"Kokoro pipeline yielded no audio segments for the input text and voice '{voice_id}'.")
            raise ValueError("Failed to generate any audio segments from the input.")

        # Create a secure temporary file
        fd, temp_path_str = tempfile.mkstemp(suffix=".wav", dir=TEMP_AUDIO_DIR)
        os.close(fd)
        temp_path = Path(temp_path_str)

        # Write the audio data
        write_wav(temp_path, KOKORO_SAMPLE_RATE, audio_data)
        logger.info(f"Audio for voice '{voice_id}' saved to temporary file: {temp_path}")
        return temp_path

    except KeyError:
        # This might occur if load_voice fails internally after pipeline creation
        logger.error(f"Internal KeyError looking up voice '{voice_id}' during generation.")
        raise ValueError(f"Invalid voice_id: {voice_id}")
    except Exception as e:
        logger.error(f"Error during audio generation for voice '{voice_id}': {e}", exc_info=True)
        raise RuntimeError(f"Audio generation failed: {e}")