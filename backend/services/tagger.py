from pathlib import Path
from typing import Optional

import httpx
from mutagen.id3 import ID3, ID3NoHeaderError, APIC, TIT2, TPE1, TALB, TDRC, TCON


def apply_tags(file_path: Path, metadata: dict) -> None:
    try:
        tags = ID3(file_path)
    except ID3NoHeaderError:
        tags = ID3()

    if metadata.get("title"):
        tags["TIT2"] = TIT2(encoding=3, text=metadata["title"])
    if metadata.get("artist"):
        tags["TPE1"] = TPE1(encoding=3, text=metadata["artist"])
    if metadata.get("album"):
        tags["TALB"] = TALB(encoding=3, text=metadata["album"])
    if metadata.get("year"):
        tags["TDRC"] = TDRC(encoding=3, text=str(metadata["year"]))
    if metadata.get("genre"):
        tags["TCON"] = TCON(encoding=3, text=metadata["genre"])

    cover_url = metadata.get("cover_url")
    if cover_url:
        _embed_cover(tags, cover_url)

    # v2_version=3 força ID3v2.3 em vez do padrão v2.4 do mutagen. O windows nao exibe capas na versao 2.4
    tags.save(file_path, v2_version=3)


def _embed_cover(tags: ID3, cover_url: str) -> None:
    resp = httpx.get(cover_url, timeout=10, follow_redirects=True)
    if resp.status_code != 200:
        return
    content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()

    tags["APIC"] = APIC(
        encoding=3,
        mime=content_type,
        type=3,  # capa de álbum (front cover)
        desc="Cover",
        data=resp.content,
    )