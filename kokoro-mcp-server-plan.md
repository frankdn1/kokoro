# Plan (v5): Kokoro TTS MCP Server (HTTP URLs, Configurable Port, Testing)

This plan outlines the architecture and implementation steps for creating an MCP server to provide Kokoro Text-to-Speech functionality. It uses HTTP URLs for audio file access, allows port configuration via a `.env` file, and includes a testing strategy.

## 1. Project Setup

*   Create project directory: `kokoro-mcp-server`
*   Set up Python virtual environment.
*   Install dependencies: `kokoro-tts`, `torch`, `mcp_server_sdk` (or equivalent), `numpy`, `scipy`, `Flask`, `python-dotenv`, `pytest`, `pytest-mock`. Add these to `requirements.txt`.
*   Create initial files:
    *   `main.py`: Main server logic.
    *   `requirements.txt`: Project dependencies.
    *   `.env`: Environment configuration (e.g., `HTTP_PORT=8080`).
    *   `.env.test`: Test-specific environment configuration (e.g., `HTTP_PORT=8081`).
    *   `.gitignore`: Include `temp_audio/`, `__pycache__/`, `*.pyc`, `.env*`, virtual environment directory (e.g., `venv/`).
*   Create directories:
    *   `temp_audio/`: For storing temporary WAV files (add to `.gitignore`).
    *   `tests/`: For test code.

## 2. MCP Server Core (`main.py`)

*   Import necessary libraries.
*   Load environment variables from `.env` or `.env.test` using `python-dotenv`.
*   Initialize Kokoro `KModel` and `KPipeline` instances (handle GPU auto-detection).
*   Initialize Flask application.
*   Define a Flask route (e.g., `/audio/<filename>`) to serve static files from the `temp_audio` directory. Ensure proper Content-Type (`audio/wav`).
*   Define MCP server name (e.g., `kokoro-tts-server`).
*   Refactor core logic (TTS generation, file handling) into testable functions.

## 3. Define Tools (via MCP JSON-RPC)

*   **`list_voices` Tool:**
    *   *Input:* None
    *   *Logic:* Retrieve available voices (IDs and friendly names) from Kokoro.
    *   *Output (JSON-RPC):* `{ "voices": [ { "id": "...", "name": "..." }, ... ] }`
*   **`generate_speech` Tool:**
    *   *Input:* `text` (string, required), `voice_id` (string, required), `speed` (float, optional, default=1.0).
    *   *Logic:*
        *   Call core function to generate audio data using Kokoro.
        *   Call core function to save audio data to a unique temporary WAV file in `temp_audio`.
        *   Construct the full HTTP URL using the configured host/port (e.g., `http://127.0.0.1:<HTTP_PORT>/audio/<filename>.wav`).
    *   *Output (JSON-RPC):* `{ "audio_uri": "http://...", "format": "wav" }`
*   **`cleanup_audio` Tool:**
    *   *Input:* `audio_uri` (string, required): The `http://...` URI.
    *   *Logic:*
        *   Parse filename from URI.
        *   Construct the full path within `temp_audio`.
        *   Validate the path is within the expected directory.
        *   Safely delete the file (`os.remove`). Handle potential errors (file not found).
    *   *Output (JSON-RPC):* `{ "success": true/false, "error": "..." (optional) }`

## 4. Server Registration/Execution

*   Implement the main execution block (`if __name__ == "__main__":`).
*   Start the Flask HTTP server in a separate thread or using an async framework.
*   Start the MCP server loop (using the MCP Server SDK) to listen for JSON-RPC requests.
*   Ensure graceful shutdown of both servers.

## 5. Testing (`tests/` directory)

*   **Framework:** Use `pytest`.
*   **Configuration:** Use `.env.test` for test settings.
*   **Unit Tests:** Test helper functions (URI parsing, filename generation, path validation, config loading).
*   **Integration Tests (MCP Tools):**
    *   Use `pytest-mock` to mock `kokoro` model/pipeline calls.
    *   Test `list_voices` structure.
    *   Test `generate_speech` (mocked): Verify file creation in `temp_audio`, correct HTTP URI format.
    *   Test `cleanup_audio` (mocked): Verify file deletion after generation.
*   **Integration Tests (HTTP Endpoint):**
    *   Use `pytest` fixtures to manage a test Flask client or run a test server instance.
    *   Test the `/audio/<filename>` endpoint: Place a test file, make GET request, verify content and status code, test cleanup.

## Diagram

```mermaid
graph TD
    subgraph Kokoro MCP Server Process
        direction TB
        A[main.py: Server Startup] --> R(Load .env Config - HTTP_PORT);
        R --> B(Initialize Kokoro Model/Pipeline);
        R --> Q(Initialize HTTP Server - Flask on HTTP_PORT);
        subgraph MCP Communication (JSON-RPC)
            direction LR
            B --> C{Tool Dispatcher};
            C --> D[list_voices Tool];
            C --> E[generate_speech Tool];
            C --> N[cleanup_audio Tool];
        end
        subgraph HTTP File Serving (HTTP GET)
            direction LR
            Q -- Serves Files --> P((temp_audio Directory));
        end
    end

    subgraph Kokoro Library
        direction LR
        F(KModel)
        G(KPipeline)
        H(Voices Data)
    end

    B --> F;
    B --> G;
    D --> H;
    E --> G;
    E --> F;
    E --> H;
    E -- Writes File --> P;

    subgraph MCP Client (e.g., Kokoro IDE)
        direction TB
        I(User Request) --> J{Use MCP Tool (JSON-RPC)};
        J -- tool: list_voices --> C;
        J -- tool: generate_speech --> C;
        J -- tool: cleanup_audio --> C;
        D --> K(Voice List Response - JSON);
        E --> L(Generated Audio Response - JSON with HTTP URI);
        N --> O(Cleanup Confirmation - JSON);
        K --> M(Display/Use Voices);
        L -- Extract URI --> S{Fetch Audio (HTTP GET)};
        S -- HTTP GET Request to :HTTP_PORT --> Q;
        N -- Delete File --> P;
        Q -- Serves File --> M;
    end