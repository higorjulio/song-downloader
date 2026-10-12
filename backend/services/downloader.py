import os
import re
import time
import uuid
import zipfile
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from services import metadata as metadata_service
from services import tagger

DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

_COOKIES_FILE = os.environ.get("YTDLP_COOKIES_FILE", str(Path(__file__).resolve().parent.parent / "cookies.txt"))


def _cookies_opts() -> dict:
    if os.path.isfile(_COOKIES_FILE):
        return {"cookiefile": _COOKIES_FILE}
    return {}


_PLAYER_CLIENTS = ["android", "ios", "web", "tv"]

# How many extra attempts to make if every client fails on the first pass
_RETRY_ROUNDS = 2
_RETRY_DELAY_SECONDS = 5


def _is_bot_check_error(error: Exception) -> bool:
    text = str(error).lower()
    return "sign in to confirm" in text or "http error 403" in text


def _run_with_client_fallback(build_opts: Callable[[str], dict], run: Callable[[dict], dict]) -> dict:
    last_error: Optional[Exception] = None

    for round_index in range(_RETRY_ROUNDS):
        for client in _PLAYER_CLIENTS:
            try:
                return run(build_opts(client))
            except Exception as e:
                last_error = e
                if not _is_bot_check_error(e):
                    raise
                continue

        if round_index < _RETRY_ROUNDS - 1:
            time.sleep(_RETRY_DELAY_SECONDS)

    raise last_error


def download_track(
    url: str, on_progress: Optional[Callable[[float], None]] = None
) -> tuple[Path, dict]:
    file_id = str(uuid.uuid4())
    output_template = str(DOWNLOAD_DIR / f"{file_id}.%(ext)s")

    def progress_hook(d: dict) -> None:
        if on_progress is None:
            return
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            downloaded = d.get("downloaded_bytes", 0)
            on_progress(downloaded / total * 100)
        elif d["status"] == "finished":
            on_progress(100)

    def build_opts(player_client: str) -> dict:
        return {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "noprogress": True,
            "progress_hooks": [progress_hook] if on_progress else [],
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }
            ],
            "extractor_args": {"youtube": {"player_client": [player_client]}},
            **_cookies_opts(),
        }

    def run(opts: dict) -> dict:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True)

    info = _run_with_client_fallback(build_opts, run)

    final_path = DOWNLOAD_DIR / f"{file_id}.mp3"
    if not final_path.exists():
        raise RuntimeError("File was not generated")

    return final_path, info


def tag_track(file_path: Path, info: dict) -> dict | None:
    video_title = info.get("title", "")
    channel_name = info.get("uploader", "") or info.get("channel", "")

    found_metadata = metadata_service.find_metadata(video_title, artist_hint=channel_name)
    if found_metadata:
        tagger.apply_tags(file_path, found_metadata)

    return found_metadata


def extract_playlist_entries(url: str) -> list[dict]:
    def build_opts(player_client: str) -> dict:
        return {
            "quiet": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "extractor_args": {"youtube": {"player_client": [player_client]}},
            **_cookies_opts(),
        }

    def run(opts: dict) -> dict:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    info = _run_with_client_fallback(build_opts, run)

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


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "", name).strip() or "audio"


def build_zip(downloaded_files: list[tuple[Path, str]]) -> Path:
    zip_id = str(uuid.uuid4())
    zip_path = DOWNLOAD_DIR / f"{zip_id}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
        used_names: set[str] = set()
        for file_path, title in downloaded_files:
            name = _safe_filename(title) + ".mp3"
            base_name = name
            counter = 1
            while name in used_names:
                name = f"{Path(base_name).stem} ({counter}).mp3"
                counter += 1
            used_names.add(name)

            zf.write(file_path, arcname=name)

        for file_path, _ in downloaded_files:
            file_path.unlink(missing_ok=True)

    return zip_path