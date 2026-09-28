import uuid
from pathlib import Path

import yt_dlp

from services import metadata as metadata_service
from services import tagger

DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def download_track(url: str) -> tuple[Path, dict]:
    file_id = str(uuid.uuid4())
    output_template = str(DOWNLOAD_DIR / f"{file_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "quiet": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    final_path = DOWNLOAD_DIR / f"{file_id}.mp3"
    if not final_path.exists():
        raise RuntimeError("File not found after download.")

    return final_path, info


def tag_track(file_path: Path, info: dict) -> dict | None:
    video_title = info.get("title", "")
    channel_name = info.get("uploader", "") or info.get("channel", "")

    found_metadata = metadata_service.find_metadata(video_title, artist_hint=channel_name)
    if found_metadata:
        tagger.apply_tags(file_path, found_metadata)

    return found_metadata


def extract_playlist_entries(url: str) -> list[dict]:
    opts = {
        "quiet": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if info.get("_type") == "playlist":
        return [
            {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "url": entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}",
            }
            for entry in info.get("entries", [])
            if entry
        ]

    return [{"id": info.get("id"), "title": info.get("title"), "url": url}]