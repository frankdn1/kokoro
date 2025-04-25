import sys
import threading
import logging
from pathlib import Path
from urllib.parse import urlparse

# Import components from our modules
from config import HTTP_HOST, HTTP_PORT, TEMP_AUDIO_DIR, logger
import kokoro_service
import http_server

# Assuming mcp_server_sdk provides necessary components
# Replace with actual SDK imports if available
# from mcp_server_sdk import MCPServer, MCPServerError
class MockMCPServerError(Exception):
    """Placeholder for SDK-specific errors."""
    pass

class MockMCPServer:
    """Placeholder for the actual MCP Server SDK class."""
    def __init__(self):
        self._tools = {}
        self._running = True

    def register_tool(self, name):
        """Decorator to register tool functions."""
        def decorator(func):
            logger.info(f"Registering MCP tool: {name}")
            self._tools[name] = func
            return func
        return decorator

    def _handle_request(self, request):
        # Placeholder for how the SDK might dispatch calls
        # In a real SDK, this would parse JSON-RPC, find the method, call it, and serialize the response
        tool_name = request.get("method")
        params = request.get("params", {})
        if tool_name in self._tools:
            try:
                # Simulate calling the tool function with parameters
                if isinstance(params, list):
                    result = self._tools[tool_name](*params)
                elif isinstance(params, dict):
                    result = self._tools[tool_name](**params)
                else:
                    raise MockMCPServerError("Invalid params format")
                return {"jsonrpc": "2.0", "result": result, "id": request.get("id")}
            except Exception as e:
                logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
                # Map specific exceptions to JSON-RPC errors if needed
                error_code = -32000 # Server error
                error_message = f"Error in tool '{tool_name}': {e}"
                if isinstance(e, ValueError):
                    error_code = -32602 # Invalid params
                elif isinstance(e, MockMCPServerError):
                     error_message = str(e) # Use custom error message

                return {
                    "jsonrpc": "2.0",
                    "error": {"code": error_code, "message": error_message},
                    "id": request.get("id")
                }
        else:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {tool_name}"},
                "id": request.get("id")
            }


    def serve_forever(self):
        logger.info("Starting Mock MCP Server (JSON-RPC)...")
        # In a real SDK, this would start the JSON-RPC listener (e.g., over stdio or network)
        logger.info("Mock MCP Server running. Waiting for requests (simulated).")
        # Simulate waiting for requests (replace with actual SDK blocking call)
        while self._running:
            try:
                # Example: Simulate receiving a request (replace with actual SDK mechanism)
                # raw_request = sys.stdin.readline()
                # if not raw_request: break # End of input
                # request_data = json.loads(raw_request)
                # response_data = self._handle_request(request_data)
                # print(json.dumps(response_data), flush=True)

                # Keep alive for mock server
                threading.Event().wait(timeout=1)
            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt received, stopping MCP server.")
                self.shutdown()
            except Exception as e:
                 logger.error(f"Error in mock server loop: {e}", exc_info=True)
                 self.shutdown() # Stop on unexpected errors

    def shutdown(self):
        self._running = False
        logger.info("Mock MCP Server shutting down.")


# --- MCP Server Instance ---
# Replace MockMCPServer with actual SDK server class when available
mcp_server = MockMCPServer()

# --- MCP Tool Implementations ---

@mcp_server.register_tool("list_voices")
def list_voices_tool():
    """Returns a list of available Kokoro voices."""
    logger.info("Executing MCP tool: list_voices")
    try:
        voices = kokoro_service.get_voice_list()
        if not voices:
             logger.warning("Voice list is empty.")
             # Depending on SDK, might raise specific error or return empty
             # raise MockMCPServerError("Voice list unavailable.")
        formatted_voices = [{"id": id, "name": name} for id, name in voices.items()]
        return {"voices": formatted_voices}
    except Exception as e:
        logger.error(f"Error in list_voices_tool: {e}", exc_info=True)
        raise MockMCPServerError(f"Failed to list voices: {e}")


@mcp_server.register_tool("generate_speech")
def generate_speech_tool(text: str, voice_id: str, speed: float = 1.0):
    """Generates speech using Kokoro and returns an HTTP URI to the audio file."""
    logger.info(f"Executing MCP tool: generate_speech (Voice: {voice_id}, Speed: {speed})")
    if not text or not voice_id:
        raise ValueError("Missing required arguments: text and voice_id") # Or MockMCPServerError

    try:
        # Ensure speed is a float
        speed_float = float(speed)
        # Call the service function to handle generation and file saving
        temp_file_path = kokoro_service.generate_speech_audio(text, voice_id, speed_float)

        # Construct the full URL using configured host and port
        # Ensure host is included for accessibility outside localhost if needed
        audio_uri = f"http://{HTTP_HOST}:{HTTP_PORT}/audio/{temp_file_path.name}"
        logger.info(f"Generated audio URI: {audio_uri}")
        return {"audio_uri": audio_uri, "format": "wav"}
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        # Catch specific, expected errors from the service layer
        logger.error(f"generate_speech failed: {e}")
        # Re-raise as a specific error the SDK might understand, or a generic one
        raise MockMCPServerError(str(e))
    except Exception as e:
        # Catch unexpected errors
        logger.error(f"Unexpected error in generate_speech: {e}", exc_info=True)
        raise MockMCPServerError("Internal server error during speech generation.")


@mcp_server.register_tool("cleanup_audio")
def cleanup_audio_tool(audio_uri: str):
    """Deletes a temporary audio file given its HTTP URI."""
    logger.info(f"Executing MCP tool: cleanup_audio (URI: {audio_uri})")
    if not audio_uri:
        raise ValueError("Missing required argument: audio_uri")

    try:
        # First validate URI format
        parsed_uri = urlparse(audio_uri)
        if not all([parsed_uri.scheme, parsed_uri.netloc, parsed_uri.path]):
            raise ValueError("Invalid audio URI format")

        filename = Path(parsed_uri.path).name
        if not filename:
            raise ValueError("Could not extract filename from URI path")

        # Construct and validate the expected local file path
        file_path = TEMP_AUDIO_DIR.joinpath(filename)
        
        # Security check - ensure path is within temp dir
        try:
            resolved_path = file_path.resolve()
            if not resolved_path.is_relative_to(TEMP_AUDIO_DIR.resolve()):
                raise ValueError("Invalid audio URI (path mismatch)")
        except RuntimeError as e:
            raise ValueError(f"Invalid audio URI (path resolution failed): {e}")

        # Perform file operations
        if resolved_path.is_file():
            resolved_path.unlink()
            logger.info(f"Successfully deleted temporary file: {resolved_path}")
            return {"success": True}
        else:
            logger.warning(f"Temporary file not found for cleanup: {resolved_path}")
            return {"success": False, "error": "File not found at specified URI"}

    except ValueError as e:
        logger.error(f"Invalid URI or path during cleanup for {audio_uri}: {e}")
        raise MockMCPServerError(f"Cleanup failed: {e}")
    except Exception as e:
        logger.error(f"Error during cleanup for URI {audio_uri}: {e}", exc_info=True)
        raise MockMCPServerError(f"Cleanup failed: {e}")


# --- Main Execution ---

def main():
    """Main function to initialize and start servers."""
    logger.info("Starting Kokoro TTS MCP Server...")
    try:
        # Initialize Kokoro service (loads models, etc.)
        kokoro_service.init_kokoro()

        # Start Flask server in a background thread
        # Mark as daemon so it exits when the main thread exits
        flask_thread = threading.Thread(target=http_server.run_http_server, daemon=True, name="FlaskThread")
        flask_thread.start()

        # Start MCP server (this should block in a real SDK)
        mcp_server.serve_forever()

    except Exception as e:
        logger.critical(f"MCP Server exited with critical error: {e}", exc_info=True)
        sys.exit(1) # Exit with error code
    finally:
        logger.info("Shutting down Kokoro TTS MCP Server.")
        # Cleanup can be added here if needed, though daemon threads exit automatically

if __name__ == "__main__":
    main()