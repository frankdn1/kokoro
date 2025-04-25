import { KokoroTTS, TextSplitterStream } from "kokoro-js";
import { detectWebGPU } from "./utils.js";

// Device detection
const device = (await detectWebGPU()) ? "webgpu" : "wasm";
self.postMessage({ status: "device", device });

// Load the model
const model_id = "onnx-community/Kokoro-82M-v1.0-ONNX";
const tts = await KokoroTTS.from_pretrained(model_id, {
  dtype: device === "wasm" ? "q8" : "fp32",
  device,
}).catch((e) => {
  self.postMessage({ status: "error", error: e.message });
  throw e;
});
self.postMessage({ status: "ready", voices: tts.voices, device });

// Listen for messages from the main thread
self.addEventListener("message", async (e) => {
  const { type, text, voice } = e.data;

  if (type === "generate") {
    // Generate speech
    const audio = await tts.generate(text, { voice });

    // Send the audio file back to the main thread
    const blob = audio.toBlob();
    self.postMessage({ status: "complete", audio: URL.createObjectURL(blob), text });
  } else if (type === "stream") {
    // Create stream and splitter
    console.log("Creating text splitter and stream");
    const splitter = new TextSplitterStream();
    const stream = tts.stream(splitter, { voice });
    console.log("Stream created:", stream);
    
    // Function to push text
    const pushText = async () => {
      try {
        console.log("Starting text pushing...");
        const tokens = text.match(/\s*\S+/g) || [];
        console.log("Text tokens:", tokens);
        for (const token of tokens) {
          console.log("Pushing token:", token);
          splitter.push(token);
          await new Promise((resolve) => setTimeout(resolve, 10)); // Keep delay between pushes
        }
        console.log("Finished pushing tokens, closing splitter.");
        splitter.close(); // Close after pushing all tokens
      } catch (e) {
        console.error("Text pushing error:", e);
        self.postMessage({ status: "error", error: e.message });
      }
    };

    // Function to consume stream and concatenate audio
    const consumeStream = async () => {
      console.log("Starting stream consumption (manual)...");
      const streamIterator = stream[Symbol.asyncIterator]();
      const audioChunks = [];
      let fullText = "";
      
      // Send initial loading state
      self.postMessage({ status: "stream_loading" });

      try {
        while (true) {
          console.log("Calling streamIterator.next()...");
          const { value: chunk, done } = await streamIterator.next();
          console.log(`streamIterator.next() returned: done=${done}`);

          if (done) {
            // Send final chunk when stream completes
            if (audioChunks.length > 0) {
              // Send final audio chunk
              const blob = await audioChunks[audioChunks.length-1].toBlob();
              const audioUrl = URL.createObjectURL(blob);
              
              self.postMessage({
                status: "stream_complete",
                audio: audioUrl,
                text: fullText.trim(),
                chunks: audioChunks.length,
                isFinal: true
              });
            } else {
              self.postMessage({ status: "stream_complete" });
            }
            break;
          }

          if (chunk) {
            const { text: chunkText, audio } = chunk;
            console.log("Processing chunk - Text:", chunkText);
            fullText += chunkText + " ";
            audioChunks.push(audio);
            
            // Create and send audio blob for this chunk
            const blob = await audio.toBlob();
            const audioUrl = URL.createObjectURL(blob);
            
            self.postMessage({
              status: "stream_progress",
              audio: audioUrl,
              text: fullText.trim(),
              chunkCount: audioChunks.length,
              isFinal: false
            });
          } else {
            console.warn("Stream yielded undefined/null value without being done.");
          }
        }
      } catch (error) {
        console.error("Error during stream consumption:", error);
        self.postMessage({ status: "error", error: error.message });
      }
    };

    // Start pushing text first
    pushText();

    // Give pushing a moment to start, then start consuming
    await new Promise(resolve => setTimeout(resolve, 50)); // Small delay before consuming
    consumeStream();
  }
});
