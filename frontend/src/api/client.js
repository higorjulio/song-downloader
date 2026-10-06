const API_BASE_URL = "http://localhost:8000";


function getFilenameFromResponse(response, fallback) {
  const disposition = response.headers.get("Content-Disposition");
  if (!disposition) return fallback;

  const match = disposition.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  if (!match) return fallback;

  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}


export async function downloadFromUrl(youtubeUrl) {
  const response = await fetch(`${API_BASE_URL}/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: youtubeUrl }),
  });

  if (!response.ok) {
    let message = "Error downloading";
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {
        
    }
    throw new Error(message);
  }

  const isZip = response.headers.get("Content-Type")?.includes("zip");
  const fallbackName = isZip ? "playlist.zip" : "audio.mp3";

  const blob = await response.blob();
  const filename = getFilenameFromResponse(response, fallbackName);

  return { blob, filename, isPlaylist: isZip };
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