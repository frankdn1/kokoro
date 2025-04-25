import threading
import logging
from pathlib import Path
from flask import Flask, send_from_directory, abort

# Import configuration constants
from config import HTTP_HOST, HTTP_PORT, TEMP_AUDIO_DIR, logger

# --- Flask App Initialization ---
flask_app = Flask(__name__)
logger.info("Flask application initialized.")

# --- Flask HTTP Server Routes ---

@flask_app.route('/audio/<path:filename>', strict_slashes=False)
def serve_audio(filename):
    """Serves the temporary audio file from the configured directory."""
    logger.info(f"Received request to serve audio file: {filename}")
    
    # Security: First check for absolute paths in the URL
    if filename.startswith('/') or filename.startswith('\\'):
        logger.warning(f"Absolute path attempt blocked: {filename}")
        return "Not Found", 404  # Return directly to avoid Flask redirect
        
    # Security: Also check for encoded absolute paths
    if filename.startswith('%2F') or filename.startswith('%5C'):
        logger.warning(f"Encoded absolute path attempt blocked: {filename}")
        return "Not Found", 404
    
    try:
        # Security: Ensure the filename is safe and points within the temp dir
        # Resolve the path to prevent directory traversal (e.g., ../../etc/passwd)
        requested_path = TEMP_AUDIO_DIR.joinpath(filename).resolve()

        # Check if the resolved path is within the intended TEMP_AUDIO_DIR
        if not requested_path.is_file() or TEMP_AUDIO_DIR.resolve() not in requested_path.parents:
             logger.warning(f"Access denied or file not found for path: {requested_path} (Original filename: {filename})")
             return "Not Found", 404  # Return directly to avoid Flask abort

        logger.info(f"Serving file: {requested_path}")
        return send_from_directory(
            TEMP_AUDIO_DIR.resolve(), # Directory must be absolute path
            requested_path.name,      # Serve using the resolved filename
            mimetype='audio/wav',
            as_attachment=False       # Serve inline for browser playback
        )
    except FileNotFoundError:
         # This might be redundant due to the check above, but good practice
         logger.warning(f"File not found during send_from_directory: {filename}")
         abort(404)
    except Exception as e:
         logger.error(f"Error serving file {filename}: {e}", exc_info=True)
         abort(500) # Internal Server Error

# --- Server Execution Function ---

def run_http_server():
    """Runs the Flask app. Intended to be run in a separate thread."""
    logger.info(f"Starting Flask HTTP server on http://{HTTP_HOST}:{HTTP_PORT}")
    try:
        # For production, consider using a more robust WSGI server like waitress or gunicorn
        # Example using waitress (requires `pip install waitress`):
        # from waitress import serve
        # serve(flask_app, host=HTTP_HOST, port=HTTP_PORT)

        # Using Flask's built-in server (suitable for development/simple cases)
        flask_app.run(host=HTTP_HOST, port=HTTP_PORT, debug=False, use_reloader=False)
        # debug=False and use_reloader=False are important when running in a thread

    except OSError as e:
        logger.error(f"Flask server failed to start on {HTTP_HOST}:{HTTP_PORT}. Port might be in use. Error: {e}", exc_info=True)
        # Consider how to signal the main application to stop if the HTTP server fails critically
        raise # Re-raise the exception
    except Exception as e:
        logger.error(f"An unexpected error occurred in the Flask server thread: {e}", exc_info=True)
        raise # Re-raise the exception