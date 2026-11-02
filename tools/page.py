"""Catalog page for the Darksynth kits.

The bench fetches each part file and draws one lane per role.
Playback in the bench is a browser synth of those notes.
The MP3 further down is a separate reading of bars 17-32 of kit 01.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.article import TAG_LINE, TITLE, paragraphs
from tools.screening import lead_frames, render_media
from tools.statements import AUDITION, ON_PICTURE, PREVIEW_LINE, PROGRAM, PUBLICATION, WARNING

ROLES = (
    ("drums", "Drums"),
    ("percussion", "Percussion"),
    ("bass", "Bass"),
    ("rhythm", "Rhythmic Synth"),
    ("lead", "Lead"),
    ("pad", "Pad"),
)


def write_page(path: Path, catalog: dict, report: dict, preview: dict, film: dict) -> None:
    path.write_text(render_page(catalog, report, preview, film), encoding="utf-8")
    root = path.parent
    path.with_name("media.html").write_text(render_media({
        "pack_name": catalog["pack_name"],
        "subject": "The still draws three short strokes and a wide gap. The strokes are the motif. The gap is the open section.",
        "colors": {
            "bg": "#07101c",
            "paper": "#f4efe6",
            "ink": "#101826",
            "accent": "#f0c14a",
            "muted": "#9aa6b8",
        },
        "frames": lead_frames(root),
        "preview_seconds": preview["seconds_encoded"],
        "film_seconds": film["duration_seconds"],
    }), encoding="utf-8")


def _rows(catalog: dict) -> str:
    rows = []
    for part in catalog["parts"]:
        rows.append(
            "<tr>"
            f"<td><a href=\"{part['path']}\">{part['id']}</a></td>"
            f"<td>{part['kit_id']}</td>"
            f"<td>{part['role']}</td>"
            f"<td>{part['variation']}</td>"
            f"<td>core</td>"
            f"<td>{part['bpm']}</td>"
            f"<td>{part['notes']}</td>"
            "</tr>"
        )
    return "".join(rows)


def _kits(catalog: dict) -> str:
    blocks = []
    for kit in catalog["kits"]:
        cycles = "".join(f"<li>{cycle}</li>" for cycle in kit["cycles"])
        blocks.append(
            f"<article id=\"{kit['id']}-card\">"
            f"<h3>{kit['title']}</h3>"
            f"<p>{kit['identity']}</p>"
            f"<p class=\"meta\">{kit['id']} · {kit['bpm']} BPM · {kit['part_bars']} bar parts · "
            f"{kit['arrangement_bars']} bar arrangement · {kit['collection_name']} · tonic {kit['tonic']} · seed {kit['seed']}</p>"
            f"<p>{kit['limitations']}</p>"
            f"<ul>{cycles}</ul>"
            f"<p>{' '.join(kit['departures'])}</p>"
            "</article>"
        )
    return "".join(blocks)


def _arrangements(catalog: dict) -> str:
    blocks = []
    for arrangement in catalog["arrangements"]:
        kit = next(item for item in catalog["kits"] if item["id"] == arrangement["kit_id"])
        sections = "".join(
            f"<li>{section['name']}, bars {section['start_bar'] + 1}-{section['start_bar'] + section['bars']}: "
            f"{', '.join(section['parts'])}</li>"
            for section in arrangement["sections"]
        )
        blocks.append(
            f"<article><h3><a href=\"{arrangement['path']}\">{kit['title']} arrangement</a></h3>"
            f"<p>{arrangement['description']}</p><ul>{sections}</ul></article>"
        )
    return "".join(blocks)


def _set_map(catalog: dict) -> str:
    items = []
    for kit in catalog["kits"]:
        roles = []
        for role, _label in ROLES:
            ids = [part["id"] for part in catalog["parts"] if part["kit_id"] == kit["id"] and part["role"] == role]
            roles.append(f"<li>{role}: {', '.join(ids)}</li>")
        items.append(
            f"<li><strong>{kit['id']} {kit['title']}</strong>, {kit['bpm']} BPM, {kit['collection_name']}"
            f"<ul>{''.join(roles)}</ul></li>"
        )
    return "<ul>" + "".join(items) + "</ul>"


def _payload(catalog: dict) -> str:
    payload = {
        "roles": [{"id": role, "label": label} for role, label in ROLES],
        "kits": [
            {
                "id": kit["id"],
                "title": kit["title"],
                "bpm": kit["bpm"],
                "tempo_us": kit["tempo_us"],
                "bars": kit["part_bars"],
                "collection": kit["collection_name"],
                "tonic": kit["tonic"],
                "identity": kit["identity"],
                "limitations": kit["limitations"],
                "cycles": kit["cycles"],
                "spell": kit["spell"],
                "arrangement": next(
                    item["path"] for item in catalog["arrangements"] if item["kit_id"] == kit["id"]
                ),
            }
            for kit in catalog["kits"]
        ],
        "parts": [
            {
                "id": part["id"],
                "kit_id": part["kit_id"],
                "role": part["role"],
                "variation": part["variation"],
                "path": part["path"],
                "notes": part["notes"],
            }
            for part in catalog["parts"]
        ],
    }
    return json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")


def render_page(catalog: dict, report: dict, preview: dict, film: dict) -> str:
    excerpt = catalog["preview_excerpt"]
    lanes = "".join(
        f'<div class="lane" id="lane-{role}" data-role="{role}"><span class="lane-label">{label}</span></div>'
        for role, label in ROLES
    )
    article = "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs(catalog))
    html = TEMPLATE
    replacements = {
        "__ROWS__": _rows(catalog),
        "__KITS__": _kits(catalog),
        "__MAP__": _set_map(catalog),
        "__ARRANGEMENTS__": _arrangements(catalog),
        "__ARTICLE__": article,
        "__DATA__": _payload(catalog),
        "__SECONDS__": f"{preview['seconds_encoded']:.3f}",
        "__FILM_SECONDS__": f"{film['duration_seconds']:.3f}",
        "__SCORE_SECONDS__": f"{excerpt['score_seconds']:.3f}",
        "__FULL_SECONDS__": f"{excerpt['full_arrangement_seconds']:.3f}",
        "__RANGE__": catalog["range_statement"],
        "__ODD__": catalog["form_note"],
        "__EXCERPT__": excerpt["bars"],
        "__REASON__": excerpt["reason"],
        "__CORE__": str(catalog["core_part_count"]),
        "__RESULT__": report["result"],
        "__WARNING__": WARNING,
        "__PROGRAM__": PROGRAM,
        "__AUDITION__": AUDITION,
        "__PUBLICATION__": PUBLICATION,
        "__PREVIEW_LINE__": PREVIEW_LINE,
        "__ON_PICTURE__": ON_PICTURE,
        "__TAG_LINE__": TAG_LINE,
        "__ARTICLE_TITLE__": TITLE,
        "__LANES__": lanes,
    }
    for key, value in replacements.items():
        html = html.replace(key, value)
    return html


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Darksynth</title>
  <link rel="icon" href="art/mark.svg" type="image/svg+xml">
  <style>
    :root {
      --bg: #07101c;
      --ink: #f4efe6;
      --muted: #9aa6b8;
      --lime: #f0c14a;
      --saffron: #ff8a4a;
      --mint: #7ec8e3;
      --line: rgba(240, 193, 74, .28);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; background: var(--bg); color: var(--ink);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      line-height: 1.45; padding-bottom: 32px;
    }
    a { color: var(--lime); }
    img, video, audio { max-width: 100%; height: auto; }
    button, .meta, .note, .transport, .lane-label { font-family: ui-monospace, Menlo, Consolas, monospace; }
    header, main { width: min(1120px, calc(100% - 2rem)); margin: 0 auto; }
    header { display: flex; justify-content: space-between; gap: 16px; align-items: end; padding: 22px 0 8px; }
    .brand { letter-spacing: .16em; text-transform: uppercase; text-decoration: none; color: var(--ink); font-size: .78rem; }
    nav { display: flex; gap: 14px; flex-wrap: wrap; font-size: .82rem; }
    h1 { font-weight: 560; font-size: clamp(2.6rem, 6vw, 4.8rem); line-height: .9; margin: 8px 0 12px; }
    h2 { font-weight: 560; font-size: 1.5rem; margin: 28px 0 8px; }
    .kicker { letter-spacing: .14em; text-transform: uppercase; color: var(--saffron); font-size: .74rem; margin: 0; }
    .meta, .note { color: var(--muted); font-size: .84rem; }
    .stage { display: grid; grid-template-columns: minmax(0, .9fr) minmax(0, 1.1fr); gap: 22px; align-items: start; }
    .hero img { display: block; width: 100%; height: auto; border-radius: 14px; }
    .chooser, .switch { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
    button {
      border: 1px solid var(--line); background: transparent; color: var(--ink);
      border-radius: 999px; padding: 7px 12px; cursor: pointer;
    }
    button[aria-pressed="true"] { background: var(--lime); color: #1a1408; border-color: var(--lime); }
    button:focus-visible, a:focus-visible { outline: 2px solid var(--lime); outline-offset: 3px; }
    .scroller { overflow-x: auto; max-width: 100%; background: #050a14; border-radius: 14px; padding: 8px 0 12px; }
    .ruler, .lane { position: relative; }
    .ruler { height: 26px; }
    .bar-mark { position: absolute; top: 4px; font-size: 11px; color: var(--muted); }
    .lane { height: 74px; border-top: 1px solid rgba(231, 255, 228, .1); }
    .lane-label {
      position: sticky; left: 6px; top: 6px; z-index: 2;
      display: inline-block; padding: 2px 6px; background: #07101c; color: var(--lime);
      font-size: 10px; letter-spacing: .08em; text-transform: uppercase;
    }
    .blip { position: absolute; border-radius: 2px; min-width: 2px; }
    .lane[data-role="drums"] .blip { background: var(--saffron); }
    .lane[data-role="bass"] .blip { background: var(--lime); }
    .lane[data-role="keys"] .blip { background: var(--mint); }
    .lane[data-role="motif"] .blip { background: #ff8bd2; }
    .lane[data-role="sequence"] .blip { background: #f2e27a; }
    .lane[data-role="pad"] .blip { background: #9eb6ff; }
    .legend { display: flex; gap: 12px; flex-wrap: wrap; font-size: .78rem; color: var(--muted); }
    .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; }
    .table-scroll { overflow-x: auto; max-width: 100%; }
    table { width: 100%; border-collapse: collapse; font-size: .8rem; }
    th, td { text-align: left; padding: 7px 6px; border-bottom: 1px solid var(--line); vertical-align: top; }
    .flow { display: flex; flex-wrap: wrap; gap: 8px; }
    .flow span { border: 1px solid var(--line); border-radius: 999px; padding: 4px 8px; font-size: .78rem; }
    .cards, .arrangements { display: grid; gap: 14px; }
    .transport {
      display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
      margin: 8px 0 0; padding: 10px 0; border-top: 1px solid var(--line);
    }
    @media (max-width: 800px) {
      .stage { grid-template-columns: 1fr; }
      header { align-items: start; flex-direction: column; }
    }
  </style>
</head>
<body>
  <header>
    <a class="brand" href="index.html">Darksynth</a>
    <nav>
      <a href="#bench">Kits</a>
      <a href="#files">Files</a>
      <a href="#reading">Preview</a>
      <a href="media.html">Stills</a>
      <a href="midi/k01-iron-gate/arrangement.mid">Kit 01 arrangement</a>
    </nav>
  </header>
  <main>
    <section class="stage">
      <div>
        <p class="kicker">Four kits · six core parts · two variations</p>
        <h1>Darksynth</h1>
        <p id="identity"></p>
        <p class="meta" id="facts"></p>
        <p class="note" id="limits"></p>
      </div>
      <figure class="hero">
        <img src="art/hero.jpg" width="1280" height="720" alt="Illustration of three short gold strokes and a wide gap on a midnight field. Not a photograph of a studio or of performers.">
        <figcaption class="note">Illustration of three motif strokes and an open gap. Not a photograph.</figcaption>
      </figure>
    </section>
    <section id="bench">
      <div class="chooser" id="chooser"></div>
      <div class="switch">
        <button type="button" id="var-a" aria-pressed="true">Variation A</button>
        <button type="button" id="var-b" aria-pressed="false">Variation B</button>
      </div>
      <p class="note" id="cycles"></p>
      <div class="scroller" id="scroller">
        <div id="sheet">
          <div class="ruler" id="ruler"></div>
          __LANES__
        </div>
      </div>
      <p class="legend">
        <span><i class="swatch" style="background:#ff8a4a"></i>drums</span>
        <span><i class="swatch" style="background:#f0c14a"></i>bass</span>
        <span><i class="swatch" style="background:#7ec8e3"></i>keys</span>
        <span><i class="swatch" style="background:#ff8bd2"></i>motif</span>
        <span><i class="swatch" style="background:#f2e27a"></i>sequence</span>
        <span><i class="swatch" style="background:#9eb6ff"></i>pad</span>
      </p>
      <p class="note" id="status">Reading the part files.</p>
      <p class="note">Space plays this variation. J and K change kit. The lanes are the 8-bar part files. The arrangement is a separate 32-bar file.</p>
      <div class="transport">
        <button type="button" id="play">Play kit</button>
        <span id="transport-label">Space plays. J and K change kit.</span>
      </div>
    </section>
    <p>__RANGE__</p>
    <p>__ODD__</p>
    <div class="flow" aria-label="File contract">
      <span>Score</span><span>MIDI</span><span>Reopened validation</span><span>MP3</span><span>Film</span><span>Stills</span><span>Drafts</span>
    </div>
    <h2>Set map</h2>
    __MAP__
    <h2>Kit notes</h2>
    <div class="cards">__KITS__</div>
    <h2>Arrangements</h2>
    <div class="arrangements">__ARRANGEMENTS__</div>
    <p>__WARNING__</p>
    <h2 id="files">Files</h2>
    <p class="meta">Validation __RESULT__. Core __CORE__. Reference files 0. <a href="midi/validation-Cursor.json">validation report</a> · <a href="catalog/catalog-Cursor.json">catalog</a> · <a href="score/canonical-score-Cursor.json">canonical score</a></p>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Part</th><th>Kit</th><th>Role</th><th>Var</th><th>Count</th><th>BPM</th><th>Notes</th></tr></thead>
        <tbody>__ROWS__</tbody>
      </table>
    </div>
    <section id="reading">
      <p class="kicker">Recorded reading · kit 01 · __EXCERPT__</p>
      <p>__REASON__ The score length of this excerpt is __SCORE_SECONDS__ seconds. The MP3 file reads __SECONDS__ seconds. The full 32-bar arrangement is __FULL_SECONDS__ seconds, so it is not the primary preview. __PREVIEW_LINE__. The film is __FILM_SECONDS__ seconds and shows __ON_PICTURE__.</p>
      <audio controls preload="metadata" src="preview/preview.mp3"></audio>
      <p><a href="preview/preview.mp3">preview/preview.mp3</a> · <a href="preview/preview-manifest-Cursor.txt">preview manifest</a></p>
      <video controls preload="metadata" poster="film/poster.jpg" width="1280" height="720">
        <source src="film/preview.mp4" type="video/mp4">
        <track kind="captions" src="film/preview.vtt" srclang="en" label="English" default>
      </video>
      <p><a href="film/preview.mp4">film/preview.mp4</a> · <a href="film/preview.vtt">film/preview.vtt</a> · <a href="media.html">stills</a></p>
    </section>
    <h2>Article draft</h2>
    <p class="kicker">DRAFT</p>
    <h3>__ARTICLE_TITLE__</h3>
    <p>__TAG_LINE__</p>
    __ARTICLE__
    <p><a href="articles/medium-draft-Cursor.md">Article draft</a> · <a href="articles/medium-paste-Cursor.txt">plain text</a></p>
    <p>__PROGRAM__</p>
    <p>__AUDITION__</p>
    <p>__PUBLICATION__</p>
  </main>
  <script id="pack" type="application/json">__DATA__</script>
  <script>
    const pack = JSON.parse(document.getElementById("pack").textContent);
    const DRUM_ROW = {36: 0.78, 38: 0.58, 40: 0.5, 37: 0.64, 39: 0.42, 42: 0.24, 46: 0.14, 49: 0.06};
    const chooser = document.getElementById("chooser");
    const status = document.getElementById("status");
    let kitId = "k01";
    let variation = "a";
    let laneNotes = {};
    let audio = null;
    let playing = false;
    let followId = 0;
    let rollWidth = 1440;

    function kit() {
      return pack.kits.find((item) => item.id === kitId);
    }
    function pitchName(pitch) {
      const spell = kit().spell;
      return spell[pitch % 12] + String(Math.floor(pitch / 12) - 1);
    }
    function readVlq(view, offset) {
      let value = 0;
      let byte = 0;
      do {
        byte = view.getUint8(offset);
        offset += 1;
        value = (value << 7) | (byte & 0x7f);
      } while (byte & 0x80);
      return [value, offset];
    }
    function parseMidi(buffer) {
      const view = new DataView(buffer);
      if (String.fromCharCode(view.getUint8(0), view.getUint8(1), view.getUint8(2), view.getUint8(3)) !== "MThd" || view.getUint16(12) !== 960) {
        throw new Error("unexpected MIDI header");
      }
      const tracks = view.getUint16(10);
      let offset = 14;
      const notes = [];
      for (let track = 0; track < tracks; track += 1) {
        if (String.fromCharCode(view.getUint8(offset), view.getUint8(offset + 1), view.getUint8(offset + 2), view.getUint8(offset + 3)) !== "MTrk") {
          throw new Error("missing track");
        }
        const length = view.getUint32(offset + 4);
        offset += 8;
        const end = offset + length;
        let tick = 0;
        let running = 0;
        const open = new Map();
        while (offset < end) {
          let delta;
          [delta, offset] = readVlq(view, offset);
          tick += delta;
          let byte = view.getUint8(offset);
          if (byte >= 0x80) {
            running = byte;
            offset += 1;
          }
          if (running === 0xff) {
            offset += 1;
            let metaLen;
            [metaLen, offset] = readVlq(view, offset);
            offset += metaLen;
            continue;
          }
          const kind = running & 0xf0;
          const data1 = byte < 0x80 ? byte : view.getUint8(offset);
          if (byte >= 0x80) offset += 1;
          let data2 = 0;
          if (kind !== 0xc0 && kind !== 0xd0) {
            data2 = view.getUint8(offset);
            offset += 1;
          }
          const key = (running & 0x0f) + ":" + data1;
          if (kind === 0x90 && data2 > 0) open.set(key, { tick: tick, velocity: data2 });
          else if (kind === 0x80 || (kind === 0x90 && data2 === 0)) {
            const started = open.get(key);
            if (started) {
              notes.push({ pitch: data1, start: started.tick, duration: tick - started.tick, velocity: started.velocity });
              open.delete(key);
            }
          }
        }
      }
      notes.sort((a, b) => a.start - b.start || a.pitch - b.pitch);
      return notes;
    }
    function renderCopy() {
      const item = kit();
      document.getElementById("identity").textContent = item.identity;
      document.getElementById("facts").textContent = item.id + " · " + item.bpm + " BPM · " + item.bars + " bar parts · " + item.collection + " · tonic " + item.tonic;
      document.getElementById("limits").textContent = item.limitations;
      document.getElementById("cycles").textContent = item.cycles[0];
      document.getElementById("transport-label").textContent = item.title + " " + variation.toUpperCase() + " · Space plays · J and K change kit";
      for (const button of chooser.querySelectorAll("button")) {
        button.setAttribute("aria-pressed", button.dataset.id === kitId ? "true" : "false");
      }
      document.getElementById("var-a").setAttribute("aria-pressed", variation === "a" ? "true" : "false");
      document.getElementById("var-b").setAttribute("aria-pressed", variation === "b" ? "true" : "false");
    }
    function draw() {
      const item = kit();
      const container = item.bars * 4 * 960;
      rollWidth = Math.max(960, item.bars * 180);
      const sheet = document.getElementById("sheet");
      sheet.style.width = rollWidth + "px";
      const ruler = document.getElementById("ruler");
      ruler.style.width = rollWidth + "px";
      ruler.innerHTML = "";
      for (let bar = 0; bar < item.bars; bar += 1) {
        const mark = document.createElement("div");
        mark.className = "bar-mark";
        mark.textContent = String(bar + 1);
        mark.style.left = (bar / item.bars) * rollWidth + "px";
        ruler.appendChild(mark);
      }
      pack.roles.forEach((role) => {
        const host = document.getElementById("lane-" + role.id);
        host.style.width = rollWidth + "px";
        host.querySelectorAll(".blip").forEach((node) => node.remove());
        const notes = laneNotes[role.id] || [];
        const low = notes.length ? Math.min(...notes.map((note) => note.pitch)) : 0;
        const high = notes.length ? Math.max(...notes.map((note) => note.pitch)) : 1;
        const span = Math.max(1, high - low);
        notes.forEach((note) => {
          const blip = document.createElement("div");
          blip.className = "blip";
          blip.title = (role.id === "drums" ? "GM " + note.pitch : pitchName(note.pitch)) + " · " + note.velocity;
          const y = role.id === "drums" && DRUM_ROW[note.pitch] !== undefined
            ? 8 + DRUM_ROW[note.pitch] * 48
            : 10 + (1 - (note.pitch - low) / span) * 46;
          blip.style.left = (note.start / container) * rollWidth + "px";
          blip.style.width = Math.max(2, (note.duration / container) * rollWidth - 1) + "px";
          blip.style.top = y + "px";
          blip.style.height = (6 + (note.velocity / 127) * 10) + "px";
          host.appendChild(blip);
        });
      });
    }
    async function loadKit() {
      stopPlayback();
      renderCopy();
      status.textContent = "Reading the part files.";
      try {
        const loaded = await Promise.all(pack.roles.map(async (role) => {
          const part = pack.parts.find((item) => item.kit_id === kitId && item.role === role.id && item.variation === variation);
          if (!part) throw new Error("missing " + role.id);
          const response = await fetch(part.path);
          if (!response.ok) throw new Error(part.path);
          const notes = parseMidi(await response.arrayBuffer());
          return { role: role.id, notes: notes, expected: part.notes };
        }));
        laneNotes = {};
        let total = 0;
        const mismatches = [];
        loaded.forEach((lane) => {
          laneNotes[lane.role] = lane.notes;
          total += lane.notes.length;
          if (lane.notes.length !== lane.expected) mismatches.push(lane.role);
        });
        draw();
        status.textContent = "Fetched " + total + " notes from the six part files."
          + (mismatches.length ? " Count mismatch: " + mismatches.join(", ") : " Counts match the catalog.");
      } catch (error) {
        laneNotes = {};
        status.textContent = "The MIDI did not load. " + error.message;
      }
    }
    function freq(pitch) {
      return 440 * Math.pow(2, (pitch - 69) / 12);
    }
    function schedule(ctx, note, origin, amount, type) {
      const item = kit();
      const seconds = (tick) => tick / 960 * item.tempo_us / 1000000;
      const when = origin + seconds(note.start);
      const duration = Math.max(0.03, seconds(note.duration));
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = type;
      osc.frequency.value = freq(note.pitch);
      const level = amount * (note.velocity / 110);
      const attack = Math.min(0.01, duration * 0.2);
      gain.gain.setValueAtTime(0.0001, when);
      gain.gain.exponentialRampToValueAtTime(Math.max(0.0002, level), when + attack);
      gain.gain.exponentialRampToValueAtTime(0.0001, when + duration);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(when);
      osc.stop(when + duration + 0.02);
    }
    function scheduleDrum(ctx, note, origin) {
      const item = kit();
      const seconds = (tick) => tick / 960 * item.tempo_us / 1000000;
      const when = origin + seconds(note.start);
      const duration = Math.max(0.03, Math.min(0.2, seconds(note.duration)));
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = note.pitch === 36 ? "sine" : "square";
      osc.frequency.value = note.pitch === 36 ? 70 : note.pitch === 42 || note.pitch === 46 ? 2400 : 180;
      const level = (note.pitch === 36 ? 0.12 : 0.03) * (note.velocity / 110);
      gain.gain.setValueAtTime(0.0001, when);
      gain.gain.exponentialRampToValueAtTime(level, when + 0.004);
      gain.gain.exponentialRampToValueAtTime(0.0001, when + duration);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(when);
      osc.stop(when + duration + 0.02);
    }
    function stopPlayback() {
      playing = false;
      cancelAnimationFrame(followId);
      if (audio) audio.close();
      audio = null;
      document.getElementById("play").textContent = "Play kit";
    }
    function playKit() {
      const notes = Object.values(laneNotes).some((lane) => lane.length);
      if (!notes) return;
      stopPlayback();
      const ctx = new AudioContext();
      audio = ctx;
      playing = true;
      document.getElementById("play").textContent = "Stop";
      const origin = ctx.currentTime + 0.05;
      pack.roles.forEach((role) => {
        (laneNotes[role.id] || []).forEach((note) => {
          if (role.id === "drums") scheduleDrum(ctx, note, origin);
          else if (role.id === "bass") schedule(ctx, note, origin, 0.08, "sawtooth");
          else if (role.id === "pad") schedule(ctx, note, origin, 0.03, "sine");
          else if (role.id === "motif") schedule(ctx, note, origin, 0.05, "sine");
          else if (role.id === "sequence") schedule(ctx, note, origin, 0.04, "triangle");
          else if (role.id === "keys") schedule(ctx, note, origin, 0.04, "triangle");
          else schedule(ctx, note, origin, 0.04, "triangle");
        });
      });
      const item = kit();
      const container = item.bars * 4 * 60 / item.bpm;
      const follow = () => {
        if (!playing || !audio) return;
        if (audio.currentTime - origin < container) followId = requestAnimationFrame(follow);
        else stopPlayback();
      };
      follow();
    }
    function stepKit(direction) {
      const index = pack.kits.findIndex((item) => item.id === kitId);
      kitId = pack.kits[(index + direction + pack.kits.length) % pack.kits.length].id;
      loadKit();
    }
    pack.kits.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.id = item.id;
      button.textContent = item.title + " " + item.bpm;
      button.addEventListener("click", () => { kitId = item.id; loadKit(); });
      chooser.appendChild(button);
    });
    document.getElementById("var-a").addEventListener("click", () => { variation = "a"; loadKit(); });
    document.getElementById("var-b").addEventListener("click", () => { variation = "b"; loadKit(); });
    document.getElementById("play").addEventListener("click", () => { if (playing) stopPlayback(); else playKit(); });
    window.addEventListener("keydown", (event) => {
      const target = event.target;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
      if (target && target.closest && target.closest("video, audio")) return;
      if (event.code === "Space") {
        event.preventDefault();
        if (playing) stopPlayback();
        else playKit();
      } else if (event.key === "j" || event.key === "J") stepKit(-1);
      else if (event.key === "k" || event.key === "K") stepKit(1);
    });
    loadKit();
  </script>
</body>
</html>
"""
