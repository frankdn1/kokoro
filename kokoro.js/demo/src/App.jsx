import { useRef, useState, useEffect } from "react";
import { motion } from "motion/react";

export default function App() {
  // Create a reference to the worker object.
  const worker = useRef(null);

  const [inputText, setInputText] = useState("Life is like a box of chocolates. You never know what you're gonna get.");
  const [selectedSpeaker, setSelectedSpeaker] = useState("af_heart");
  const audioRef = useRef(null);
  const [streamStatus, setStreamStatus] = useState('idle'); // 'idle'|'loading'|'streaming'|'complete'
  const [currentAudioUrl, setCurrentAudioUrl] = useState(null);

  const [voices, setVoices] = useState([]);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [loadingMessage, setLoadingMessage] = useState("Loading...");

  const [results, setResults] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [audioQueue, setAudioQueue] = useState([]);
  const [isPlaying, setIsPlaying] = useState(false);

  // We use the `useEffect` hook to setup the worker as soon as the `App` component is mounted.
  useEffect(() => {
    // Create the worker if it does not yet exist.
    worker.current ??= new Worker(new URL("./worker.js", import.meta.url), {
      type: "module",
    });

    // Create a callback function for messages from the worker thread.
    const onMessageReceived = (e) => {
      console.log("Worker message received:", e.data);
      switch (e.data.status) {
        case "device":
          setLoadingMessage(`Loading model (device="${e.data.device}")`);
          break;
        case "ready":
          setStatus("ready");
          setVoices(e.data.voices);
          break;
        case "error":
          setError(e.data.data);
          break;
        case "complete":
          const { audio, text } = e.data;
          setResults((prev) => [{ text, src: audio }, ...prev]);
          setStatus("ready");
          break;
        case "stream_loading":
          setLoadingMessage("Processing audio stream...");
          break;
        case "stream_progress":
          console.log("Stream progress:", e.data);
          setStreamStatus('streaming');
          setCurrentAudioUrl(e.data.audio);
          
          // Add new audio chunk to queue
          setAudioQueue(prev => [...prev, e.data.audio]);
          
          // Initialize audio element if needed
          if (!audioRef.current) {
            audioRef.current = new Audio();
            audioRef.current.addEventListener('ended', () => {
              // Play next chunk if available
              const nextChunk = audioQueue[0];
              if (nextChunk) {
                setAudioQueue(prev => prev.slice(1));
                audioRef.current.src = nextChunk;
                audioRef.current.play().catch(e => console.error("Audio play error:", e));
              } else {
                setIsPlaying(false);
                setStreamStatus('complete');
              }
            });
            
            // Start playing first chunk
            audioRef.current.src = e.data.audio;
            audioRef.current.play().catch(e => console.error("Audio play error:", e));
          }
          break;
        case "stream_complete":
          console.log("Stream completed");
          setStreaming(false);
          setStatus("ready");
          // Keep the player visible after completion
          if (e.data.audio) {
            setCurrentAudioUrl(e.data.audio);
            setStreamStatus('complete');
          }
          break;
      }
    };

    const onErrorReceived = (e) => {
      console.error("Worker error:", e);
      setError(e.message);
    };

    // Attach the callback function as an event listener.
    worker.current.addEventListener("message", onMessageReceived);
    worker.current.addEventListener("error", onErrorReceived);

    // Define a cleanup function for when the component is unmounted.
    return () => {
      worker.current.removeEventListener("message", onMessageReceived);
      worker.current.removeEventListener("error", onErrorReceived);
    };
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    setStatus("running");

    worker.current.postMessage({
      type: "generate",
      text: inputText.trim(),
      voice: selectedSpeaker,
    });
  };


  const handleStream = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setCurrentAudioUrl(null);
    setAudioQueue([]);
    setIsPlaying(false);
    setStreamStatus('loading');
    setStreaming(true);
    setStatus("running");
    setLoadingMessage("Starting stream...");
    worker.current.postMessage({
      type: "stream",
      text: inputText.trim(),
      voice: selectedSpeaker,
    });
  };

  const handleStop = () => {
    setStreaming(false);
    setStatus("ready");
    // Worker will handle cleanup when stream completes
  };

  return (
    <div className="relative w-full min-h-screen bg-gradient-to-br from-gray-900 to-gray-700 flex flex-col items-center justify-center p-4 relative overflow-hidden font-sans">
      <motion.div initial={{ opacity: 1 }} animate={{ opacity: status === null ? 1 : 0 }} transition={{ duration: 0.5 }} className="absolute w-screen h-screen justify-center flex flex-col items-center z-10 bg-gray-800/95 backdrop-blur-md" style={{ pointerEvents: status === null ? "auto" : "none" }}>
        <div className="w-[250px] h-[250px] border-4 border-white shadow-[0_0_0_5px_#4973ff] rounded-full overflow-hidden">
          <div className="loading-wave"></div>
        </div>
        <p className={`text-3xl my-5 text-center ${error ? "text-red-500" : "text-white"}`}>{error ?? loadingMessage}</p>
      </motion.div>

      <div className="max-w-3xl w-full space-y-8 relative z-[2]">
        <div className="text-center">
          <h1 className="text-5xl font-extrabold text-gray-100 mb-2 drop-shadow-lg font-heading">Kokoro Text-to-Speech</h1>
          <p className="text-2xl text-gray-300 font-semibold font-subheading">
            Powered by&nbsp;
            <a href="https://github.com/hexgrad/kokoro" target="_blank" rel="noreferrer" className="underline">
              Kokoro
            </a>
            &nbsp;and&nbsp;
            <a href="https://huggingface.co/docs/transformers.js" target="_blank" rel="noreferrer" className="underline">
              <img width="40" src="hf-logo.svg" className="inline translate-y-[-2px] me-1"></img>Transformers.js
            </a>
          </p>
        </div>
        <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-lg p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <textarea placeholder="Enter text..." value={inputText} onChange={(e) => setInputText(e.target.value)} className="w-full min-h-[100px] max-h-[300px] bg-gray-700/50 backdrop-blur-sm border-2 border-gray-600 rounded-xl resize-y text-gray-100 placeholder-gray-400 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" rows={Math.min(8, inputText.split("\n").length)} />
            <div className="flex flex-col items-center space-y-4">
              <select value={selectedSpeaker} onChange={(e) => setSelectedSpeaker(e.target.value)} className="w-full bg-gray-700/50 backdrop-blur-sm border-2 border-gray-600 rounded-xl text-gray-100 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                {Object.entries(voices).map(([id, voice]) => (
                  <option key={id} value={id}>
                    {voice.name} ({voice.language === "en-us" ? "American" : "British"} {voice.gender})
                  </option>
                ))}
              </select>
              <div className="flex space-x-4">
                <button type="submit" className="inline-flex justify-center items-center px-6 py-2 text-lg font-semibold bg-gradient-to-t from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 transition-colors duration-300 rounded-xl text-white disabled:opacity-50" disabled={status === "running" || inputText.trim() === ""}>
                  {status === "running" && !streaming ? "Generating..." : "Generate"}
                </button>
                {!streaming ? (
                  <button type="button" onClick={handleStream} className="inline-flex justify-center items-center px-6 py-2 text-lg font-semibold bg-gradient-to-t from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700 transition-colors duration-300 rounded-xl text-white disabled:opacity-50" disabled={status === "running" || inputText.trim() === ""}>
                    Stream
                  </button>
                ) : (
                  <button type="button" onClick={handleStop} className="inline-flex justify-center items-center px-6 py-2 text-lg font-semibold bg-gradient-to-t from-red-600 to-orange-600 hover:from-red-700 hover:to-orange-700 transition-colors duration-300 rounded-xl text-white">
                    Stop
                  </button>
                )}
              </div>
            </div>
          </form>
        </div>

        {/* Audio player section - always visible once streaming starts */}
        {(streamStatus === 'loading' || streamStatus === 'streaming' || streamStatus === 'complete') && (
          <motion.div
            initial={{ y: 50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.5 }}
            className="bg-gray-800/70 backdrop-blur-sm border border-gray-700 rounded-lg p-4"
          >
            <h3 className="text-white mb-2">
              {streamStatus === 'loading' ? 'Loading...' :
               streamStatus === 'streaming' ? 'Streaming Audio' :
               'Stream Complete'}
            </h3>
            
            {streamStatus === 'loading' ? (
              <p className="text-gray-300">Processing audio stream...</p>
            ) : currentAudioUrl ? (
              <audio
                controls
                src={currentAudioUrl}
                className="w-full"
                autoPlay
              />
            ) : null}
          </motion.div>
        )}

        {results.length > 0 && (
          <motion.div initial={{ y: 50, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.5 }} className="max-h-[250px] overflow-y-auto px-2 mt-4 space-y-6 relative z-[2]">
            {results.map((result, i) => (
              <div key={i}>
                <div className="text-white bg-gray-800/70 backdrop-blur-sm border border-gray-700 rounded-lg p-4 z-10">
                  <span className="absolute right-5 font-bold">#{results.length - i}</span>
                  <p className="mb-3 max-w-[95%]">{result.text}</p>
                  <audio controls src={result.src} className="w-full">
                    Your browser does not support the audio element.
                  </audio>
                </div>
              </div>
            ))}
          </motion.div>
        )}
      </div>

      <div className="bg-[#015871] pointer-events-none absolute left-0 w-full h-[5%] bottom-[-50px]">
        <div className="wave"></div>
        <div className="wave"></div>
      </div>
    </div>
  );
}
