import threading
import uuid
from pathlib import Path

import yt_dlp
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services import metadata as metadata_service
from services import tagger

router = APIRouter(prefix="/download", tags=["download"])

DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

#DELETAR DOWNLOAD APOS 10M
FILE_TTL_SECONDS = 10 * 60  # 10 minutos


def delete_file_later(file_path: Path, delay_seconds: int) -> None:

    def _delete():
        if file_path.exists():
            file_path.unlink()

    timer = threading.Timer(delay_seconds, _delete)
    timer.daemon = True
    timer.start()

class DownloadRequest(BaseModel):
    url: str


@router.post("")
def download(payload: DownloadRequest):
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

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(payload.url, download=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao baixar: {e}")

    final_path = DOWNLOAD_DIR / f"{file_id}.mp3"

    if not final_path.exists():
        raise HTTPException(status_code=500, detail="Arquivo não foi gerado")

    video_title = info.get("title", "")
    channel_name = info.get("uploader", "") or info.get("channel", "")
    found_metadata = metadata_service.find_metadata(video_title, artist_hint=channel_name)
    if found_metadata:
        tagger.apply_tags(final_path, found_metadata)

    filename = f"{info.get('title', 'audio')}.mp3"

    delete_file_later(final_path, FILE_TTL_SECONDS)

    return FileResponse(final_path, media_type="audio/mpeg", filename=filename)