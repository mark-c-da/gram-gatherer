"""Caption, carousel OCR, Whisper, then silent-reel frame OCR.

OCR on stills only for image carousels (2+ stills, no video).
When a reel has thin caption and empty/thin Whisper, sample frames by duration
(max 12), OCR them (ocr-frames), and archive JPEGs under archive/frames/.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from lib.classify import caption_sufficient
from lib.fetch import FetchResult

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif"}
VIDEO_EXTS = {".mp4", ".m4v", ".mov", ".webm", ".mkv"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"}
# Single decorative thumbs — never treat as a carousel slide set.
NON_CAROUSEL_IMAGE_NAMES = {"oembed-thumb.jpg"}

MAX_FRAME_SAMPLES = 12
MIN_FRAME_SAMPLES = 3


def _ensure_heif_support() -> None:
    """Register HEIF opener when pillow-heif is installed (real .heic files)."""
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except ImportError:
        pass


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


@dataclass(frozen=True)
class FrameSamplePlan:
    count: int
    timestamps: tuple[float, ...]
    duration: float

    @property
    def interval(self) -> float:
        if self.count <= 0 or self.duration <= 0:
            return 0.0
        return self.duration / (self.count + 1)


def frame_sample_plan(duration: float) -> FrameSamplePlan:
    """Spread up to MAX_FRAME_SAMPLES frames across the reel, skipping 0 and end.

    n = min(12, max(3, round(duration)))
    timestamps at interval, 2*interval, … where interval = duration / (n + 1)
    """
    if duration <= 0 or math.isnan(duration) or math.isinf(duration):
        return FrameSamplePlan(count=0, timestamps=(), duration=0.0)
    n = min(MAX_FRAME_SAMPLES, max(MIN_FRAME_SAMPLES, int(round(duration))))
    interval = duration / (n + 1)
    stamps = tuple(interval * i for i in range(1, n + 1))
    return FrameSamplePlan(count=n, timestamps=stamps, duration=float(duration))


def extract_text(
    fetched: FetchResult,
    *,
    caption_override: str | None = None,
    skip_media: bool = False,
    repo_root: Path | None = None,
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
            result.skipped.extend(["ocr", "whisper", "ocr-frames"])
        result.sources_used = _unique(result.sources_used)
        result.skipped = _unique(result.skipped)
        return result

    videos = list(fetched.videos)
    slides = carousel_slide_images(fetched)
    if slides:
        ocr = _ocr_images(slides)
        if ocr.text:
            result.ocr_text = ocr.text
            result.sources_used.append("ocr")
        result.skipped.extend(ocr.skipped)
    else:
        result.skipped.append("ocr: not a carousel (need 2+ stills, no video)")

    if videos:
        whisper = _whisper_videos(videos)
        if whisper.text:
            result.transcript = whisper.text
            result.sources_used.append("whisper")
        result.skipped.extend(whisper.skipped)

        # Silent / on-screen-text reels: sample frames when speech did not help.
        if not caption_sufficient(result.combined_text):
            frames = _frame_ocr_video(
                videos[0],
                shortcode=fetched.ref.shortcode,
                url=fetched.ref.url,
                repo_root=repo_root,
            )
            if frames.text:
                merged = "\n\n".join(
                    p for p in (result.ocr_text, frames.text) if p.strip()
                )
                result.ocr_text = merged
                result.sources_used.append("ocr-frames")
            result.skipped.extend(frames.skipped)
        else:
            result.skipped.append("ocr-frames: skipped (caption/whisper already sufficient)")

    result.sources_used = _unique(result.sources_used)
    result.skipped = _unique(result.skipped)
    return result


def carousel_slide_images(fetched: FetchResult) -> list[Path]:
    """Return stills to OCR only when this looks like an image carousel.

    - 2+ image files after filtering out oEmbed/decorative thumbs
    - No video (reels often write 1 thumbnail — never OCR that)
    """
    if fetched.videos:
        return []
    slides: list[Path] = []
    for path in fetched.images:
        if path.suffix.lower() not in IMAGE_EXTS:
            continue
        if path.name.lower() in NON_CAROUSEL_IMAGE_NAMES:
            continue
        slides.append(path)
    if len(slides) < 2:
        return []
    return slides


@dataclass
class _Piece:
    text: str = ""
    skipped: list[str] = field(default_factory=list)


def _frame_ocr_video(
    video: Path,
    *,
    shortcode: str,
    url: str,
    repo_root: Path | None,
) -> _Piece:
    duration = probe_duration(video)
    if duration is None or duration <= 0:
        return _Piece(skipped=["ocr-frames: could not probe video duration"])

    plan = frame_sample_plan(duration)
    if plan.count == 0:
        return _Piece(skipped=["ocr-frames: empty sample plan"])

    frames_dir = video.parent / "frames"
    try:
        if frames_dir.exists():
            shutil.rmtree(frames_dir, ignore_errors=True)
        frames_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _Piece(skipped=[f"ocr-frames: could not create frames dir ({exc})"])

    sampled = _sample_video_frames(video, frames_dir, plan.timestamps)
    frame_paths = [Path(p) for p in (sampled.text.split("\n") if sampled.text else []) if p]
    if not frame_paths:
        _archive_frames(
            frames_dir,
            repo_root=repo_root,
            shortcode=shortcode,
            meta={
                "shortcode": shortcode,
                "url": url,
                "duration": plan.duration,
                "interval": plan.interval,
                "frame_count": 0,
                "timestamps": list(plan.timestamps),
                "error": "; ".join(sampled.skipped) or "no frames written",
            },
        )
        return _Piece(skipped=sampled.skipped or ["ocr-frames: no frames written"])

    # Archive before OCR so review samples exist even if OCR fails.
    _archive_frames(
        frames_dir,
        repo_root=repo_root,
        shortcode=shortcode,
        meta={
            "shortcode": shortcode,
            "url": url,
            "duration": plan.duration,
            "interval": plan.interval,
            "frame_count": len(frame_paths),
            "timestamps": list(plan.timestamps),
            "files": [p.name for p in frame_paths],
        },
    )

    ocr = _ocr_images(frame_paths)
    text = _dedupe_ocr_lines(ocr.text) if ocr.text else ""
    skipped = list(sampled.skipped) + list(ocr.skipped)
    if not text and not skipped:
        skipped.append("ocr-frames: OCR returned no text")
    return _Piece(text=text, skipped=skipped)


def probe_duration(video: Path) -> float | None:
    """Return media duration in seconds, or None on failure."""
    ffmpeg = _ffmpeg_bin()
    if not ffmpeg:
        return None
    ffprobe = _ffprobe_bin(ffmpeg)
    if ffprobe:
        cmd = [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        except (OSError, subprocess.TimeoutExpired):
            proc = None
        if proc and proc.returncode == 0:
            try:
                return float((proc.stdout or "").strip())
            except ValueError:
                pass

    # Fallback: parse ffmpeg -i stderr.
    cmd = [ffmpeg, "-i", str(video)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    blob = (proc.stderr or "") + (proc.stdout or "")
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", blob)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _sample_video_frames(video: Path, frames_dir: Path, timestamps: tuple[float, ...]) -> _Piece:
    ffmpeg = _ffmpeg_bin()
    if not ffmpeg:
        return _Piece(skipped=["ocr-frames: ffmpeg not found"])

    paths: list[str] = []
    skipped: list[str] = []
    for i, ts in enumerate(timestamps, start=1):
        out = frames_dir / f"frame-{i:02d}.jpg"
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{ts:.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            skipped.append(f"ocr-frames: frame {i} failed ({exc})")
            continue
        if proc.returncode != 0 or not out.exists():
            skipped.append(f"ocr-frames: frame {i} ffmpeg error")
            continue
        paths.append(str(out))
    return _Piece(text="\n".join(paths), skipped=skipped)


def _archive_frames(
    frames_dir: Path,
    *,
    repo_root: Path | None,
    shortcode: str,
    meta: dict,
) -> None:
    if repo_root is None or not shortcode:
        return
    if not frames_dir.exists():
        return
    dest = repo_root / "archive" / "frames" / shortcode
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for path in frames_dir.iterdir():
            if path.is_file():
                shutil.copy2(path, dest / path.name)
        (dest / "meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:
        # Archive is best-effort for calibration; never fail the gather.
        return


def _dedupe_ocr_lines(text: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        norm = re.sub(r"\s+", " ", line).lower()
        if len(norm) < 3:
            continue
        if norm in seen:
            continue
        seen.add(norm)
        out.append(line)
    return "\n".join(out)


def _ocr_images(images: list[Path]) -> _Piece:
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return _Piece(skipped=["ocr: install pillow and pytesseract, plus Tesseract OCR"])

    _ensure_heif_support()

    tesseract = shutil.which("tesseract") or shutil.which("tesseract.exe")
    if tesseract is None:
        for candidate in (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Tesseract-OCR"
            / "tesseract.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
            / "Tesseract-OCR"
            / "tesseract.exe",
        ):
            if candidate.is_file():
                pytesseract.pytesseract.tesseract_cmd = str(candidate)
                tesseract = str(candidate)
                break
    if tesseract is None:
        return _Piece(skipped=["ocr: tesseract binary not found on PATH"])

    chunks: list[str] = []
    skipped: list[str] = []
    for path in images:
        if path.suffix.lower() not in IMAGE_EXTS:
            continue
        try:
            with Image.open(path) as img:
                text = pytesseract.image_to_string(img.convert("RGB"))
        except Exception as exc:  # noqa: BLE001 — one bad slide must not abort the run
            skipped.append(f"ocr: {path.name}: {exc}")
            continue
        if text.strip():
            chunks.append(text.strip())
    return _Piece(text="\n\n".join(chunks).strip(), skipped=skipped)


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


def _ffprobe_bin(ffmpeg: str) -> str | None:
    candidate = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    if candidate.is_file():
        return str(candidate)
    return shutil.which("ffprobe") or shutil.which("ffprobe.exe")


_whisper_model = None


def _get_whisper_model():
    """One CPU model for the process. int8 avoids a float16 conversion on each reel."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    from faster_whisper import WhisperModel

    try:
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    except Exception:
        _whisper_model = WhisperModel("base", device="cpu", compute_type="float32")
    return _whisper_model


def _whisper_faster(path: Path) -> _Piece:
    try:
        from faster_whisper import WhisperModel  # noqa: F401
    except ImportError:
        return _Piece(skipped=["whisper: faster-whisper not installed"])

    try:
        model = _get_whisper_model()
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
