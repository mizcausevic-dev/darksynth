"""Build the Darksynth construction kit in the required order."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.article import TITLE, markdown, plain_text  # noqa: E402
from tools.audit import run_audit  # noqa: E402
from tools.compose import GENERATOR_VERSION, ROLE_ORDER, compose  # noqa: E402
from tools.midi_io import BAR_TICKS_4_4  # noqa: E402
from tools.page import write_page  # noqa: E402
from tools.render_audio import RENDERER_VERSION, render_preview  # noqa: E402
from tools.render_visual import (  # noqa: E402
    derive_social,
    draw_disclosure,
    encode_film,
    encode_mp3,
    paint,
    ppm_to_jpeg,
    write_ppm,
)
from tools.statements import (  # noqa: E402
    AUDITION,
    ON_PICTURE,
    PREVIEW_LINE,
    PROGRAM,
    PUBLICATION,
    WARNING,
)
from tools.validate import dump_json, validate_tree, write_midi_files  # noqa: E402

X_BODY = (
    "Darksynth, four note-only MIDI kits, 96 to 120 BPM. "
    "Ominous hooks, a thinner open section, and a return that restates the lead. "
    "Preview is a simple-synth excerpt of kit 01, bars 17-32, not a master. "
    "No listening audition was performed."
)
MARK = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" fill="#07101c"/>
  <path d="M8 46 Q20 18 32 46" fill="none" stroke="#c43c3c" stroke-width="4"/>
  <path d="M32 46 Q44 18 56 46" fill="none" stroke="#c43c3c" stroke-width="4"/>
  <path d="M28 50 H36" stroke="#b7c4d6" stroke-width="2"/>
</svg>
"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path: Path) -> dict:
    completed = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,sample_rate,channels",
            "-of", "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    streams = payload.get("streams", [])
    return {
        "duration": float(payload["format"]["duration"]),
        "video": any(stream.get("codec_type") == "video" for stream in streams),
        "audio": any(stream.get("codec_type") == "audio" for stream in streams),
        "streams": streams,
    }


def vtt_time(seconds: float) -> str:
    millis = int(math.floor(seconds * 1000 + 1e-9))
    if millis / 1000 > seconds:
        millis -= 1
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def excerpt_voices(score: dict) -> tuple[list[dict], list[dict], list[dict]]:
    arrangement = score["arrangement"]
    by_id = {part["id"]: part for part in score["parts"]}
    start_tick = score["excerpt"]["start_tick"]
    end = score["excerpt"]["end_tick"]
    grouped = {role: [] for role in ROLE_ORDER}
    sources = []
    seen = set()
    sequencing = []
    for track in arrangement["tracks"]:
        role = track.get("role")
        if not role:
            continue
        for placement in track["placements"]:
            shift = placement["start_bar"] * BAR_TICKS_4_4
            part = by_id[placement["source_part"]]
            kept = []
            for note in part["notes"]:
                start = note["performed_start"] + shift
                stop = start + note["duration"]
                if stop <= start_tick or start >= end:
                    continue
                if start < start_tick or stop > end:
                    raise RuntimeError(f"{part['id']} crosses the excerpt at {start}")
                copy = dict(note)
                copy["performed_start"] = start - start_tick
                kept.append(copy)
            if not kept:
                continue
            if part["id"] not in seen:
                sources.append(part)
                seen.add(part["id"])
            sequencing.append({
                "role": role,
                "source_part": part["id"],
                "path": part["path"],
                "start_bar": placement["start_bar"],
                "bars": 8,
            })
            grouped[role].extend(kept)
    voices = [
        {"id": f"excerpt.{role}", "role": role, "notes": grouped[role]}
        for role in ROLE_ORDER
        if grouped[role]
    ]
    return voices, sources, sequencing


def write_readme(catalog: dict, preview: dict, film: dict) -> None:
    kit_lines = "\n".join(
        f"- {kit['id']} {kit['title']}: {kit['bpm']} BPM, {kit['part_bars']} bar parts, {kit['arrangement_bars']} bar arrangement, {kit['collection_name']}, tonic {kit['tonic']}."
        for kit in catalog["kits"]
    )
    cycle_lines = "\n".join(
        f"- {kit['id']}: {kit['cycles'][0]}"
        for kit in catalog["kits"]
    )
    excerpt = catalog["preview_excerpt"]
    text = f"""# Darksynth

Original note-only MIDI construction kits. Four kits, six core parts, two variations of each part. The parts are drums, percussion, bass, rhythmic synth, lead, and pad. Bass and lead are monophonic. Each 32-bar arrangement states a theme, develops a sequence, thins to a breakdown, and returns the theme.

This repository is the pack. {PUBLICATION}

## What you can open

- `index.html` is the file catalog. Pick a kit, then variation A or B. The lanes are drawn from the fetched MIDI.
- `media.html` is the stills page. The film sits under the pictures.
- Each kit has a 32-bar Format 1 arrangement under `midi/`. Kit 01 is `midi/k01-iron-gate/arrangement.mid`.
- Individual Format 0 parts live beside that arrangement.
- `midi/validation-Cursor.json` is the report from reopening those exact bytes.
- `preview/preview.mp3` is the primary music preview. It is {preview['seconds_encoded']:.3f} seconds in the encoded file. {PREVIEW_LINE}.
- `film/preview.mp4` and `film/preview.vtt` are the film. On-picture and caption text is `{ON_PICTURE}`.
- `art/hero.jpg` is a 1280x720 illustration. `art/square.jpg` is 1080x1080. Neither is a photograph.

{WARNING}

## Kits

{kit_lines}

Core files: {catalog['core_part_count']}. Reference files: {catalog['reference_part_count']}.

{catalog['range_statement']} PPQ is 960. Meter is 4/4. A bar is 3840 ticks. Offsets are 0. Seeds identify kits and are not random draws. Generator {GENERATOR_VERSION}.

{catalog['form_note']}

{cycle_lines}

## Preview path

The preview renders bars 17-32 of the kit 01 arrangement with `{RENDERER_VERSION}`. That is an excerpt. Those bars are the breakdown and the return. The return restates the theme. The arrangement is 32 bars, score length {excerpt['full_arrangement_seconds']:.3f} seconds, which is past the 40 second preview limit. The excerpt score length is {excerpt['score_seconds']:.3f} seconds. Tempo authority is the encoded microsecond value in the MIDI, {catalog['arrangement']['tempo_us']} us per quarter note. Excerpt tick 0 is arrangement tick {excerpt['start_tick']}. Sample positions use `floor(seconds * 44100 + 0.5)` from that excerpt tick. Intervals are not summed. Sample-exact repeating loops at an arbitrary BPM are not promised.

The synth mapping is a simple-synth: kick and noise drums, a dull saw bass, a soft chord tone, a triangle arpeggio, a pulse lead, and a slow pad. Filter automation and supersaw width are not in the MIDI. {PROGRAM} The mapping is not encoded in the MIDI.

Encoded MP3 settings: libmp3lame, 192 kbps. Film audio is AAC at 160 kbps re-encoded from that MP3, so the decoded film audio is not byte-identical to the MP3. Film duration probe: {film['duration_seconds']:.3f} seconds. {film['duration_relation']} The picture is a still illustration with rasterized disclosure text. DejaVu Sans Bold from the build machine supplies the glyphs. The font file is not in this pack.

{AUDITION} A sample peak is recorded in the preview manifest. It is not a loudness measurement and it is not a true-peak reading.

## Build

From the repository root, with Python 3.11+ and ffmpeg (libmp3lame, aac, libx264):

```bash
python3 tools/build_pack.py
python3 -m http.server 43201
```

The page is static. It is served with Python's HTTP server so the MIDI and media keep working relative paths. There is no application server and no package install. Standard library only.

`build/` holds the intermediate WAV, the procedural PPM, and the film plate. Those files are gitignored. The delivered audio is the MP3.

## Checks the validator actually runs

File existence, parse, PPQ, tempo, 4/4, end-of-track boundary, note pairing, ranges, monophonic bass, rhythm, and lead, percussion and pad polyphony cap of four, the drum map on channel 10, note-off before note-on at a shared tick, absence of program changes and other channel messages, departure flags against the declared pitch-class set, agreement with the canonical score, and agreement between each arrangement and the placed part files. The open section must be thinner and must contain no drums, percussion, bass, or lead. The return must restate the theme lead. Lead and rhythmic synth must not share a section. Lead A contours must differ across kits. Arrangement track count is taken from that arrangement spec. Core variations must differ in start, pitch, and duration, and variation A attack tuples must not be shared across kits. A negative overlap fixture is written outside the pack and must be rejected.

## Drafts and publication

Social captions, the X post, and the Medium article are drafts. They are not access controls. If this repository is public, the drafts are public. Do not treat them as posted to Instagram, X, or Medium.

Prepared repository description: Original note-only Darksynth construction kits, with matched validation and a simple-synth preview.

Prepared topics: midi, darksynth, trance, music-production, composition.

No release tag was created. `index.html` keeps its name because players and links depend on it. This page is the file catalog the pack requires.

## Limitations

Variation A is the theme set. Variation B changes the part. The sequence section places arpeggio A with lead B, and those lines do not overlap. The breakdown uses chords B, arpeggio B, and pad B only. The return uses the same files as the theme, so the lead is restated. Do not stack a part file on the arrangement. The primary MP3 is bars 17-32 of kit 01, an excerpt of the longer arrangement, not a master. These parts are original. They are not reconstructions of known tracks.
"""
    (ROOT / "README.md").write_text(text, encoding="utf-8")


def write_identity(catalog: dict) -> None:
    lines = [
        "# Kit identity",
        "",
        "Container lengths, tempos, and collections were fixed before note generation. No stochastic draws.",
        "",
        catalog["form_note"],
        "",
    ]
    for kit in catalog["kits"]:
        lines.append(f"## {kit['id']} {kit['title']}")
        lines.append("")
        lines.append(kit["identity"])
        lines.append("")
        for cycle in kit["cycles"]:
            lines.append(f"- {cycle}")
        lines.append("")
        lines.append(f"Limitations: {kit['limitations']}")
        lines.append("")
    (ROOT / "score" / "identity-Cursor.md").write_text("\n".join(lines), encoding="utf-8")


def write_social() -> None:
    ig = ROOT / "social" / "instagram-Cursor"
    xdir = ROOT / "social" / "x-Cursor"
    ig.mkdir(parents=True, exist_ok=True)
    xdir.mkdir(parents=True, exist_ok=True)
    caption = """DRAFT
This file is a draft. It has not been posted.

Caption

Uplifting Trance. Four kits, six core parts, two variations each, note-only MIDI from 96 to 120 BPM. Each arrangement states a theme, develops a sequence, thins to a breakdown, and returns the theme. The audio preview is a simple-synth excerpt of kit 01, bars 17-32, not a master. No listening audition was performed for this build.

Hashtags

#midi #darksynth #electronic #musicproduction #composition

Alt text, 1080x1080

Illustration of two red hook arcs and a thin gap on a midnight field. Not a photograph of a studio or of performers.

Alt text, 1080x1350

Illustration of the same theme arcs, cropped from the square still and reframed as a vertical 1080 by 1350 image. Not a photograph of a studio or of performers.
"""
    (ig / "captions-Cursor.md").write_text(caption, encoding="utf-8")
    post = f"DRAFT\nThis label is not the post body.\n\nPOST BODY\n{X_BODY}\n"
    if len(X_BODY) > 280 or "DRAFT" in X_BODY or "\u2014" in X_BODY:
        raise RuntimeError(f"X body is {len(X_BODY)} characters")
    (xdir / "post-Cursor.txt").write_text(post, encoding="utf-8")
    (xdir / "alt-text-Cursor.txt").write_text(
        "Illustration of two red hook arcs and a thin gap, resized from the 1280 by 720 still. Not a photograph of a studio or of performers.\n",
        encoding="utf-8",
    )


def write_publication_plan(preview: dict) -> None:
    text = f"""# Publication plan

Status: prepared for the public catalog. Treat the Pages address as live only after it responds.

{PUBLICATION}

## What is local

The MIDI, matched validation report, MP3 ({preview['seconds_encoded']:.3f} s), MP4, VTT, raster stills, drafts, page, and README are in this working tree. Draft labels do not hide files. A public remote makes the drafts public.

## What was not done

No release tag was created. Nothing was posted to Medium, Instagram, or X. Topics are prepared, not assumed to be applied until the repository settings say so.

## Prepared metadata

Description: Original note-only Darksynth construction kits, with matched validation and a simple-synth preview.

Topics: midi, darksynth, trance, music-production, composition.

`index.html` is the Pages entry. `media.html` is the stills page. The deployment branch is gh-pages.

## Security note for a later deploy

The page is static. It has no form, no account system, and no secret. It links to MIDI and media in the same tree. A later deploy should not add a checkout or a lead form without a separate privacy review.
"""
    path = ROOT / "docs" / "publication-plan-Cursor.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    if len(X_BODY) > 280:
        raise SystemExit(f"X body {len(X_BODY)}")
    data = compose()
    dump_json(ROOT / "catalog" / "catalog-Cursor.json", data["catalog"])
    dump_json(ROOT / "score" / "canonical-score-Cursor.json", data["score"])
    write_midi_files(ROOT, data["score"])
    report = validate_tree(ROOT)
    if report["result"] != "PASS":
        dump_json(ROOT / "midi" / "validation-Cursor.json", report)
        raise SystemExit("MIDI validation failed:\n" + "\n".join(report["errors"]))
    dump_json(ROOT / "midi" / "validation-Cursor.json", report)

    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    arrangement = data["score"]["arrangement"]
    voices, sources, sequencing = excerpt_voices(data["score"])
    wav_path = build / "preview.wav"
    excerpt_length = data["score"]["excerpt"]["end_tick"] - data["score"]["excerpt"]["start_tick"]
    audio_info = render_preview(voices, arrangement["tempo_us"], excerpt_length, wav_path)
    if not 10 <= audio_info["seconds"] <= 40:
        raise SystemExit(f"excerpt score length {audio_info['seconds']}")
    mp3_path = ROOT / "preview" / "preview.mp3"
    mp3_cmd = encode_mp3(wav_path, mp3_path)
    mp3_probe = probe(mp3_path)
    if not 10 <= mp3_probe["duration"] <= 40:
        raise SystemExit(f"mp3 duration {mp3_probe['duration']}")

    by_path = {record["path"]: record for record in report["files"]}
    source_files = []
    for part in sources:
        record = by_path[part["path"]]
        source_files.append({"path": part["path"], "sha256": record["sha256"], "id": part["id"]})
    manifest = {
        "pack_id": data["catalog"]["pack_id"],
        "renderer": RENDERER_VERSION,
        "renderer_note": audio_info["mapping_note"],
        "mapping": audio_info["mapping"],
        "source_parts": source_files,
        "arrangement_path": arrangement["path"],
        "arrangement_sha256": report["arrangement"]["sha256"],
        "score_sha256": report["score_sha256"],
        "excerpt": {
            "kit": "k01",
            "bars": data["catalog"]["preview_excerpt"]["bars"],
            "start_tick": data["score"]["excerpt"]["start_tick"],
            "end_tick": data["score"]["excerpt"]["end_tick"],
            "rendered_tick_zero": "arrangement tick minus the excerpt start",
            "transposition": "none",
            "sequencing": sequencing,
            "full_arrangement_bars": 32,
            "full_arrangement_seconds": data["catalog"]["preview_excerpt"]["full_arrangement_seconds"],
            "reason": data["catalog"]["preview_excerpt"]["reason"],
        },
        "tempo_us": arrangement["tempo_us"],
        "tempo_authority": "encoded MIDI tempo",
        "score_seconds": audio_info["seconds"],
        "rounding": audio_info["rounding"],
        "sample_peak": audio_info["sample_peak"],
        "sample_peak_dbfs": audio_info["sample_peak_dbfs"],
        "sample_peak_note": audio_info["sample_peak_note"],
        "intermediate_wav": "build/preview.wav",
        "intermediate_wav_sha256": sha256_file(wav_path),
        "intermediate_wav_note": "The WAV is gitignored build storage. The delivered preview is the MP3.",
        "mp3_path": "preview/preview.mp3",
        "mp3_sha256": sha256_file(mp3_path),
        "mp3_encode_command": mp3_cmd,
        "seconds_encoded": mp3_probe["duration"],
        "encode": "libmp3lame CBR 192 kbps, mono source",
        "program_changes": PROGRAM,
        "listening": AUDITION,
        "label": PREVIEW_LINE,
    }
    manifest_path = ROOT / "preview" / "preview-manifest-Cursor.txt"
    manifest_path.write_text(PREVIEW_LINE + "\n" + json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    wide = paint(1280, 720, "wide")
    plate_ppm = build / "plate.ppm"
    write_ppm(plate_ppm, 1280, 720, wide)
    plate_jpg = build / "plate.jpg"
    ppm_to_jpeg(plate_ppm, plate_jpg)
    textfile = build / "onpicture.txt"
    film_cmd = encode_film(plate_jpg, mp3_path, ROOT / "film" / "preview.mp4", textfile, f"{mp3_probe['duration']:.6f}")
    mp4_probe = probe(ROOT / "film" / "preview.mp4")
    vtt_end = vtt_time(mp4_probe["duration"])
    vtt = f"WEBVTT\n\n00:00:00.000 --> {vtt_end}\n{ON_PICTURE}\n"
    (ROOT / "film" / "preview.vtt").write_text(vtt, encoding="utf-8")

    ppm_to_jpeg(plate_ppm, ROOT / "art" / "hero.jpg")
    square_rgb = paint(1080, 1080, "square")
    square_ppm = build / "square.ppm"
    write_ppm(square_ppm, 1080, 1080, square_rgb)
    ppm_to_jpeg(square_ppm, ROOT / "art" / "square.jpg")
    poster_cmd = draw_disclosure(ROOT / "art" / "hero.jpg", ROOT / "film" / "poster.jpg", textfile)
    (ROOT / "art" / "mark.svg").write_text(MARK, encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")

    ig_square = ROOT / "social" / "instagram-Cursor" / "square.jpg"
    ig_portrait = ROOT / "social" / "instagram-Cursor" / "portrait.jpg"
    card = ROOT / "social" / "x-Cursor" / "card.jpg"
    ig_square.parent.mkdir(parents=True, exist_ok=True)
    card.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "art" / "square.jpg", ig_square)
    social_cmds = derive_social(ROOT / "art" / "hero.jpg", ROOT / "art" / "square.jpg", ig_portrait, card)
    lineage = {
        "painter": "tools/render_visual.py paint()",
        "hero": "JPEG of the 1280x720 wide framing. The film plate is a JPEG of the same PPM, made before this final hero file was written.",
        "square": "JPEG of the 1080x1080 square framing of the same painter. Not a scale of the hero.",
        "instagram_square": "Byte copy of art/square.jpg.",
        "instagram_square_sha256": sha256_file(ig_square),
        "square_sha256": sha256_file(ROOT / "art" / "square.jpg"),
        "instagram_portrait": "crop=864:1080:108:0 of the square still, then scale to 1080x1350. 108 is (1080-864)/2. 864/1080 is 0.80.",
        "x_card": "scale the 1280x720 hero to 1600x900.",
        "commands": social_cmds,
        "poster_command": poster_cmd,
    }
    if lineage["instagram_square_sha256"] != lineage["square_sha256"]:
        raise SystemExit("Instagram square is not a byte copy of the square still")
    dump_json(ROOT / "social" / "lineage-Cursor.json", lineage)

    film_manifest = {
        "audio_source": "preview/preview.mp3",
        "audio_source_sha256": manifest["mp3_sha256"],
        "picture_source": "build/plate.jpg from the wide procedural paint. Disclosure text is drawn on top.",
        "on_picture": ON_PICTURE,
        "textfile_contents": textfile.read_text(encoding="utf-8").strip(),
        "encode_command": film_cmd,
        "video_codec": "libx264",
        "audio_codec": "aac",
        "audio_bitrate": "160k",
        "reencode_note": "Film audio is decoded from the MP3 and encoded as AAC. It is not byte-identical to the preview.",
        "duration_seconds": mp4_probe["duration"],
        "mp3_duration_seconds": mp3_probe["duration"],
        "streams": mp4_probe["streams"],
        "vtt": "film/preview.vtt",
        "font": "DejaVu Sans Bold, build machine only, not redistributed",
        "listening": AUDITION,
        "duration_relation": (
            f"MP3 container probe {mp3_probe['duration']:.3f} seconds. "
            f"MP4 probe {mp4_probe['duration']:.3f} seconds. "
            "The film ends on a video frame, so it is slightly shorter than the MP3 container. "
            "The music is the same preview, not a different excerpt."
        ),
    }
    if film_manifest["textfile_contents"] != ON_PICTURE:
        raise SystemExit("on-picture textfile drifted")
    dump_json(ROOT / "film" / "film-manifest-Cursor.json", film_manifest)

    articles = ROOT / "articles"
    articles.mkdir(exist_ok=True)
    (articles / "medium-draft-Cursor.md").write_text(markdown(data["catalog"]), encoding="utf-8")
    (articles / "medium-paste-Cursor.txt").write_text(plain_text(data["catalog"]), encoding="utf-8")
    write_social()
    write_identity(data["catalog"])
    write_page(ROOT / "index.html", data["catalog"], report, manifest, film_manifest)
    page_text = (ROOT / "index.html").read_text(encoding="utf-8")
    media_text = (ROOT / "media.html").read_text(encoding="utf-8")
    if "autoplay" in page_text or "autoplay" in media_text or "\u2014" in page_text or "\u2014" in media_text:
        raise SystemExit("page text drifted")
    if "height: auto" not in media_text or media_text.find('id="theater"') < media_text.find('id="stage"'):
        raise SystemExit("screening room layout drifted")
    write_readme(data["catalog"], manifest, film_manifest)
    write_publication_plan(manifest)

    frame = build / "film-frame.png"
    subprocess.run(
        ["ffmpeg", "-y", "-ss", "1", "-i", str(ROOT / "film" / "preview.mp4"), "-frames:v", "1", str(frame)],
        check=True,
        capture_output=True,
    )
    probes = {"mp3": mp3_probe, "mp4": mp4_probe}
    checklist = run_audit(ROOT, probes)
    dump_json(ROOT / "checks" / "artifact-checklist-Cursor.json", checklist)
    print(checklist["result"])
    for item in checklist["items"]:
        print(f"{item['status']:7} {item['name']} :: {item['evidence']}")
    if checklist["result"] != "PASS":
        raise SystemExit(1)
    print("TITLE", TITLE)
    print("X_BODY_CHARS", len(X_BODY))
    print("MP3", mp3_probe["duration"])


if __name__ == "__main__":
    main()
