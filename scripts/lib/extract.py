"""Caption, OCR, then Whisper — in that order."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from lib.fetch import FetchResult

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTS = {".mp4", ".m4v", ".mov", ".webm", ".mkv"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"}


@dataclass
class ExtractResult:
    caption: str = ""
    ocr_text: str = ""
    transcript: str = ""
    sources_used: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def combined_text(self) -> str:
        parts = [self.caption, self.ocr_text, self.transcript]
        return "\n\n".join(p.strip() for p in parts if p.strip())


def extract_text(
    fetched: FetchResult,
    *,
    caption_override: str | None = None,
    skip_media: bool = False,
) -> ExtractResult:
    result = ExtractResult()
    caption = (caption_override or fetched.caption or "").strip()
    if caption_override and caption_override.strip():
        result.sources_used.append("user-paste")
        result.caption = caption
    elif caption:
        result.sources_used.append("caption")
        result.caption = caption

    if skip_media:
        if result.caption:
            result.skipped.extend(["ocr", "whisper"])
        result.sources_used = _unique(result.sources_used)
        result.skipped = _unique(result.skipped)
        return result

    images = list(fetched.images)
    videos = list(fetched.videos)
    if images:
        ocr = _ocr_images(images)
        if ocr.text:
            result.ocr_text = ocr.text
            result.sources_used.append("ocr")
        result.skipped.extend(ocr.skipped)
    elif videos:
        # Stills-only OCR is skipped when there are no image files.
        pass

    if videos:
        whisper = _whisper_videos(videos)
        if whisper.text:
            result.transcript = whisper.text
            result.sources_used.append("whisper")
        result.skipped.extend(whisper.skipped)

    result.sources_used = _unique(result.sources_used)
    result.skipped = _unique(result.skipped)
    return result


@dataclass
class _Piece:
    text: str = ""
    skipped: list[str] = field(default_factory=list)


def _ocr_images(images: list[Path]) -> _Piece:
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return _Piece(skipped=["ocr: install pillow and pytesseract, plus Tesseract OCR"])

    if shutil.which("tesseract") is None:
        return _Piece(skipped=["ocr: tesseract binary not found on PATH"])

    chunks: list[str] = []
    for path in images:
        if path.suffix.lower() not in IMAGE_EXTS:
            continue
        try:
            text = pytesseract.image_to_string(Image.open(path))
        except Exception as exc:  # noqa: BLE001 — OCR should never abort the run
            return _Piece(text="\n".join(chunks).strip(), skipped=[f"ocr: {exc}"])
        if text.strip():
            chunks.append(text.strip())
    return _Piece(text="\n\n".join(chunks).strip())


def _whisper_videos(videos: list[Path]) -> _Piece:
    media = videos[0]
    audio = _ensure_audio(media)
    if audio.skipped:
        return audio

    path = Path(audio.text)
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    faster = _whisper_faster(path)
    if faster.text:
        return faster
    skipped = list(faster.skipped)

    if api_key:
        api = _whisper_openai(path)
        if api.text:
            return api
        skipped.extend(api.skipped)
    elif any("faster-whisper not installed" in item for item in skipped):
        skipped.append("whisper: set OPENAI_API_KEY or install faster-whisper")

    return _Piece(skipped=_unique(skipped))


def _ensure_audio(media: Path) -> _Piece:
    if media.suffix.lower() in AUDIO_EXTS:
        return _Piece(text=str(media))
    ffmpeg = _ffmpeg_bin()
    if not ffmpeg:
        if media.suffix.lower() in VIDEO_EXTS:
            return _Piece(text=str(media), skipped=["whisper: ffmpeg not found, sending video file as-is"])
        return _Piece(skipped=["whisper: ffmpeg not found and media is not audio"])

    wav = media.with_suffix(".wav")
    if not wav.exists():
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(media),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(wav),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return _Piece(text=str(media), skipped=[f"whisper: ffmpeg failed ({exc}), using original file"])
        if proc.returncode != 0 or not wav.exists():
            return _Piece(text=str(media), skipped=["whisper: ffmpeg could not extract audio, using original file"])
    return _Piece(text=str(wav))


def _ffmpeg_bin() -> str | None:
    found = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _whisper_faster(path: Path) -> _Piece:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return _Piece(skipped=["whisper: faster-whisper not installed"])

    try:
        model = WhisperModel("base", device="cpu")
        segments, _info = model.transcribe(str(path))
        text = " ".join(seg.text.strip() for seg in segments if getattr(seg, "text", "").strip())
        return _Piece(text=text.strip())
    except Exception as exc:  # noqa: BLE001
        return _Piece(skipped=[f"whisper: faster-whisper failed ({exc})"])


def _whisper_openai(path: Path) -> _Piece:
    try:
        from openai import OpenAI
    except ImportError:
        return _Piece(skipped=["whisper: openai package not installed"])

    try:
        client = OpenAI()
        with path.open("rb") as handle:
            resp = client.audio.transcriptions.create(model="whisper-1", file=handle)
        text = getattr(resp, "text", "") or ""
        return _Piece(text=text.strip())
    except Exception as exc:  # noqa: BLE001
        return _Piece(skipped=[f"whisper: OpenAI API failed ({exc})"])


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
