import re
from typing import Optional

import httpx
from rapidfuzz import fuzz

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
DEEZER_SEARCH_URL = "https://api.deezer.com/search"

# below that we desconsider the result
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
    #artist - song
    title = raw_title
    for pattern in NOISE_PATTERNS:
        title = re.sub(pattern, "", title, flags=re.IGNORECASE)
    title = title.strip(" -|_")

    for sep in [" - ", " – ", " | "]:
        if sep in title:
            artist, track = title.split(sep, 1)
            return artist.strip(), track.strip()

    return "", title.strip()


def _clean_channel_name(channel_name: str) -> str:

    #official channels have "topic" suffix or camelCase names
    name = re.sub(r"\s*-\s*Topic$", "", channel_name, flags=re.IGNORECASE).strip()

    #insert space in camelCase names
    name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)

    #remove sufixes
    noisy_suffixes = {"vevo", "official", "music", "tv", "records", "channel"}
    tokens = name.split()
    while len(tokens) > 1 and tokens[-1].lower() in noisy_suffixes:
        tokens.pop()

    return " ".join(tokens).strip()


def _classify_version(track_title: str, album_title: str) -> tuple[bool, bool]:

    #is_alt_recording: live, demo, radio edit, remix, acoustic, etc
    #is_compilation: greatest hits, best of, the collection, anthology
    text = f"{track_title} {album_title}".lower()

    alt_recording_markers = [
        "live", "ao vivo", "demo", "radio edit", "remix", "acoustic", "acústico",
        "instrumental", "karaoke", "tribute", "rehearsal", "alternate", "session",
        "extended", "mono version",
    ]
    is_alt_recording = any(re.search(rf"\b{re.escape(m)}\b", text) for m in alt_recording_markers)

    compilation_markers = ["greatest hits", "best of", "the collection", "anthology"]
    is_compilation = any(re.search(rf"\b{re.escape(m)}\b", text) for m in compilation_markers)

    if not is_alt_recording:
        #ignore parentheses of remaster and "single version" before checking
        stripped_title = re.sub(
            r"[\(\[]\s*remaster(ed)?\s*\d{0,4}\s*[\)\]]", "", track_title, flags=re.IGNORECASE
        )
        stripped_title = re.sub(
            r"[\(\[]\s*single version\s*[\)\]]", "", stripped_title, flags=re.IGNORECASE
        )
        if re.search(r"[\(\[][^\)\]]+[\)\]]", stripped_title):
            is_alt_recording = True

    return is_alt_recording, is_compilation


def _artist_plausible(score_artist: str, candidate_artist: str) -> bool:

    #additional check, check if at least one whole word is equal
    if not score_artist:
        return True

    score_tokens = set(re.findall(r"[a-z0-9]+", score_artist.casefold()))
    candidate_tokens = set(re.findall(r"[a-z0-9]+", candidate_artist.casefold()))

    if not score_tokens or not candidate_tokens:
        return True

    return bool(score_tokens & candidate_tokens)


def _score_candidate(candidate_artist: str, candidate_track: str, score_artist: str, track: str) -> tuple[float, float]:

    #calculate scores for artist and track separately, instead of a single combined string.
    track_score = fuzz.token_sort_ratio(track.casefold(), candidate_track.casefold())
    if score_artist:
        artist_score = fuzz.token_sort_ratio(score_artist.casefold(), candidate_artist.casefold())
    else:
        # Sem nenhuma pista de artista, não tem o que comparar — não penaliza.
        artist_score = 100
    return artist_score, track_score


MIN_ARTIST_SCORE = 45

MIN_TRACK_SCORE = 65


def _best_match(
    results: list, track: str, score_artist: str, source: str, allow_alt_version: bool
) -> Optional[dict]:

    
    candidates = []

    for r in results:
        if source == "itunes":
            candidate_artist = r.get("artistName", "")
            candidate_track = r.get("trackName", "")
            candidate_album = r.get("collectionName", "")
        else:
            candidate_artist = r.get("artist", {}).get("name", "")
            candidate_track = r.get("title", "")
            candidate_album = r.get("album", {}).get("title", "")

        artist_score, track_score = _score_candidate(candidate_artist, candidate_track, score_artist, track)

        if artist_score < MIN_ARTIST_SCORE or not _artist_plausible(score_artist, candidate_artist):
            continue 

        is_alt_recording, is_compilation = _classify_version(candidate_track, candidate_album)
        if is_alt_recording and not allow_alt_version:
            continue

        if track_score < MIN_TRACK_SCORE:
            continue

        combined_score = (artist_score * 0.35) + (track_score * 0.65)
        if combined_score < MIN_CONFIDENCE:
            continue

        candidates.append((combined_score, is_compilation, r))

    if not candidates:
        return None

    
    candidates.sort(key=lambda c: (c[1], -c[0]))
    best_score, _, best = candidates[0]

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


def search_deezer(
    query_artist: str, track: str, score_artist: str = "", allow_alt_version: bool = False
) -> Optional[dict]:
    query = f"{query_artist} {track}".strip()
    resp = httpx.get(DEEZER_SEARCH_URL, params={"q": query}, timeout=10)
    if resp.status_code != 200:
        return None
    return _best_match(
        resp.json().get("data", []), track, score_artist or query_artist, "deezer", allow_alt_version
    )


def search_itunes(
    query_artist: str, track: str, score_artist: str = "", allow_alt_version: bool = False
) -> Optional[dict]:
    query = f"{query_artist} {track}".strip()
    resp = httpx.get(
        ITUNES_SEARCH_URL,
        params={"term": query, "entity": "song", "limit": 5},
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    return _best_match(
        resp.json().get("results", []), track, score_artist or query_artist, "itunes", allow_alt_version
    )


def find_metadata(raw_title: str, artist_hint: str = "") -> Optional[dict]:

    #clear title and try to find metadata in Deezer first
    parsed_artist, track = clean_title(raw_title)
    cleaned_hint = _clean_channel_name(artist_hint) if artist_hint else ""

    #only accept an "alternative" result (live, demo, radio edit, remix, etc) if the
    #original title of the video on YouTube already indicated that
    allow_alt_version, _ = _classify_version(track, "")

    best_known_artist = parsed_artist or cleaned_hint

    attempts: list[tuple[str, str]] = []
    if parsed_artist:
        attempts.append((parsed_artist, parsed_artist))
    if cleaned_hint and cleaned_hint != parsed_artist:
        attempts.append((cleaned_hint, cleaned_hint))
    attempts.append(("", best_known_artist))

    for query_artist, score_artist in attempts:
        result = search_deezer(query_artist, track, score_artist, allow_alt_version)
        if result:
            return result

    for query_artist, score_artist in attempts:
        result = search_itunes(query_artist, track, score_artist, allow_alt_version)
        if result:
            return result

    return None