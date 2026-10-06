import { useState } from "react";
import { downloadFromUrl, saveBlobAsFile } from "./api/client";
import "./App.css";

function App() {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState("idle"); // idle | loading | error
  const [errorMessage, setErrorMessage] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    if (!url.trim()) return;

    setStatus("loading");
    setErrorMessage("");

    try {
      const { blob, filename } = await downloadFromUrl(url.trim());
      saveBlobAsFile(blob, filename);
      setStatus("idle");
      setUrl("");
    } catch (err) {
      setStatus("error");
      setErrorMessage(err.message);
    }
  }

  return (
    <div className="app">
      <h1>Song Downloader</h1>
      <p className="subtitle">Paste a video or a playlist link from Youtube</p>

      <form onSubmit={handleSubmit} className="download-form">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.youtube.com/watch?v=..."
          disabled={status === "loading"}
        />
        <button type="submit" disabled={status === "loading" || !url.trim()}>
          {status === "loading" ? "Downloading..." : "Download"}
        </button>
      </form>

      {status === "error" && <p className="error">{errorMessage}</p>}
    </div>
  );
}

export default App;