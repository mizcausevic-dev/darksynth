"""Factual article draft. Not published."""

from __future__ import annotations

from tools.statements import AUDITION, ON_PICTURE, PREVIEW_LINE, PROGRAM, PUBLICATION, WARNING

TITLE = "Darksynth is a note-only MIDI construction kit"
SUBTITLE = "Four kits, mechanical pulse, and a lead the return restates. The preview is an excerpt, not a master"
TAGS = ["midi", "darksynth", "electronic", "music production", "composition"]
TAG_LINE = "Tags: " + ", ".join(TAGS)


def paragraphs(catalog: dict) -> list[str]:
    kits = catalog["kits"]
    tempos = ", ".join(str(kit["bpm"]) for kit in kits)
    names = ", ".join(f"{kit['title']} in {kit['collection_name']}" for kit in kits)
    chord_lines = " ".join(line for kit in kits for line in kit["chord_lines"])
    theme_lines = " ".join(kit["theme_line"] for kit in kits)
    bass_lines = " ".join(kit["bass_line"] for kit in kits)
    departures = " ".join(item for kit in kits for item in kit["departures"])
    excerpt = catalog["preview_excerpt"]
    return [
        "DRAFT. " + PUBLICATION,
        TAG_LINE,
        "The pack is four coordinated kits in 4/4. Tempos are "
        + tempos
        + " BPM, one fixed integer per kit, inside the 90 to 125 range used for this project. Each kit has six core parts: drums, percussion, bass, rhythmic synth, lead, and pad. Every core part has two variations. That is 48 files. There is no reference-only count. Part files are 8 bars. Each kit also has one 32-bar arrangement.",
        "The kits are "
        + names
        + ". "
        + theme_lines
        + " The lead hooks are different melodies. They are not transpositions of one line with the same velocities. Variation B of each part changes start times, pitches, and durations. Velocity alone is not the difference.",
        "Each arrangement has four 8-bar sections. Bars 1-8 state the theme: drums, percussion, bass, lead, and pad, with the rhythmic synth silent. Bars 9-16 are the pulse section: drums, percussion, bass, rhythmic synth, and pad. The theme lead does not play in that section. Lead B is an alternate file and is not placed in the arrangement. Bars 17-24 are the open section: rhythmic synth B and pad B only. Bars 25-32 are the return. The return places the same lead A part as the theme, with the same drums, percussion, bass, and pad. The lead is restated. It is not a new tune.",
        chord_lines,
        bass_lines,
        "Bass, rhythmic synth, and lead are monophonic. The pad may hold four notes. Drums and percussion are GM channel 10, MIDI channel index 9, with an explicit map: 36 kick, 37 side stick, 38 acoustic snare, 39 clap, 40 electric snare, 42 closed hat, 46 open hat, 49 crash. C4 is 60. The resolution is 960 ticks per quarter note. Offsets are 0. Seeds name the kits. Nothing is random. "
        + departures,
        PROGRAM,
        "Darksynth is a creative label in this pack. It is not a claim of scene membership or a fixed genre boundary. Distortion and gain staging are not note-only MIDI properties. They are not in these files. The preview synth is a simple-synth with bounded drive: a short kick, noise for hats and snare, a dull saw for the bass, a triangle for the rhythmic synth, a pulse for the lead, and a slow tone for the pad. That mapping is documented. It is not a program change.",
        "The primary preview is an excerpt of the 32-bar Iron Gate arrangement, bars 17-32, at 96 BPM. "
        + excerpt["reason"]
        + " "
        + PREVIEW_LINE
        + ". The film takes its audio from that preview file and shows the words "
        + ON_PICTURE
        + " on the picture and in the WebVTT captions.",
        AUDITION
        + " The validator reopened the MIDI bytes and compared them with the canonical score. Lead intervals and departure flags were checked against those pitches. That is a structural check. The sample peak written beside the preview is the peak of the integer mix. It is not a loudness figure and it is not a true-peak reading. Nothing in this build is claimed as a master.",
        "The stills are procedural illustrations of a low horizon, two sharp arcs, and a wide gap. The gap is the open section. They are not photographs of a session or of performers.",
        "When a public URL exists, use either the combined arrangement or the separate parts. " + WARNING,
        "Call to action: the MIDI, the matched report, and the preview belong together. Do not publish this draft to Medium, Instagram, or X from the draft files alone.",
    ]


def markdown(catalog: dict) -> str:
    body = "\n\n".join(paragraphs(catalog))
    return f"# {TITLE}\n\n{SUBTITLE}\n\n{body}\n"


def plain_text(catalog: dict) -> str:
    lines = [TITLE, "", SUBTITLE, "", *paragraphs(catalog), ""]
    return "\n".join(lines) + "\n"
