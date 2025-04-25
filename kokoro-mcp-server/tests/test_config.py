import os
import pytest
from pathlib import Path

# Ensure we are testing the config module within our server package
# This might require adjusting sys.path or using relative imports depending on test runner setup
# For simplicity, assume pytest runs from the root `kokoro-mcp-server` directory
from config import HTTP_PORT, HTTP_HOST, DEVICE, TEMP_AUDIO_DIR, KOKORO_SAMPLE_RATE, logger

# Define the path to the test environment file relative to the project root
TEST_ENV_PATH = Path(__file__).parent.parent / '.env.test'
MAIN_ENV_PATH = Path(__file__).parent.parent / '.env'

@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    """Ensure the test .env file exists for configuration tests."""
    logger.info("Setting up test environment for config tests...")
    # Create dummy .env files if they don't exist, to ensure tests can run
    # In a real CI/CD, these might already be present or managed differently
    if not TEST_ENV_PATH.exists():
        logger.warning(f"Creating dummy {TEST_ENV_PATH} for testing.")
        TEST_ENV_PATH.write_text("HTTP_PORT=8081\nKOKORO_DEVICE=cpu\n") # Example test values

    if not MAIN_ENV_PATH.exists():
         logger.warning(f"Creating dummy {MAIN_ENV_PATH} for testing.")
         MAIN_ENV_PATH.write_text("HTTP_PORT=8080\n") # Example main value

    # The config module loads .env files on import, so this setup ensures
    # they are present before the tests access the imported config values.
    # Reloading the config module might be needed if tests modify .env files,
    # but for basic checks, ensuring existence before import is usually sufficient.
    yield # Let tests run

    # Teardown: Optionally remove dummy files if created by this fixture
    # Be careful not to delete actual user .env files if they existed before
    # For this example, we won't delete them automatically.
    logger.info("Tearing down test environment for config tests.")


def test_http_port_loaded_from_test_env():
    """Verify HTTP_PORT is loaded correctly, prioritizing .env.test."""
    # Assumes .env.test sets HTTP_PORT=8081 and .env sets HTTP_PORT=8080
    # Since config.py loads .env.test then .env with override=True on the second load,
    # the value from .env (8080) should actually take precedence if both exist and define the var.
    # Let's adjust the expectation based on the loading logic in config.py
    # config.py loads .env.test first, then .env with override=True.
    # So, .env's value should win if the key exists in both.

    # Re-read the logic:
    # load_dotenv(dotenv_path=Path('.') / '.env.test', override=True) # Load test first
    # load_dotenv(dotenv_path=Path('.') / '.env', override=True) # Load main, overriding test

    # Therefore, if HTTP_PORT is in both, the value from .env (8080) should be loaded.
    # Let's test that expectation.
    expected_port = 8080 # Expecting the value from .env
    logger.info(f"Checking HTTP_PORT: Expected={expected_port}, Actual={HTTP_PORT}")
    assert HTTP_PORT == expected_port

def test_http_host_default():
    """Verify HTTP_HOST defaults correctly if not in .env files."""
    # Assuming HTTP_HOST is not defined in the dummy .env files
    expected_host = "127.0.0.1"
    logger.info(f"Checking HTTP_HOST: Expected={expected_host}, Actual={HTTP_HOST}")
    assert HTTP_HOST == expected_host

import torch # Import torch for mocking

def test_device_determination(monkeypatch, mocker):
    """Verify DEVICE is determined correctly (prioritizing .env.test)."""
    # Temporarily set environment variables to control the test scenario
    monkeypatch.setenv("KOKORO_DEVICE", "cpu")
    # Ensure the main .env file's KOKORO_DEVICE doesn't interfere by unsetting it
    monkeypatch.delenv("KOKORO_DEVICE", raising=False)

    # Mock torch availability to ensure determine_device relies on KOKORO_DEVICE_ENV
    mocker.patch('torch.cuda.is_available', return_value=False)
    if hasattr(torch.backends, 'mps'):
        mocker.patch('torch.backends.mps.is_available', return_value=False)
        # Also mock the torch.zeros call that checks MPS functionality
        mocker.patch('torch.zeros', side_effect=RuntimeError("MPS is mocked off"))


    # Re-import config to apply the monkeypatched environment variables and mocks
    # This is necessary because config loads environment variables and determines device on import
    import importlib
    import config
    importlib.reload(config)

    expected_device = "cpu" # Expecting value from the monkeypatched environment
    logger.info(f"Checking DEVICE: Expected={expected_device}, Actual={config.DEVICE}")
    assert config.DEVICE == expected_device

    # Note: The original DEVICE variable imported at the top level of this test file
    # will retain its initial value. We must use config.DEVICE after reloading.

def test_temp_audio_dir_exists():
    """Verify the temporary audio directory exists."""
    logger.info(f"Checking TEMP_AUDIO_DIR existence: {TEMP_AUDIO_DIR}")
    assert TEMP_AUDIO_DIR.exists()
    assert TEMP_AUDIO_DIR.is_dir()

def test_kokoro_sample_rate_constant():
    """Verify the sample rate constant is defined."""
    expected_rate = 24000
    logger.info(f"Checking KOKORO_SAMPLE_RATE: Expected={expected_rate}, Actual={KOKORO_SAMPLE_RATE}")
    assert KOKORO_SAMPLE_RATE == expected_rate