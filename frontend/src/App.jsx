import { useState } from "react";
import { useDownload } from "./hooks/useDownload";
import "./App.css";

const STATUS_LABELS = {
  starting: "Starting...",
  fetching_info: "Reading link...",
  downloading: "Downloading...",
  tagging: "Applying tags...",
  zipping: "Zipping playlist...",
};

function App() {
  const [url, setUrl] = useState("");
  const { state, start } = useDownload();

  const isBusy = state.status !== "idle" && state.status !== "error";

  function handleSubmit(e) {
    e.preventDefault();
    if (!url.trim() || isBusy) return;
    start(url.trim());
  }

  return (
    <div className="app">
      <h1>YT Music Downloader</h1>
      <p className="subtitle">Paste a YouTube video or playlist link</p>

      <form onSubmit={handleSubmit} className="download-form">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.youtube.com/watch?v=..."
          disabled={isBusy}
        />
        <button type="submit" disabled={isBusy || !url.trim()}>
          {isBusy ? "Downloading..." : "Download"}
        </button>
      </form>

      {isBusy && (
        <div className="progress-box">
          <p className="progress-label">
            {state.total_tracks
              ? `Track ${state.current_index}/${state.total_tracks}${
                  state.current_title ? ` — ${state.current_title}` : ""
                }`
              : STATUS_LABELS[state.status] || "Processing..."}
          </p>
          <div className="progress-bar">
            <div
              className="progress-bar-fill"
              style={{ width: `${state.percent ?? 0}%` }}
            />
          </div>
          {state.total_tracks && (
            <p className="progress-sub">{STATUS_LABELS[state.status]}</p>
          )}
        </div>
      )}

      {state.status === "error" && <p className="error">{state.error}</p>}
    </div>
  );
}

export default App;