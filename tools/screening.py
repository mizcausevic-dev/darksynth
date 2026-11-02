"""Screening room for the stills page.

The large frame keeps its own aspect. Thumbs are a short strip. The film sits
in a later section, under the pictures.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.statements import AUDITION, ON_PICTURE, PREVIEW_LINE


def _bytes(root: Path, src: str) -> int | None:
    path = root / src
    return path.stat().st_size if path.is_file() else None


def lead_frames(root: Path) -> list[dict]:
    return [
        {
            "id": "hero",
            "src": "art/hero.jpg",
            "w": 1280,
            "h": 720,
            "label": "Hero",
            "role": "Catalog still and film plate",
            "alt": "Illustration of three short gold strokes and a wide gap on a midnight field. Not a photograph of a studio or of performers.",
            "lineage": "Wide framing painted at 1280 by 720. The film plate is this picture before the disclosure line is drawn.",
            "bytes": _bytes(root, "art/hero.jpg"),
        },
        {
            "id": "square",
            "src": "art/square.jpg",
            "w": 1080,
            "h": 1080,
            "label": "Square",
            "role": "Square still, also the Instagram square",
            "alt": "Square illustration of three motif strokes and an open gap. Not a photograph of a studio or of performers.",
            "lineage": "Painted again at 1080 by 1080 with a different phrase layout. It is not a scale of the hero. The Instagram square is a byte copy of this file.",
            "bytes": _bytes(root, "art/square.jpg"),
        },
        {
            "id": "portrait",
            "src": "social/instagram-Cursor/portrait.jpg",
            "w": 1080,
            "h": 1350,
            "label": "Portrait",
            "role": "Instagram portrait",
            "alt": "Vertical crop of the motif-stroke illustration. Not a photograph of a studio or of performers.",
            "lineage": "From the square: crop 864x1080 from x=108, then scale to 1080x1350.",
            "bytes": _bytes(root, "social/instagram-Cursor/portrait.jpg"),
        },
        {
            "id": "card",
            "src": "social/x-Cursor/card.jpg",
            "w": 1600,
            "h": 900,
            "label": "Card",
            "role": "X card",
            "alt": "Wide card of the motif-stroke illustration. Not a photograph of a studio or of performers.",
            "lineage": "The 1280 by 720 hero scaled to 1600 by 900.",
            "bytes": _bytes(root, "social/x-Cursor/card.jpg"),
        },
        {
            "id": "poster",
            "src": "film/poster.jpg",
            "w": 1280,
            "h": 720,
            "label": "Poster",
            "role": "Film poster",
            "alt": "Film poster with the words preview, not master.",
            "lineage": "The hero plus the words preview, not master, drawn along the bottom in DejaVu Sans Bold. The font file is not in the pack.",
            "bytes": _bytes(root, "film/poster.jpg"),
        },
    ]


def render_media(config: dict) -> str:
    frames = config["frames"]
    data = json.dumps(frames, ensure_ascii=False).replace("<", "\\u003c")
    preview_seconds = f"{config['preview_seconds']:.3f}"
    film_seconds = f"{config['film_seconds']:.3f}"
    colors = config["colors"]
    return TEMPLATE.replace("__DATA__", data).replace("__PACK__", config["pack_name"]).replace(
        "__SUBJECT__", config["subject"]
    ).replace("__BG__", colors["bg"]).replace("__PAPER__", colors["paper"]).replace(
        "__INK__", colors["ink"]
    ).replace("__ACCENT__", colors["accent"]).replace("__MUTED__", colors["muted"]).replace(
        "__PREVIEW_SECONDS__", preview_seconds
    ).replace("__FILM_SECONDS__", film_seconds).replace("__PREVIEW_LINE__", PREVIEW_LINE).replace(
        "__ON_PICTURE__", ON_PICTURE
    ).replace("__AUDITION__", AUDITION)


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__PACK__, stills</title>
  <link rel="icon" href="art/mark.svg" type="image/svg+xml">
  <style>
    :root {
      --bg: __BG__;
      --paper: __PAPER__;
      --ink: __INK__;
      --accent: __ACCENT__;
      --muted: __MUTED__;
      --line: rgba(244, 239, 230, .18);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--paper);
      font-family: Georgia, "Iowan Old Style", Palatino, serif;
      line-height: 1.45;
    }
    a { color: var(--accent); }
    button, .meta, figcaption, .kicker { font-family: ui-monospace, Menlo, Consolas, monospace; }
    header, main { width: min(1120px, calc(100% - 2rem)); margin: 0 auto; }
    header { padding: 28px 0 8px; }
    h1 { font-weight: 500; font-size: clamp(2.2rem, 5vw, 4.2rem); line-height: .95; margin: 8px 0 12px; }
    h2 { font-weight: 500; font-size: 1.6rem; margin: 0 0 8px; }
    .kicker { letter-spacing: .14em; text-transform: uppercase; color: var(--accent); font-size: .75rem; }
    .lede { max-width: 42rem; }
    .chapter { margin: 36px 0; padding-top: 22px; border-top: 1px solid var(--line); }
    .stage { background: #000; border-radius: 18px; overflow: hidden; }
    .stage img { display: block; width: 100%; height: auto; }
    figcaption { color: var(--muted); font-size: .82rem; padding: 8px 0 0; }
    .strip { display: flex; gap: 10px; overflow-x: auto; padding: 14px 0 4px; }
    .strip button {
      flex: 0 0 148px;
      width: 148px;
      padding: 0;
      border: 2px solid transparent;
      border-radius: 10px;
      background: #000;
      cursor: pointer;
      color: inherit;
      text-align: left;
    }
    .strip button[aria-pressed="true"] { border-color: var(--accent); }
    .strip img { display: block; width: 100%; height: 84px; object-fit: cover; object-position: center; }
    .strip span { display: block; padding: 6px 8px 8px; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; }
    .dossier { display: grid; grid-template-columns: 1.1fr .9fr; gap: 22px; align-items: start; margin-top: 14px; }
    .dossier dl { margin: 0; display: grid; grid-template-columns: 7rem 1fr; gap: 6px 10px; font-size: .92rem; }
    .dossier dt { color: var(--muted); font-family: ui-monospace, Menlo, Consolas, monospace; font-size: .75rem; letter-spacing: .08em; text-transform: uppercase; }
    .dossier dd { margin: 0; }
    .cut { display: grid; grid-template-columns: 1fr auto 1fr; gap: 16px; align-items: center; }
    .crop { position: relative; }
    .crop img, .cut img, .pair img, .theater video, .reading audio {
      display: block; width: 100%; height: auto; background: #000;
    }
    .window {
      position: absolute; top: 0; bottom: 0; left: 10%; width: 80%;
      border: 2px solid var(--accent);
      box-shadow: 0 0 0 999px rgba(0, 0, 0, .45);
      pointer-events: none;
    }
    .arrow { font-family: ui-monospace, Menlo, Consolas, monospace; color: var(--accent); text-align: center; }
    .pair { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; align-items: start; }
    .theater, .reading { margin-top: 12px; }
    @media (max-width: 800px) {
      .dossier, .cut, .pair { grid-template-columns: 1fr; }
      .arrow { transform: rotate(90deg); }
    }
  </style>
</head>
<body>
  <header>
    <p class="kicker"><a href="index.html">__PACK__</a></p>
    <h1>Stills, then the recording.</h1>
    <p class="lede">__SUBJECT__ None of these frames is a photograph of a session or of performers.</p>
  </header>
  <main>
    <section>
      <div class="stage">
        <img id="stage" alt="" width="1280" height="720">
      </div>
      <div class="strip" id="strip" role="tablist" aria-label="Stills"></div>
      <div class="dossier">
        <div>
          <p class="kicker" id="role"></p>
          <h2 id="label"></h2>
          <p id="lineage"></p>
        </div>
        <dl>
          <dt>File</dt><dd id="file"></dd>
          <dt>Pixels</dt><dd id="pixels"></dd>
          <dt>Bytes</dt><dd id="bytes"></dd>
          <dt>Use</dt><dd id="use"></dd>
        </dl>
      </div>
      <p class="meta">Left and right arrow keys move through the five frames.</p>
    </section>

    <section class="chapter">
      <p class="kicker">Portrait cut</p>
      <h2>The tall frame is a window, not a new painting.</h2>
      <p>The square is 1080 by 1080. The portrait is a crop 864x1080 from x=108 of the square, then scaled to 1080x1350. The marked window is that slice.</p>
      <div class="cut">
        <figure class="crop">
          <img src="art/square.jpg" width="1080" height="1080" alt="Square still with the portrait crop marked.">
          <div class="window" aria-hidden="true"></div>
          <figcaption>art/square.jpg · crop x=108, width 864, height 1080</figcaption>
        </figure>
        <p class="arrow">to</p>
        <figure>
          <img src="social/instagram-Cursor/portrait.jpg" width="1080" height="1350" alt="Portrait made by scaling that crop.">
          <figcaption>portrait · 1080 by 1350</figcaption>
        </figure>
      </div>
    </section>

    <section class="chapter">
      <p class="kicker">Poster</p>
      <h2>Same picture. One line added.</h2>
      <p>The poster is the hero. The only added mark is the line __ON_PICTURE__, drawn along the bottom. The typeface is DejaVu Sans Bold from the build machine. It is not shipped in the pack.</p>
      <div class="pair">
        <figure>
          <img src="art/hero.jpg" width="1280" height="720" alt="Hero still before the disclosure line.">
          <figcaption>art/hero.jpg · 1280 by 720</figcaption>
        </figure>
        <figure>
          <img src="film/poster.jpg" width="1280" height="720" alt="Film poster with the words preview, not master.">
          <figcaption>film/poster.jpg · __ON_PICTURE__</figcaption>
        </figure>
      </div>
    </section>

    <section class="chapter" id="theater">
      <p class="kicker">Film</p>
      <h2>The recording sits under the stills.</h2>
      <p>Picture from the hero plate, with __ON_PICTURE__ on the image and in the captions. Audio is the preview MP3 re-encoded as AAC, so the film is __FILM_SECONDS__ seconds and the MP3 is __PREVIEW_SECONDS__ seconds. __PREVIEW_LINE__.</p>
      <div class="theater">
        <video controls preload="metadata" poster="film/poster.jpg" width="1280" height="720">
          <source src="film/preview.mp4" type="video/mp4">
          <track kind="captions" src="film/preview.vtt" srclang="en" label="English" default>
        </video>
        <p><a href="film/preview.mp4">film/preview.mp4</a> · <a href="film/preview.vtt">film/preview.vtt</a></p>
      </div>
    </section>

    <section class="chapter reading">
      <p class="kicker">Recorded reading</p>
      <h2>The MP3 is the source. The film follows it.</h2>
      <audio controls preload="metadata" src="preview/preview.mp3"></audio>
      <p><a href="preview/preview.mp3">preview/preview.mp3</a> · __PREVIEW_SECONDS__ seconds · __PREVIEW_LINE__.</p>
      <p>__AUDITION__</p>
    </section>
  </main>
  <script id="frames" type="application/json">__DATA__</script>
  <script>
    const frames = JSON.parse(document.getElementById("frames").textContent);
    const strip = document.getElementById("strip");
    const stage = document.getElementById("stage");
    let index = 0;

    function show(next) {
      index = (next + frames.length) % frames.length;
      const frame = frames[index];
      stage.src = frame.src;
      stage.alt = frame.alt;
      stage.width = frame.w;
      stage.height = frame.h;
      document.getElementById("role").textContent = frame.role;
      document.getElementById("label").textContent = frame.label;
      document.getElementById("lineage").textContent = frame.lineage;
      document.getElementById("file").textContent = frame.src;
      document.getElementById("pixels").textContent = frame.w + " by " + frame.h;
      document.getElementById("bytes").textContent = frame.bytes ? frame.bytes.toLocaleString() + " bytes" : "size unread";
      document.getElementById("use").textContent = frame.role;
      for (const button of strip.querySelectorAll("button")) {
        button.setAttribute("aria-pressed", Number(button.dataset.index) === index ? "true" : "false");
      }
    }

    frames.forEach((frame, frameIndex) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.index = String(frameIndex);
      button.setAttribute("role", "tab");
      const img = document.createElement("img");
      img.src = frame.src;
      img.alt = "";
      const caption = document.createElement("span");
      caption.textContent = frame.label;
      button.appendChild(img);
      button.appendChild(caption);
      button.addEventListener("click", () => show(frameIndex));
      strip.appendChild(button);
    });

    window.addEventListener("keydown", (event) => {
      const target = event.target;
      if (target && target.closest && target.closest("video, audio")) return;
      if (event.key === "ArrowRight") show(index + 1);
      else if (event.key === "ArrowLeft") show(index - 1);
    });
    show(0);
  </script>
</body>
</html>
"""
