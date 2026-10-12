import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services import jobs as jobs_service
from services.cleanup import delete_file_later
from services.downloader import (
    build_zip,
    download_track,
    extract_playlist_entries,
    tag_track,
)
from services.ws_manager import manager

router = APIRouter(tags=["download"])


class DownloadRequest(BaseModel):
    url: str


@router.post("/download")
async def start_download(payload: DownloadRequest):
    job_id = jobs_service.create_job()
    asyncio.create_task(_run_job(job_id, payload.url))
    return {"job_id": job_id}


@router.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await manager.connect(job_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(job_id)


@router.get("/download/file/{job_id}")
def get_file(job_id: str):
    job = jobs_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "done":
        raise HTTPException(status_code=409, detail="File still not ready for download")

    file_path = job["file_path"]
    filename = job["filename"]
    media_type = "application/zip" if filename.endswith(".zip") else "audio/mpeg"

    delete_file_later(file_path)

    return FileResponse(file_path, media_type=media_type, filename=filename)


async def _run_job(job_id: str, url: str) -> None:
    loop = asyncio.get_event_loop()

    async def report(**fields) -> None:
        job = jobs_service.update_job(job_id, **fields)
        await manager.send_progress(job_id, job)

    try:
        await report(status="fetching_info")
        entries = await loop.run_in_executor(None, extract_playlist_entries, url)

        if not entries:
            await report(status="error", error="No content found at the provided URL")
            return

        if len(entries) == 1:
            await _run_single(job_id, entries[0]["url"], loop, report)
        else:
            await _run_playlist(job_id, entries, loop, report)

    except Exception as e:
        await report(status="error", error=str(e))


async def _run_single(job_id: str, url: str, loop, report) -> None:
    def on_progress(percent: float) -> None:
        asyncio.run_coroutine_threadsafe(
            report(status="downloading", percent=percent), loop
        )

    file_path, info = await loop.run_in_executor(
        None, lambda: download_track(url, on_progress=on_progress)
    )

    await report(status="tagging", percent=100)
    await loop.run_in_executor(None, tag_track, file_path, info)

    filename = f"{info.get('title', 'audio')}.mp3"
    await report(status="done", file_path=str(file_path), filename=filename)


async def _run_playlist(job_id: str, entries: list[dict], loop, report) -> None:
    total = len(entries)
    downloaded_files: list[tuple] = []

    for index, entry in enumerate(entries, start=1):
        await report(
            status="downloading",
            percent=0,
            current_index=index,
            total_tracks=total,
            current_title=entry.get("title"),
        )

        def on_progress(percent: float, idx=index) -> None:
            asyncio.run_coroutine_threadsafe(
                report(
                    status="downloading",
                    percent=percent,
                    current_index=idx,
                    total_tracks=total,
                    current_title=entry.get("title"),
                ),
                loop,
            )

        try:
            file_path, info = await loop.run_in_executor(
                None, lambda: download_track(entry["url"], on_progress=on_progress)
            )
            await loop.run_in_executor(None, tag_track, file_path, info)
            title = info.get("title") or entry.get("title") or file_path.stem
            downloaded_files.append((file_path, title))
        except Exception:
            continue

    if not downloaded_files:
        await report(status="error", error="No tracks could be downloaded from the provided playlist")
        return

    await report(status="zipping", percent=100, current_index=total, total_tracks=total)
    zip_path = await loop.run_in_executor(None, build_zip, downloaded_files)

    await report(status="done", file_path=str(zip_path), filename="playlist.zip")