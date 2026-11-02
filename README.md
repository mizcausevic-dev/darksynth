# Darksynth

Original note-only MIDI construction kits. Four kits, six core parts, two variations of each part. The parts are drums, percussion, bass, rhythmic synth, lead, and pad. Bass and lead are monophonic. Each 32-bar arrangement states a theme, develops a sequence, thins to a breakdown, and returns the theme.

This repository is the pack. The GitHub repository is https://github.com/mizcausevic-dev/darksynth and it is public. The catalog page is https://mizcausevic-dev.github.io/darksynth/ . Treat that catalog address as live only after it responds.

## What you can open

- `index.html` is the file catalog. Pick a kit, then variation A or B. The lanes are drawn from the fetched MIDI.
- `media.html` is the stills page. The film sits under the pictures.
- Each kit has a 32-bar Format 1 arrangement under `midi/`. Kit 01 is `midi/k01-iron-gate/arrangement.mid`.
- Individual Format 0 parts live beside that arrangement.
- `midi/validation-Cursor.json` is the report from reopening those exact bytes.
- `preview/preview.mp3` is the primary music preview. It is 37.538 seconds in the encoded file. preview, not a master.
- `film/preview.mp4` and `film/preview.vtt` are the film. On-picture and caption text is `preview, not master`.
- `art/hero.jpg` is a 1280x720 illustration. `art/square.jpg` is 1080x1080. Neither is a photograph.

Use either the combined arrangement or the separate parts. Do not stack the part files on top of the combined file.

## Kits

- k01 Iron Gate: 96 BPM, 8 bar parts, 32 bar arrangement, D Mixolydian, tonic D.
- k02 Black Motor: 104 BPM, 8 bar parts, 32 bar arrangement, A major, tonic A.
- k03 Voltage Veil: 112 BPM, 8 bar parts, 32 bar arrangement, G Lydian, tonic G.
- k04 Red Terminal: 120 BPM, 8 bar parts, 32 bar arrangement, F major, tonic F.

Core files: 48. Reference files: 0.

Drums use MIDI channel index 9, the GM channel 10, and only the mapped pitches 36 kick, 37 side stick, 38 acoustic snare, 39 clap, 40 electric snare, 42 closed hat, 46 open hat, and 49 crash. Bass is monophonic, MIDI 41 to 62, channel 1, and it avoids the drum pitches. Harmonic keys allow four notes, MIDI 48 to 76, channel 2. Motif is monophonic, MIDI 60 to 86, channel 3. Sequence is monophonic, MIDI 52 to 81, channel 4. Pad allows four notes, MIDI 48 to 81, channel 5. C4 is 60. PPQ is 960. Meter is 4/4. A bar is 3840 ticks. Offsets are 0. Seeds identify kits and are not random draws. Generator 1.0.0.

Every arrangement is theme, pulse, open, return. The open section is thinner and has no drums, percussion, bass, or lead. The return restates motif A. Motif and pulse do not share a section. A bar stays 3840 ticks.

- k01: Keys A changes chord every two bars: D dominant seventh, C major seventh, G major seventh, A minor seventh.
- k02: Keys A is A major seventh, D major, E major, then F# minor, two bars each.
- k03: Keys A bars 1-4 are G major seventh. Bars 5-8 are D major seventh.
- k04: Keys A is Bb major seventh, F major, D minor seventh, then C major.

## Preview path

The preview renders bars 17-32 of the kit 01 arrangement with `simple-synth-1.0.0`. That is an excerpt. Those bars are the breakdown and the return. The return restates the theme. The arrangement is 32 bars, score length 80.000 seconds, which is past the 40 second preview limit. The excerpt score length is 37.500 seconds. Tempo authority is the encoded microsecond value in the MIDI, 625000 us per quarter note. Excerpt tick 0 is arrangement tick 61440. Sample positions use `floor(seconds * 44100 + 0.5)` from that excerpt tick. Intervals are not summed. Sample-exact repeating loops at an arbitrary BPM are not promised.

The synth mapping is a simple-synth: kick and noise drums, a dull saw bass, a soft chord tone, a triangle arpeggio, a pulse lead, and a slow pad. Filter automation and supersaw width are not in the MIDI. No program changes are encoded. A conventional GM player will normally use its default piano program for pitched channels unless configured otherwise; compatible GM channel 10 percussion is treated separately. Player behavior may vary. The mapping is not encoded in the MIDI.

Encoded MP3 settings: libmp3lame, 192 kbps. Film audio is AAC at 160 kbps re-encoded from that MP3, so the decoded film audio is not byte-identical to the MP3. Film duration probe: 37.500 seconds. MP3 container probe 37.538 seconds. MP4 probe 37.500 seconds. The film ends on a video frame, so it is slightly shorter than the MP3 container. The music is the same preview, not a different excerpt. The picture is a still illustration with rasterized disclosure text. DejaVu Sans Bold from the build machine supplies the glyphs. The font file is not in this pack.

No human listening audition was performed for this build. A sample peak is recorded in the preview manifest. It is not a loudness measurement and it is not a true-peak reading.

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
