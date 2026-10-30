"""FFmpeg / ffprobe wrappers that turn one source file into a multi-rendition HLS package.

All commands are argument lists (never a shell string), so file names can't inject options
or shell syntax, and every call has a timeout.
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class VideoProcessingError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProbeResult:
    duration: float
    width: int
    height: int
    video_codec: str
    has_audio: bool


@dataclass(frozen=True)
class Rendition:
    height: int
    video_kbps: int
    audio_kbps: int
    level: str  # H.264 level for -level:v
    codec_tag: str  # RFC 6381 codec string for the master playlist

    @property
    def name(self) -> str:
        return f"{self.height}p"


RENDITIONS: tuple[Rendition, ...] = (
    Rendition(360, 800, 96, "3.0", "avc1.4d401e"),
    Rendition(480, 1400, 128, "3.1", "avc1.4d401f"),
    Rendition(720, 2800, 128, "3.1", "avc1.4d401f"),
    Rendition(1080, 5000, 192, "4.0", "avc1.4d4028"),
)
AUDIO_CODEC_TAG = "mp4a.40.2"


def _run(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=True)
    except FileNotFoundError as exc:
        raise VideoProcessingError(
            f"{args[0]} not found; install FFmpeg and/or set FFMPEG_PATH"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoProcessingError(f"{Path(args[0]).name} timed out after {timeout}s") from exc
    except subprocess.CalledProcessError as exc:
        tail = (exc.stderr or "").strip().splitlines()[-5:]
        raise VideoProcessingError(f"{Path(args[0]).name} failed: {' | '.join(tail)}") from exc


def probe(path: Path) -> ProbeResult:
    settings = get_settings()
    args = [
        settings.ffprobe_path, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]  # fmt: skip
    result = _run(args, timeout=120)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise VideoProcessingError("ffprobe returned invalid JSON") from exc

    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None or not video.get("width") or not video.get("height"):
        raise VideoProcessingError("file has no video stream")
    duration = float(data.get("format", {}).get("duration") or video.get("duration") or 0)
    if duration <= 0:
        raise VideoProcessingError("could not determine video duration")
    return ProbeResult(
        duration=duration,
        width=int(video["width"]),
        height=int(video["height"]),
        video_codec=str(video.get("codec_name", "unknown")),
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
    )


def select_renditions(source_height: int) -> list[Rendition]:
    """Only renditions the source can actually supply; never upscale."""
    chosen = [r for r in RENDITIONS if r.height <= source_height]
    if not chosen:
        # Tiny source: one rendition at its native (even) height, with the lowest bitrate ladder.
        base = RENDITIONS[0]
        height = max(2, source_height - source_height % 2)
        chosen = [Rendition(height, base.video_kbps, base.audio_kbps, base.level, base.codec_tag)]
    return chosen


def scaled_width(info: ProbeResult, height: int) -> int:
    width = round(info.width * height / info.height)
    return width + (width % 2)


def hls_args(src: Path, out_dir: Path, info: ProbeResult, r: Rendition) -> list[str]:
    settings = get_settings()
    seg = settings.hls_segment_seconds
    args = [
        settings.ffmpeg_path, "-hide_banner", "-nostdin", "-y", "-i", str(src),
        "-map", "0:v:0",
        "-vf", f"scale=-2:{r.height}",
        "-c:v", "libx264", "-preset", "veryfast", "-profile:v", "main", "-level:v", r.level,
        "-pix_fmt", "yuv420p",
        "-b:v", f"{r.video_kbps}k", "-maxrate", f"{int(r.video_kbps * 1.07)}k",
        "-bufsize", f"{r.video_kbps * 2}k",
        # Keyframes at fixed times keep segment boundaries aligned across renditions,
        # so the player can switch quality cleanly.
        "-force_key_frames", f"expr:gte(t,n_forced*{seg})", "-sc_threshold", "0",
    ]  # fmt: skip
    if info.has_audio:
        args += ["-map", "0:a:0", "-c:a", "aac", "-b:a", f"{r.audio_kbps}k", "-ac", "2"]
    else:
        args += ["-an"]
    args += [
        "-f", "hls", "-hls_time", str(seg), "-hls_playlist_type", "vod",
        "-hls_flags", "independent_segments",
        "-hls_segment_filename", str(out_dir / "seg_%05d.ts"),
        str(out_dir / "index.m3u8"),
    ]  # fmt: skip
    return args


def master_playlist(info: ProbeResult, renditions: list[Rendition]) -> str:
    lines = ["#EXTM3U", "#EXT-X-VERSION:3", "#EXT-X-INDEPENDENT-SEGMENTS"]
    for r in renditions:
        audio = r.audio_kbps if info.has_audio else 0
        bandwidth = int((r.video_kbps * 1.07 + audio) * 1000)
        codecs = f"{r.codec_tag},{AUDIO_CODEC_TAG}" if info.has_audio else r.codec_tag
        lines.append(
            f"#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},AVERAGE-BANDWIDTH={(r.video_kbps + audio) * 1000},"
            f'RESOLUTION={scaled_width(info, r.height)}x{r.height},CODECS="{codecs}",NAME="{r.name}"'
        )
        lines.append(f"{r.name}/index.m3u8")
    return "\n".join(lines) + "\n"


def transcode_to_hls(src: Path, out_dir: Path, info: ProbeResult) -> list[str]:
    """Write <out_dir>/master.m3u8 plus one sub-folder per rendition. Returns quality names."""
    settings = get_settings()
    renditions = select_renditions(info.height)
    for r in renditions:
        rendition_dir = out_dir / r.name
        rendition_dir.mkdir(parents=True, exist_ok=True)
        logger.info("transcoding %s", r.name)
        _run(hls_args(src, rendition_dir, info, r), timeout=settings.ffmpeg_timeout_seconds)
    (out_dir / "master.m3u8").write_text(master_playlist(info, renditions), encoding="utf-8")
    return [r.name for r in renditions]


def extract_thumbnail(src: Path, dest: Path, info: ProbeResult) -> None:
    settings = get_settings()
    at = min(max(info.duration * 0.1, 1.0), max(info.duration - 1, 0))
    args = [
        settings.ffmpeg_path, "-hide_banner", "-nostdin", "-y", "-ss", f"{at:.2f}", "-i", str(src),
        "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", str(dest),
    ]  # fmt: skip
    _run(args, timeout=300)
