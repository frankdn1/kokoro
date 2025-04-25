import pytest
import os
from pathlib import Path
import tempfile

# Import the Flask app instance from the http_server module
from http_server import flask_app
# Import config for TEMP_AUDIO_DIR
from config import TEMP_AUDIO_DIR, logger

# --- Fixtures ---

@pytest.fixture(scope='module')
def test_client():
    """Provides a test client for the Flask application."""
    logger.info("Setting up Flask test client...")
    # Propagate exceptions from the application to the test client
    flask_app.config['TESTING'] = True
    flask_app.config['PROPAGATE_EXCEPTIONS'] = True

    with flask_app.test_client() as client:
        yield client
    logger.info("Tearing down Flask test client.")


@pytest.fixture(scope='function') # Use function scope to ensure cleanup after each test
def temp_audio_file():
    """Creates a temporary dummy audio file for testing."""
    logger.info("Creating temporary audio file for test...")
    # Create a file directly in the TEMP_AUDIO_DIR for the test client to find
    fd, file_path_str = tempfile.mkstemp(suffix=".wav", dir=TEMP_AUDIO_DIR)
    file_path = Path(file_path_str)
    # Write some dummy content
    dummy_content = b"RIFFdummyWAVEfmt data"
    with open(file_path, 'wb') as f:
        f.write(dummy_content)
    os.close(fd)
    logger.info(f"Created dummy file: {file_path}")

    yield file_path # Provide the path to the test

    # Teardown: Clean up the created file
    logger.info(f"Cleaning up temporary audio file: {file_path}")
    try:
        file_path.unlink()
    except FileNotFoundError:
        logger.warning(f"Test file {file_path} already deleted or moved.")
    except Exception as e:
        logger.error(f"Error cleaning up test file {file_path}: {e}", exc_info=True)


# --- Test Cases ---

def test_serve_audio_success(test_client, temp_audio_file):
    """Test successfully serving an existing audio file."""
    logger.info(f"Testing successful GET /audio/{temp_audio_file.name}")
    response = test_client.get(f"/audio/{temp_audio_file.name}")

    assert response.status_code == 200
    assert response.mimetype == 'audio/wav'
    assert response.data == b"RIFFdummyWAVEfmt data" # Check content matches dummy content

def test_serve_audio_not_found(test_client):
    """Test requesting a non-existent audio file."""
    filename = "non_existent_dummy_file.wav"
    logger.info(f"Testing GET /audio/{filename} (expected 404)")
    response = test_client.get(f"/audio/{filename}")

    assert response.status_code == 404

def test_serve_audio_directory_traversal_attempt(test_client):
    """Test attempting directory traversal."""
    # Construct a path attempting to go outside the temp dir
    # Note: Flask/Werkzeug's routing usually handles basic .. cleaning,
    # but the check in our route provides an extra layer.
    malicious_filename = "../config.py" # Example attempt
    logger.info(f"Testing GET /audio/{malicious_filename} (expected 404 - traversal)")
    response = test_client.get(f"/audio/{malicious_filename}")

    # Expect 404 because the resolved path check should fail
    assert response.status_code == 404

def test_serve_audio_absolute_path_attempt(test_client):
    """Test attempting to request using an absolute-like path in URL."""
    # Although browsers/clients shouldn't send this, test robustness
    malicious_filename = "/etc/passwd"
    logger.info(f"Testing GET /audio/{malicious_filename} (expected 308 - Flask redirect for absolute paths)")
    response = test_client.get(f"/audio/{malicious_filename}")

    # Flask returns 308 (Permanent Redirect) for absolute paths
    assert response.status_code == 308