import re
from typing import Optional

import httpx
from rapidfuzz import fuzz

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
DEEZER_SEARCH_URL = "https://api.deezer.com/search"

#abaixo disso, so descarta
MIN_CONFIDENCE = 60

NOISE_PATTERNS = [
    r"\(official.*?\)",
    r"\[official.*?\]",
    r"\(lyrics?.*?\)",
    r"\[lyrics?.*?\]",
    r"\(audio\)",
    r"\[audio\]",
    r"\(hd\)",
    r"\[hd\]",
    r"official video",
    r"official music video",
    r"lyric video",
]


def clean_title(raw_title: str) -> tuple[str, str]:
    title = raw_title
    for pattern in NOISE_PATTERNS:
        title = re.sub(pattern, "", title, flags=re.IGNORECASE)
    title = title.strip(" -|_")

    for sep in [" - ", " – ", " | "]:
        if sep in title:
            artist, track = title.split(sep, 1)
            return artist.strip(), track.strip()

    return "", title.strip()


def _best_match(results: list, artist: str, track: str, source: str) -> Optional[dict]:
    best = None
    best_score = 0

    for r in results:
        if source == "itunes":
            candidate_artist = r.get("artistName", "")
            candidate_track = r.get("trackName", "")
        else:  # deezer
            candidate_artist = r.get("artist", {}).get("name", "")
            candidate_track = r.get("title", "")

        score = fuzz.token_sort_ratio(
            f"{artist} {track}", f"{candidate_artist} {candidate_track}"
        )
        if score > best_score:
            best_score = score
            best = r

    if best is None or best_score < MIN_CONFIDENCE:
        return None

    if source == "itunes":
        return {
            "title": best.get("trackName"),
            "artist": best.get("artistName"),
            "album": best.get("collectionName"),
            "cover_url": (best.get("artworkUrl100") or "").replace("100x100", "600x600"),
            "year": (best.get("releaseDate") or "")[:4],
            "genre": best.get("primaryGenreName"),
            "confidence": best_score,
        }
    else:
        return {
            "title": best.get("title"),
            "artist": best.get("artist", {}).get("name"),
            "album": best.get("album", {}).get("title"),
            "cover_url": best.get("album", {}).get("cover_xl")
            or best.get("album", {}).get("cover_big"),
            "year": None,
            "genre": None,
            "confidence": best_score,
        }


def search_itunes(artist: str, track: str) -> Optional[dict]:
    query = f"{artist} {track}".strip()
    resp = httpx.get(
        ITUNES_SEARCH_URL,
        params={"term": query, "entity": "song", "limit": 5},
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    return _best_match(resp.json().get("results", []), artist, track, source="itunes")


def search_deezer(artist: str, track: str) -> Optional[dict]:
    query = f"{artist} {track}".strip()
    resp = httpx.get(DEEZER_SEARCH_URL, params={"q": query}, timeout=10)
    if resp.status_code != 200:
        return None
    return _best_match(resp.json().get("data", []), artist, track, source="deezer")


def find_metadata(raw_title: str, artist_hint: str = "") -> Optional[dict]:

    #Tenta achar no Deezer, se nao achar, vai pro iTunes
    #artist_hint é o nome do canal do YouTube
    artist, track = clean_title(raw_title)

    if not artist and artist_hint:
        artist = _clean_channel_name(artist_hint)

    result = search_deezer(artist, track)
    if result:
        return result

    return search_itunes(artist, track)


def _clean_channel_name(channel_name: str) -> str:
    return re.sub(r"\s*-\s*Topic$", "", channel_name, flags=re.IGNORECASE).strip() 