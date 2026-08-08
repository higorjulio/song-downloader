import os
import uuid

from yt_dlp import YoutubeDL
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="YT Music Downloader")

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# LEMBRAR DE CRIAR PASTA ROUTES E CONFIGURAR

class DownloadRequest(BaseModel):
    url: str


@app.post("/download")
def download(payload: DownloadRequest):
    file_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

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

    final_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp3")

    if not os.path.exists(final_path):
        raise HTTPException(status_code=500, detail="Arquivo não foi gerado")

    filename = f"{info.get('title', 'audio')}.mp3"
    return FileResponse(final_path, media_type="audio/mpeg", filename=filename)