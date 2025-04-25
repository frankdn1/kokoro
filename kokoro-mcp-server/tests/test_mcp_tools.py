import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from urllib.parse import urlparse

# Import the tool functions and config needed for testing
# Assuming pytest runs from the root `kokoro-mcp-server` directory
from main import list_voices_tool, generate_speech_tool, cleanup_audio_tool, MockMCPServerError
from config import HTTP_HOST, HTTP_PORT, TEMP_AUDIO_DIR, logger

# --- Fixtures ---

@pytest.fixture
def mock_kokoro_service(mocker):
    """Mocks the kokoro_service module functions."""
    logger.info("Applying mock for kokoro_service...")
    mock_get_list = mocker.patch('kokoro_service.get_voice_list', return_value={
        'af_test_voice': 'Test Voice Female',
        'am_test_voice': 'Test Voice Male'
    })
    # Mock generate_speech_audio to return a predictable Path object
    mock_generate = mocker.patch('kokoro_service.generate_speech_audio')
    mock_generate.return_value = TEMP_AUDIO_DIR / "test_audio_123.wav"

    # Mock the init function as well, as it might be called implicitly
    mocker.patch('kokoro_service.init_kokoro')

    return {
        "get_voice_list": mock_get_list,
        "generate_speech_audio": mock_generate
    }

@pytest.fixture
def mock_path_ops(mocker):
    """Mocks Path operations like is_file and unlink."""
    logger.info("Applying mock for Path operations...")
    mock_is_file = mocker.patch('pathlib.Path.is_file')
    mock_unlink = mocker.patch('pathlib.Path.unlink')
    # Ensure resolve() and parents work as expected for security checks
    mocker.patch('pathlib.Path.resolve', side_effect=lambda p=Path('.'): Path(os.path.abspath(p)))
    # Mock is_relative_to for path traversal checks
    mock_is_relative_to = mocker.patch('pathlib.Path.is_relative_to')


    return {
        "is_file": mock_is_file,
        "unlink": mock_unlink,
        "is_relative_to": mock_is_relative_to
    }


# --- Test Cases ---

def test_list_voices_tool_success(mock_kokoro_service):
    """Test list_voices_tool returns correctly formatted voice list."""
    logger.info("Testing list_voices_tool success case...")
    result = list_voices_tool()
    assert "voices" in result
    assert isinstance(result["voices"], list)
    assert len(result["voices"]) == 2
    assert {"id": "af_test_voice", "name": "Test Voice Female"} in result["voices"]
    assert {"id": "am_test_voice", "name": "Test Voice Male"} in result["voices"]
    mock_kokoro_service["get_voice_list"].assert_called_once()

def test_list_voices_tool_empty(mock_kokoro_service):
    """Test list_voices_tool when kokoro_service returns empty list."""
    logger.info("Testing list_voices_tool empty case...")
    mock_kokoro_service["get_voice_list"].return_value = {}
    result = list_voices_tool()
    assert "voices" in result
    assert result["voices"] == []
    mock_kokoro_service["get_voice_list"].assert_called_once()

def test_generate_speech_tool_success(mock_kokoro_service):
    """Test generate_speech_tool success case."""
    logger.info("Testing generate_speech_tool success case...")
    text = "Hello world"
    voice_id = "af_test_voice"
    speed = 1.2

    result = generate_speech_tool(text=text, voice_id=voice_id, speed=speed)

    # Assert generate_speech_audio was called correctly
    mock_kokoro_service["generate_speech_audio"].assert_called_once_with(text, voice_id, speed)

    # Assert the result format
    assert "audio_uri" in result
    assert "format" in result
    assert result["format"] == "wav"

    # Assert the URI format
    expected_filename = "test_audio_123.wav"
    expected_uri = f"http://{HTTP_HOST}:{HTTP_PORT}/audio/{expected_filename}"
    assert result["audio_uri"] == expected_uri

def test_generate_speech_tool_missing_args():
    """Test generate_speech_tool raises error on missing arguments."""
    logger.info("Testing generate_speech_tool missing args...")
    with pytest.raises(ValueError, match="Missing required arguments"):
        generate_speech_tool(text="hello", voice_id=None) # type: ignore
    with pytest.raises(ValueError, match="Missing required arguments"):
        generate_speech_tool(text=None, voice_id="af_test") # type: ignore

def test_generate_speech_tool_service_error(mock_kokoro_service):
    """Test generate_speech_tool handles errors from kokoro_service."""
    logger.info("Testing generate_speech_tool service error...")
    mock_kokoro_service["generate_speech_audio"].side_effect = RuntimeError("Kokoro generation failed!")

    with pytest.raises(MockMCPServerError, match="Kokoro generation failed!"):
        generate_speech_tool(text="hello", voice_id="af_test_voice")

def test_cleanup_audio_tool_success(mock_path_ops):
    """Test cleanup_audio_tool successfully deletes a file."""
    logger.info("Testing cleanup_audio_tool success case...")
    filename = "test_audio_abc.wav"
    audio_uri = f"http://{HTTP_HOST}:{HTTP_PORT}/audio/{filename}"
    expected_path = TEMP_AUDIO_DIR / filename

    # Mock that the file exists
    mock_path_ops["is_file"].return_value = True

    result = cleanup_audio_tool(audio_uri=audio_uri)

    assert result == {"success": True}
    mock_path_ops["unlink"].assert_called_once()


def test_cleanup_audio_tool_file_not_found(mock_path_ops):
    """Test cleanup_audio_tool when the file doesn't exist."""
    logger.info("Testing cleanup_audio_tool file not found...")
    filename = "non_existent_file.wav"
    audio_uri = f"http://{HTTP_HOST}:{HTTP_PORT}/audio/{filename}"

    # Mock that the file does not exist
    mock_path_ops["is_file"].return_value = False

    result = cleanup_audio_tool(audio_uri=audio_uri)

    assert result == {"success": False, "error": "File not found at specified URI"}
    mock_path_ops["unlink"].assert_not_called()

def test_cleanup_audio_tool_invalid_uri_path(mock_path_ops):
    """Test cleanup_audio_tool with a URI outside the temp directory."""
    logger.info("Testing cleanup_audio_tool invalid path...")
    # Simulate trying to delete something outside the temp dir
    audio_uri = f"http://{HTTP_HOST}:{HTTP_PORT}/audio/../../etc/passwd"

    # Mock is_relative_to to return False, simulating a path outside the temp dir
    mock_path_ops["is_relative_to"].return_value = False

    with pytest.raises(MockMCPServerError, match="Cleanup failed: Invalid audio URI \(path mismatch\)"):
         cleanup_audio_tool(audio_uri=audio_uri)

    mock_path_ops["unlink"].assert_not_called()


def test_cleanup_audio_tool_malformed_uri():
    """Test cleanup_audio_tool with a malformed URI."""
    logger.info("Testing cleanup_audio_tool malformed URI...")
    audio_uri = "http:/invalid-uri" # Missing slashes

    with pytest.raises(MockMCPServerError, match="Cleanup failed: Invalid audio URI format"):
         cleanup_audio_tool(audio_uri=audio_uri)

def test_cleanup_audio_tool_missing_arg():
    """Test cleanup_audio_tool raises error on missing argument."""
    logger.info("Testing cleanup_audio_tool missing arg...")
    with pytest.raises(ValueError, match="Missing required argument"):
        cleanup_audio_tool(audio_uri=None) # type: ignore