"""Procedural raster artwork and ffmpeg media steps.

The painter draws three short gold strokes and a wide gap. The strokes are the
motif. The gap is the open section. It is an illustration, not a photograph of a
session or of performers.

DejaVu Sans Bold is used only to rasterize the disclosure into the film and the
poster. The font file is not shipped.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tools.statements import ON_PICTURE

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _clamp(value: int) -> int:
    return 0 if value < 0 else 255 if value > 255 else value


def paint(width: int, height: int, framing: str) -> bytes:
    pixels = bytearray(width * height * 3)
    for y in range(height):
        shade = y / max(1, height - 1)
        row = y * width * 3
        red = 7 + int(10 * (1 - shade))
        green = 12 + int(18 * shade)
        blue = 28 + int(36 * (1 - shade))
        for x in range(width):
            pixels[row + x * 3] = red
            pixels[row + x * 3 + 1] = green
            pixels[row + x * 3 + 2] = blue
    margin = int(width * (0.08 if framing == "wide" else 0.1))
    span = width - margin * 2
    base = int(height * 0.72)
    stroke_w = max(3, int(width * 0.06))

    def stroke(x0: int, x1: int, y_off: int) -> None:
        y0 = base + y_off
        for x in range(x0, x1):
            for thickness in range(3):
                y = y0 + thickness - 1
                if 0 <= y < height:
                    row = y * width * 3
                    pixels[row + x * 3] = 240
                    pixels[row + x * 3 + 1] = 186
                    pixels[row + x * 3 + 2] = 74

    stroke(margin, margin + stroke_w, 0)
    stroke(margin + int(span * 0.42), margin + int(span * 0.42) + stroke_w, -int(height * 0.06))
    stroke(margin + int(span * 0.78), margin + int(span * 0.78) + stroke_w, 0)
    gap0 = margin + int(span * 0.22)
    gap1 = margin + int(span * 0.72)
    y_line = int(height * 0.78)
    for x in range(gap0, gap1, 7):
        for y in range(y_line, min(height, y_line + 2)):
            row = y * width * 3
            pixels[row + x * 3] = 180
            pixels[row + x * 3 + 1] = 196
            pixels[row + x * 3 + 2] = 214
    return bytes(pixels)

def write_ppm(path: Path, width: int, height: int, rgb: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"P6\n{width} {height}\n255\n".encode("ascii")
    path.write_bytes(header + rgb)


def run(command: list[str]) -> None:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "command failed\n"
            + " ".join(command)
            + "\n"
            + completed.stderr[-2000:]
        )


def ppm_to_jpeg(ppm: Path, jpeg: Path, quality: int = 3) -> None:
    jpeg.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-i", str(ppm), "-frames:v", "1", "-q:v", str(quality), str(jpeg)])


def draw_disclosure(source: Path, dest: Path, textfile: Path) -> list[str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    textfile.write_text(ON_PICTURE + "\n", encoding="utf-8")
    command = [
        "ffmpeg", "-y", "-i", str(source),
        "-vf",
        (
            f"drawtext=textfile={textfile}:fontfile={FONT}:fontsize=48:"
            "fontcolor=white:x=(w-text_w)/2:y=h-100:box=1:boxcolor=black@0.68:boxborderw=22"
        ),
        "-frames:v", "1",
        "-q:v", "3",
        str(dest),
    ]
    run(command)
    return command


def encode_mp3(wav: Path, mp3: Path) -> list[str]:
    mp3.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-i", str(wav),
        "-codec:a", "libmp3lame", "-b:a", "192k",
        str(mp3),
    ]
    run(command)
    return command


def encode_film(plate: Path, mp3: Path, mp4: Path, textfile: Path, duration: str) -> list[str]:
    mp4.parent.mkdir(parents=True, exist_ok=True)
    textfile.write_text(ON_PICTURE + "\n", encoding="utf-8")
    command = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", "24", "-i", str(plate),
        "-i", str(mp3),
        "-t", duration,
        "-vf",
        (
            "scale=1280:720,"
            f"drawtext=textfile={textfile}:fontfile={FONT}:fontsize=48:"
            "fontcolor=white:x=(w-text_w)/2:y=h-100:box=1:boxcolor=black@0.68:boxborderw=22"
        ),
        "-r", "24",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
        "-shortest",
        "-movflags", "+faststart",
        str(mp4),
    ]
    run(command)
    return command


def derive_social(hero: Path, square: Path, portrait: Path, card: Path) -> dict[str, list[str]]:
    portrait.parent.mkdir(parents=True, exist_ok=True)
    card.parent.mkdir(parents=True, exist_ok=True)
    portrait_cmd = [
        "ffmpeg", "-y", "-i", str(square),
        "-vf", "crop=864:1080:108:0,scale=1080:1350",
        "-q:v", "3",
        str(portrait),
    ]
    card_cmd = [
        "ffmpeg", "-y", "-i", str(hero),
        "-vf", "scale=1600:900",
        "-q:v", "3",
        str(card),
    ]
    run(portrait_cmd)
    run(card_cmd)
    return {"portrait": portrait_cmd, "card": card_cmd}
