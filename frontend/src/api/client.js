const API_BASE_URL = "http://localhost:8000";
const WS_BASE_URL = "ws://localhost:8000";

export async function startDownload(youtubeUrl) {
  const response = await fetch(`${API_BASE_URL}/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: youtubeUrl }),
  });

  if (!response.ok) {
    let message = "Failed to start the download";
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {
      // response wasn't JSON, keep the generic message
    }
    throw new Error(message);
  }

  const { job_id } = await response.json();
  return job_id;
}

/**
 * Opens a WebSocket connection for the job and calls `onMessage` on every
 * progress event received. Returns the cleanup function (closes the socket).
 *
 * Shape of the events the backend sends (fields vary by status):
 *   { status: "fetching_info" }
 *   { status: "downloading", percent, current_index?, total_tracks?, current_title? }
 *   { status: "tagging" | "zipping", percent }
 *   { status: "done", file_path, filename }
 *   { status: "error", error }
 */
export function watchProgress(jobId, onMessage) {
  const socket = new WebSocket(`${WS_BASE_URL}/ws/${jobId}`);

  socket.onmessage = (event) => {
    onMessage(JSON.parse(event.data));
  };

  return () => socket.close();
}

/**
 * Fetches the final file for an already-finished job (status "done") and
 * returns { blob, filename }. Only call this after receiving the "done" event.
 */
export async function fetchJobFile(jobId) {
  const response = await fetch(`${API_BASE_URL}/download/file/${jobId}`);

  if (!response.ok) {
    throw new Error("Failed to fetch the finished file");
  }

  const disposition = response.headers.get("Content-Disposition");
  const match = disposition?.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  const filename = match ? decodeURIComponent(match[1]) : "download";

  const blob = await response.blob();
  return { blob, filename };
}

export function saveBlobAsFile(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}