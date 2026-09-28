import re
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services.downloader import (
    download_track,
    tag_track,
    extract_playlist_entries,
    DOWNLOAD_DIR,
)
from services.cleanup import delete_file_later

router = APIRouter(prefix="/download", tags=["download"])


class DownloadRequest(BaseModel):
    url: str


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "", name).strip() or "audio"


@router.post("")
def download(payload: DownloadRequest):
    try:
        entries = extract_playlist_entries(payload.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error trying to read link: {e}")

    if not entries:
        raise HTTPException(status_code=400, detail="No content found")

    if len(entries) == 1:
        return _download_single(entries[0]["url"])

    return _download_playlist(entries)


def _download_single(url: str) -> FileResponse:
    try:
        file_path, info = download_track(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {e}")

    tag_track(file_path, info)

    filename = f"{info.get('title', 'audio')}.mp3"
    delete_file_later(file_path)

    return FileResponse(file_path, media_type="audio/mpeg", filename=filename)


def _download_playlist(entries: list[dict]) -> FileResponse:
    downloaded_files: list[tuple[Path, str]] = []
    failed_tracks: list[str] = []

    for entry in entries:
        try:
            file_path, info = download_track(entry["url"])
            tag_track(file_path, info)
            title = info.get("title") or entry.get("title") or file_path.stem
            downloaded_files.append((file_path, title))
        except Exception:
            failed_tracks.append(entry.get("title") or entry["url"])
            continue

    if not downloaded_files:
        raise HTTPException(status_code=400, detail="No tracks could be downloaded successfully")

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

        #delete each file after adding to zip
        for file_path, _ in downloaded_files:
            file_path.unlink(missing_ok=True)

    delete_file_later(zip_path)

    return FileResponse(zip_path, media_type="application/zip", filename="playlist.zip")