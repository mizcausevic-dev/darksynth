"""Artifact checklist. Mandatory failures mean the pack is incomplete."""

from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

from tools.article import SUBTITLE, TAG_LINE, TAGS, TITLE, paragraphs
from tools.statements import AUDITION, ON_PICTURE, PREVIEW_LINE, PROGRAM, WARNING

VTT_STAMP = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})")


def jpeg_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:2] != b"\xff\xd8":
        raise ValueError(f"{path} is not a JPEG")
    index = 2
    while index + 4 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in (0xD8, 0xD9) or marker == 0x01 or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        length = struct.unpack(">H", data[index + 2:index + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[index + 5:index + 9])
            return width, height
        index += 2 + length
    raise ValueError(f"{path} has no SOF marker")


def _stamp_to_seconds(match: re.Match) -> float:
    hours, minutes, seconds, millis = (int(piece) for piece in match.groups())
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def _parse_vtt(path: Path, duration: float) -> list[str]:
    errors = []
    text = path.read_text(encoding="utf-8")
    if not text.startswith("WEBVTT"):
        errors.append("VTT does not start with WEBVTT")
    if ON_PICTURE not in text.splitlines():
        errors.append("VTT cue text is not the exact disclosure line")
    cues = []
    for line in text.splitlines():
        if "-->" not in line:
            continue
        left, right = line.split("-->")
        start_match = VTT_STAMP.search(left)
        end_match = VTT_STAMP.search(right)
        if start_match is None or end_match is None:
            errors.append(f"unparsed cue timing: {line}")
            continue
        start = _stamp_to_seconds(start_match)
        end = _stamp_to_seconds(end_match)
        cues.append((start, end))
        if start < 0 or end < start or end > duration + 0.001:
            errors.append(f"cue {start}-{end} outside duration {duration}")
    if not cues:
        errors.append("VTT has no cues")
    return errors


def _links(html: str, root: Path) -> list[str]:
    errors = []
    refs = re.findall(r"(?:href|src)=\"([^\"]+)\"", html)
    for ref in refs:
        if ref.startswith("#") or ref.startswith("http"):
            continue
        if not (root / ref).is_file():
            errors.append(f"missing linked file {ref}")
    return errors


def run_audit(root: Path, probes: dict) -> dict:
    items = []

    def add(name: str, status: str, evidence: str, mandatory: bool = True) -> None:
        items.append({
            "name": name,
            "status": status,
            "mandatory": mandatory,
            "evidence": evidence,
        })

    report_path = root / "midi" / "validation-Cursor.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    add(
        "validation report PASS",
        "PASS" if report["result"] == "PASS" and not report["errors"] else "FAIL",
        str(report_path),
    )
    hash_ok = True
    for record in report["files"]:
        path = root / record["path"]
        if not path.is_file():
            hash_ok = False
            break
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != record["sha256"]:
            hash_ok = False
            break
    arrangement = root / report["arrangement"]["path"]
    arrangement_ok = arrangement.is_file() and hashlib.sha256(arrangement.read_bytes()).hexdigest() == report["arrangement"]["sha256"]
    add("reopened MIDI hashes still match the report", "PASS" if hash_ok and arrangement_ok else "FAIL", str(report_path))

    manifest_path = root / "preview" / "preview-manifest-Cursor.txt"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    first = manifest_text.splitlines()[0]
    manifest = json.loads("\n".join(manifest_text.splitlines()[1:]))
    mp3 = root / "preview" / "preview.mp3"
    mp3_hash = hashlib.sha256(mp3.read_bytes()).hexdigest()
    mp3_duration = probes["mp3"]["duration"]
    add(
        "primary MP3 preview",
        "PASS" if mp3.is_file() and 10 <= mp3_duration <= 40 and mp3_hash == manifest["mp3_sha256"] else "FAIL",
        f"{mp3} duration {mp3_duration}",
    )
    add(
        "preview manifest line and provenance",
        "PASS" if first == PREVIEW_LINE and PROGRAM in manifest_text and AUDITION in manifest_text else "FAIL",
        str(manifest_path),
    )

    mp4_ok = probes["mp4"]["video"] and probes["mp4"]["audio"] and 10 <= probes["mp4"]["duration"] <= 40
    add("MP4 with audio and video", "PASS" if mp4_ok else "FAIL", json.dumps(probes["mp4"]))
    vtt_errors = _parse_vtt(root / "film" / "preview.vtt", probes["mp4"]["duration"])
    add("WebVTT disclosure and bounds", "PASS" if not vtt_errors else "FAIL", "; ".join(vtt_errors) or "film/preview.vtt")

    hero = jpeg_size(root / "art" / "hero.jpg")
    square = jpeg_size(root / "art" / "square.jpg")
    poster = jpeg_size(root / "film" / "poster.jpg")
    add("hero JPEG 1280x720", "PASS" if hero == (1280, 720) else "FAIL", str(hero))
    add("square JPEG 1080x1080", "PASS" if square == (1080, 1080) else "FAIL", str(square))
    add("poster JPEG", "PASS" if poster[0] > 0 else "FAIL", str(poster))

    ig_square = jpeg_size(root / "social" / "instagram-Cursor" / "square.jpg")
    ig_portrait = jpeg_size(root / "social" / "instagram-Cursor" / "portrait.jpg")
    card = jpeg_size(root / "social" / "x-Cursor" / "card.jpg")
    add("Instagram square 1080", "PASS" if ig_square == (1080, 1080) else "FAIL", str(ig_square))
    add("Instagram portrait 1080x1350", "PASS" if ig_portrait == (1080, 1350) else "FAIL", str(ig_portrait))
    add("X image", "PASS" if card == (1600, 900) else "FAIL", str(card))

    captions = (root / "social" / "instagram-Cursor" / "captions-Cursor.md").read_text(encoding="utf-8")
    add("Instagram captions draft", "PASS" if captions.startswith("DRAFT") and "Alt text" in captions else "FAIL", "social/instagram-Cursor/captions-Cursor.md")
    post = (root / "social" / "x-Cursor" / "post-Cursor.txt").read_text(encoding="utf-8")
    body = post.split("POST BODY\n", 1)[1].strip()
    add(
        "X post draft under 280 characters",
        "PASS" if post.startswith("DRAFT") and "POST BODY" in post and len(body) <= 280 and "DRAFT" not in body else "FAIL",
        f"{len(body)} characters",
    )
    alt = (root / "social" / "x-Cursor" / "alt-text-Cursor.txt").read_text(encoding="utf-8")
    add("X alt text", "PASS" if "Illustration" in alt else "FAIL", "social/x-Cursor/alt-text-Cursor.txt")

    md = (root / "articles" / "medium-draft-Cursor.md").read_text(encoding="utf-8")
    txt = (root / "articles" / "medium-paste-Cursor.txt").read_text(encoding="utf-8")
    catalog = json.loads((root / "catalog" / "catalog-Cursor.json").read_text(encoding="utf-8"))
    article_paragraphs = paragraphs(catalog)
    article_ok = (
        TITLE in md and TITLE in txt
        and SUBTITLE in md and SUBTITLE in txt
        and TAG_LINE in md and TAG_LINE in txt
        and "DRAFT" in md and "DRAFT" in txt
        and len(TAGS) <= 5
        and all(paragraph in md and paragraph in txt for paragraph in article_paragraphs)
        and AUDITION in md and AUDITION in txt
        and not txt.lstrip().startswith("#")
    )
    add("article draft and plain text", "PASS" if article_ok else "FAIL", "articles/medium-draft-Cursor.md")

    page = (root / "index.html").read_text(encoding="utf-8")
    page_ok = (
        "autoplay" not in page
        and WARNING in page
        and AUDITION in page
        and PROGRAM in page
        and PREVIEW_LINE in page
        and ON_PICTURE in page
        and 'poster="film/poster.jpg"' in page
        and 'kind="captions"' in page
        and "controls" in page
        and not _links(page, root)
    )
    add("catalog page", "PASS" if page_ok else "FAIL", "; ".join(_links(page, root)) or "index.html")
    readme = (root / "README.md").read_text(encoding="utf-8")
    add(
        "README describes this pack",
        "PASS" if "Darksynth" in readme and "simple-synth" in readme and "python3 tools/build_pack.py" in readme else "FAIL",
        "README.md",
    )
    em = "\u2014"
    authored = [page, readme, md, txt, captions, post, manifest_text]
    add("no em dash in authored pack text", "PASS" if all(em not in text for text in authored) else "FAIL", "text scan")
    add("human listening audition", "NOT RUN", AUDITION, mandatory=False)
    add("loudness measurement", "NOT RUN", "No loudness validator was run. Sample peak is recorded separately and is not a loudness claim.", mandatory=False)
    add("external publication", "NOT RUN", "Publication is checked after the Pages URL responds.", mandatory=False)

    mandatory_fail = [item for item in items if item["mandatory"] and item["status"] != "PASS"]
    return {
        "result": "FAIL" if mandatory_fail else "PASS",
        "items": items,
        "listening": AUDITION,
    }
