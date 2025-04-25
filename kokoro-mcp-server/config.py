import os
import logging
from pathlib import Path
from dotenv import load_dotenv
import torch

# Logging setup (can be configured further)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Environment Loading ---

# Load environment variables (.env takes precedence over .env.test if both exist)
# In a real scenario, you might load .env.test specifically for testing environments
load_dotenv(dotenv_path=Path('.') / '.env.test', override=True) # Load test first if exists
load_dotenv(dotenv_path=Path('.') / '.env', override=True) # Load main .env, overriding test if keys overlap
logger.info("Loaded environment variables from .env files (if present).")

# --- Application Settings ---

HTTP_HOST = os.getenv("HTTP_HOST", "127.0.0.1")
HTTP_PORT = int(os.getenv("HTTP_PORT", 8080))
KOKORO_DEVICE_ENV = os.getenv("KOKORO_DEVICE") # e.g., 'cuda', 'cpu', 'mps' or None for auto

# --- Directory Setup ---

# Ensure temp audio directory exists relative to this config file's location
BASE_DIR = Path(__file__).parent.resolve()
TEMP_AUDIO_DIR = BASE_DIR / "temp_audio"
try:
    TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Temporary audio directory ensured at: {TEMP_AUDIO_DIR}")
except OSError as e:
    logger.error(f"Failed to create temporary audio directory {TEMP_AUDIO_DIR}: {e}", exc_info=True)
    # Depending on severity, you might want to exit here
    raise

# --- Kokoro Device Determination ---

def determine_device() -> str:
    """Determines the appropriate torch device based on environment and availability."""
    if KOKORO_DEVICE_ENV and KOKORO_DEVICE_ENV.lower() in ['cuda', 'cpu', 'mps']:
        device = KOKORO_DEVICE_ENV.lower()
        logger.info(f"Using device specified in environment: {device}")
    else:
        if torch.cuda.is_available():
            device = 'cuda'
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            # Check if MPS is truly available and functional
            try:
                torch.zeros(1, device='mps')
                device = 'mps'
            except Exception:
                logger.warning("MPS backend detected but seems non-functional. Falling back to CPU.")
                device = 'cpu'
        else:
            device = 'cpu'
        logger.info(f"Auto-detected device: {device}")
    return device

DEVICE = determine_device()

# --- Other Constants ---
KOKORO_SAMPLE_RATE = 24000 # Assuming Kokoro default output rate

logger.info(f"Configuration loaded: HTTP={HTTP_HOST}:{HTTP_PORT}, Device={DEVICE}")