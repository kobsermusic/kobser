from collections.abc import Callable, Iterable
from pathlib import Path

from mutagen import File as MutagenFile

DEFAULT_ALBUM = "Singles"


def tag(file_path: str, artist: str, title: str, album: str = DEFAULT_ALBUM) -> None:
    """Write artist/title plus albumartist/album tags.

    Navidrome's getArtists endpoint indexes by album artist. If only the track
    `artist` is written, new artists don't appear in the Library browse view,
    though search3 still finds them. We set albumartist = artist, and album
    defaults to "Singles", so each standalone download is grouped under the
    artist's own "Singles" album."""
    audio = MutagenFile(file_path, easy=True)
    if audio is None:
        return
    audio["artist"] = artist
    audio["title"] = title
    audio["album"] = album
    audio["albumartist"] = artist
    audio.save()


AUDIO_EXTENSIONS = {".m4a", ".mp3", ".flac", ".opus", ".ogg", ".webm", ".wav", ".aac", ".wma", ".aiff"}


def read_title_artist(file_path: str) -> tuple[str, str] | None:
    """Return (title, artist) from a file's tags, or None if they can't be read."""
    try:
        audio = MutagenFile(file_path, easy=True)
    except Exception:
        return None
    if audio is None or audio.tags is None:
        return None
    title = (audio.tags.get("title") or [""])[0]
    artist = (audio.tags.get("artist") or audio.tags.get("albumartist") or [""])[0]
    return title, artist


def find_file_by_tags(
    folders: Iterable[Path],
    title: str,
    artist: str,
    norm: Callable[[str], str],
    read_tags: Callable[[str], tuple[str, str] | None] = read_title_artist,
    max_depth: int = 2,
) -> Path | None:
    """Find the audio file in `folders` (and up to `max_depth` levels below) whose
    tags match `title` (and `artist`, when the file has one). Used when a track's
    file doesn't follow kobser's "Artist - Title" naming, e.g. music added by hand."""
    want_title, want_artist = norm(title), norm(artist)
    if not want_title:
        return None
    for folder in folders:
        if not folder.is_dir():
            continue
        base_depth = len(folder.parts)
        for path in sorted(folder.rglob("*")):
            if len(path.parts) - base_depth > max_depth or path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            tags = read_tags(str(path))
            if not tags:
                continue
            t, a = tags
            if norm(t) == want_title and (not a or not want_artist or norm(a) == want_artist):
                return path
    return None
