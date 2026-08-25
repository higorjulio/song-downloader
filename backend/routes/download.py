import uuid
from pathlib import Path

from yt_dlp import YoutubeDL
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/download", tags=["download"])

DOWNLOAD_DIR = Path(__file__).parent.parent / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


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
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(payload.url, download=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao baixar: {e}")

    final_path = DOWNLOAD_DIR / f"{file_id}.mp3"

    if not final_path.exists():
        raise HTTPException(status_code=500, detail="Arquivo não foi gerado")

    filename = f"{info.get('title', 'audio')}.mp3"
    return FileResponse(final_path, media_type="audio/mpeg", filename=filename)