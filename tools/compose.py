"""Darksynth construction kits.

Container lengths are fixed before any note is written.
Each kit is 8-bar parts in 4/4, plus one 32-bar arrangement.
A bar is 3840 ticks. PPQ is 960. Offsets are 0. Nothing is random.

Arrangement form, in every kit:
bars 1-8 theme, bars 9-16 pulse, bars 17-24 open, bars 25-32 return.
The open section has no drums, percussion, bass, or lead. The return places the same
lead A file as the theme. Lead and rhythmic synth are never in the same section.
"""

from __future__ import annotations

from tools.midi_io import BAR_TICKS_4_4, PPQ, bpm_to_us, effective_bpm

GENERATOR_VERSION = "1.0.0"
PACK_ID = "darksynth"
PACK_NAME = "Darksynth"
BAR = BAR_TICKS_4_4
PART_BARS = 8
ARRANGEMENT_BARS = 32
EXCERPT_START_BAR = 16
EXCERPT_BARS = 15

ROLE_ORDER = ("drums", "percussion", "bass", "rhythm", "lead", "pad")
SHORT = {
    "drums": "drums",
    "percussion": "percussion",
    "bass": "bass",
    "rhythm": "rhythm",
    "lead": "lead",
    "pad": "pad",
}
ROLE_NAME = {
    "drums": "Drums",
    "percussion": "Percussion",
    "bass": "Bass",
    "rhythm": "Rhythmic Synth",
    "lead": "Lead",
    "pad": "Pad",
}
CHANNEL = {
    "drums": 9,
    "percussion": 9,
    "bass": 1,
    "rhythm": 4,
    "lead": 3,
    "pad": 5,
}
LIMITS = {
    "drums": (36, 49, 4, False),
    "percussion": (36, 49, 4, False),
    "bass": (41, 62, 1, True),
    "rhythm": (52, 81, 1, True),
    "lead": (60, 86, 1, True),
    "pad": (48, 81, 4, False),
}
DRUM_MAP = {
    36: "Acoustic Bass Drum",
    37: "Side Stick",
    38: "Acoustic Snare",
    39: "Hand Clap",
    40: "Electric Snare",
    42: "Closed Hi-Hat",
    46: "Open Hi-Hat",
    49: "Crash Cymbal 1",
}
DRUM_PITCHES = set(DRUM_MAP)
QUALITIES = {
    (0, 4, 7): "major",
    (0, 3, 7): "minor",
    (0, 4, 7, 11): "major seventh",
    (0, 3, 7, 10): "minor seventh",
    (0, 4, 7, 10): "dominant seventh",
    (0, 3, 6): "diminished",
    (0, 4, 8): "augmented",
    (0, 5, 7): "suspended fourth",
    (0, 2, 7): "suspended second",
    (0, 7): "perfect fifth",
    (0, 5): "perfect fourth",
    (0, 4): "major third",
    (0, 3): "minor third",
    (0, 2): "major second",
    (0, 3, 6, 10): "half diminished seventh",
}
INTERVALS = {
    0: "unison",
    1: "minor second",
    2: "major second",
    3: "minor third",
    4: "major third",
    5: "perfect fourth",
    6: "tritone",
    7: "perfect fifth",
    8: "minor sixth",
    9: "major sixth",
    10: "minor seventh",
    11: "major seventh",
    12: "octave",
}
SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_F = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


class Part:
    def __init__(self, kit, role, variation):
        lo, hi, poly, mono = LIMITS[role]
        self.kit = kit
        self.role = role
        self.variation = variation
        self.part_id = f"{kit['id']}.{SHORT[role]}.{variation}"
        self.channel = CHANNEL[role]
        self.monophonic = mono
        self.max_poly = poly
        self.lo = lo
        self.hi = hi
        self.container_ticks = PART_BARS * BAR
        self.notes = []

    def add(self, start, duration, pitch, velocity, departure=False):
        end = start + duration
        if start < 0 or duration <= 0 or end > self.container_ticks:
            raise ValueError(f"{self.part_id} boundary {start}+{duration} pitch {pitch}")
        if not self.lo <= pitch <= self.hi:
            raise ValueError(f"{self.part_id} pitch {pitch}")
        if self.role == "drums" and pitch not in DRUM_MAP:
            raise ValueError(f"{self.part_id} unmapped drum {pitch}")
        if self.role not in ("drums", "percussion") and pitch in DRUM_PITCHES:
            raise ValueError(f"{self.part_id} pitch {pitch} collides with the drum map")
        if not 1 <= velocity <= 127:
            raise ValueError(f"{self.part_id} velocity {velocity}")
        active = 1
        for other in self.notes:
            o0 = other["performed_start"]
            o1 = o0 + other["duration"]
            if start < o1 and o0 < end:
                if other["pitch"] == pitch or self.monophonic:
                    raise ValueError(f"{self.part_id} overlap {pitch}@{start} with {other['pitch']}@{o0}")
                active += 1
        if active > self.max_poly:
            raise ValueError(f"{self.part_id} poly {active}")
        self.notes.append({
            "nominal_start": start,
            "offset": 0,
            "performed_start": start,
            "duration": duration,
            "pitch": pitch,
            "velocity": velocity,
            "channel": self.channel,
            "departure": departure,
        })

    def finish(self):
        ordered = sorted(self.notes, key=lambda note: (note["performed_start"], note["pitch"]))
        if len(ordered) < 8:
            raise ValueError(f"{self.part_id} too few notes")
        for index, note in enumerate(ordered, 1):
            note["id"] = f"{self.part_id}.n{index:04d}"
        return {
            "id": self.part_id,
            "study_id": self.kit["id"],
            "kit_id": self.kit["id"],
            "slug": self.kit["slug"],
            "role": self.role,
            "variation": self.variation,
            "core": True,
            "channel": self.channel,
            "file_slug": f"{SHORT[self.role]}-{self.variation}",
            "path": f"midi/{self.kit['slug']}/{SHORT[self.role]}-{self.variation}.mid",
            "monophonic": self.monophonic,
            "max_poly": self.max_poly,
            "container_ticks": self.container_ticks,
            "container_bars": PART_BARS,
            "bpm": self.kit["bpm"],
            "tempo_us": self.kit["tempo_us"],
            "notes": ordered,
        }


def paint(part, events):
    for start, duration, pitch, velocity, departure in events:
        part.add(start, duration, pitch, velocity, departure=departure)


def spell_pitch(pitch, spell):
    return f"{spell[pitch % 12]}{(pitch // 12) - 1}"


def chord_name(pitches, spell):
    pcs = sorted({pitch % 12 for pitch in pitches})
    root_order = [min(pitches) % 12] + [pc for pc in pcs if pc != min(pitches) % 12]
    for root in root_order:
        rel = tuple(sorted((pc - root) % 12 for pc in pcs))
        if rel in QUALITIES:
            return f"{spell[root]} {QUALITIES[rel]}"
    spelled = " ".join(spell_pitch(pitch, spell) for pitch in sorted(pitches))
    return f"spelled {spelled}"


def chord_sentence(part_id, bars, pitches, spell):
    name = chord_name(pitches, spell)
    spelling = " ".join(spell_pitch(pitch, spell) for pitch in sorted(pitches))
    return {
        "part_id": part_id,
        "bars": bars,
        "name": name,
        "spelling": spelling,
        "pitches": sorted(pitches),
        "line": f"{part_id} bars {bars} are {name}: {spelling}.",
    }


def fit_rhythm(pitch):
    lo, hi, _poly, _mono = LIMITS["rhythm"]
    while pitch < lo:
        pitch += 12
    while pitch > hi:
        pitch -= 12
    if pitch in DRUM_PITCHES or not lo <= pitch <= hi:
        raise ValueError(f"rhythm pitch {pitch}")
    return pitch


def loop(pattern, bars=range(8)):
    events = []
    for bar in bars:
        origin = bar * BAR
        for offset, duration, pitch, velocity in pattern:
            events.append((origin + offset, duration, pitch, velocity, False))
    return events


def held_chords(spans, offset, duration, velocity, departures=()):
    events = []
    departure_keys = set(departures)
    for start_bar, pitches in spans:
        origin = start_bar * BAR + offset
        for index, pitch in enumerate(pitches):
            events.append((origin, duration, pitch, velocity - index * 3, (start_bar, pitch) in departure_keys))
    return events


def arp(spans, step, duration, velocity, active_bars):
    events = []
    by_bar = {}
    for start_bar, bar_count, pitches in spans:
        for bar in range(start_bar, start_bar + bar_count):
            by_bar[bar] = pitches
    for bar in active_bars:
        tones = [fit_rhythm(pitch) for pitch in by_bar[bar]]
        slots = list(range(0, BAR, step))
        for index, offset in enumerate(slots):
            if bar % 2 == 0:
                pitch = tones[index % len(tones)]
            else:
                pitch = tones[(len(tones) - 1 - index) % len(tones)]
            events.append((bar * BAR + offset, duration, pitch, velocity - (index % 4) * 3, False))
    return events


def one_per_bar(pitches, offset, duration, velocity, departure_bars=()):
    events = []
    if len(pitches) != 8:
        raise ValueError("one_per_bar needs 8 pitches")
    for bar, pitch in enumerate(pitches):
        events.append((bar * BAR + offset, duration, pitch, velocity - bar, bar in departure_bars))
    return events


def kits():
    common = {
        "meter": "4/4",
        "bar_ticks": BAR,
        "ppq": PPQ,
        "part_bars": PART_BARS,
        "arrangement_bars": ARRANGEMENT_BARS,
        "stochastic_draws": 0,
    }
    rows = [
        {
            **common,
            "id": "k01",
            "slug": "k01-iron-gate",
            "title": "Iron Gate",
            "bpm": 96,
            "tonic": "D",
            "tonal_reference": "D",
            "collection_name": "D Mixolydian",
            "pitch_classes": [0, 2, 4, 6, 7, 9, 11],
            "spell": SHARP,
            "seed": 96031,
        },
        {
            **common,
            "id": "k02",
            "slug": "k02-black-motor",
            "title": "Black Motor",
            "bpm": 104,
            "tonic": "A",
            "tonal_reference": "A",
            "collection_name": "A major",
            "pitch_classes": [1, 2, 4, 6, 8, 9, 11],
            "spell": SHARP,
            "seed": 104031,
        },
        {
            **common,
            "id": "k03",
            "slug": "k03-voltage-veil",
            "title": "Voltage Veil",
            "bpm": 112,
            "tonic": "G",
            "tonal_reference": "G",
            "collection_name": "G Lydian",
            "pitch_classes": [1, 2, 4, 6, 7, 9, 11],
            "spell": SHARP,
            "seed": 112031,
        },
        {
            **common,
            "id": "k04",
            "slug": "k04-red-terminal",
            "title": "Red Terminal",
            "bpm": 120,
            "tonic": "F",
            "tonal_reference": "F",
            "collection_name": "F major",
            "pitch_classes": [0, 2, 4, 5, 7, 9, 10],
            "spell": FLAT_F,
            "seed": 120031,
        },
    ]
    for row in rows:
        row["tempo_us"] = bpm_to_us(row["bpm"])
        row["effective_bpm"] = effective_bpm(row["tempo_us"])
    return rows


def _drums(kit_id, variation):
    if kit_id == "k01" and variation == "a":
        events = loop([(0, 240, 36, 100), (960, 120, 42, 58), (1920, 180, 38, 84), (2880, 100, 42, 46)])
        events.append((0, 400, 49, 90, False))
        return events
    if kit_id == "k01" and variation == "b":
        return loop([(0, 200, 36, 96), (480, 80, 42, 50), (1440, 160, 36, 78), (2400, 140, 37, 74), (3360, 220, 46, 64)])
    if kit_id == "k02" and variation == "a":
        return loop([(0, 220, 36, 98), (720, 90, 42, 52), (1920, 160, 39, 80), (2640, 90, 42, 44)])
    if kit_id == "k02" and variation == "b":
        return loop([(360, 180, 36, 90), (1200, 240, 46, 60), (1680, 150, 40, 76), (2880, 70, 42, 42)])
    if kit_id == "k03" and variation == "a":
        return loop([(0, 260, 36, 94), (480, 110, 42, 48), (1920, 140, 38, 72), (3360, 160, 42, 40)])
    if kit_id == "k03" and variation == "b":
        return loop([(240, 150, 36, 86), (1200, 100, 42, 44), (2160, 180, 37, 70), (3120, 200, 46, 58)])
    if kit_id == "k04" and variation == "a":
        return loop([(0, 200, 36, 102), (1440, 120, 42, 54), (2400, 170, 38, 82)])
    if kit_id == "k04" and variation == "b":
        return loop([(360, 140, 42, 48), (960, 190, 36, 92), (1920, 130, 39, 74), (2880, 210, 46, 62)])
    raise ValueError(kit_id)


def _bass_pairs(roots, offset_a, offset_b, dur_a, dur_b, vel_a, vel_b):
    events = []
    for bar in range(8):
        root = roots[bar // 2]
        events.append((bar * BAR + offset_a, dur_a, root, vel_a, False))
        events.append((bar * BAR + offset_b, dur_b, root + 7 if root + 7 <= 62 else root - 5, vel_b, False))
    return events


def _bass(kit_id, variation):
    if kit_id == "k01" and variation == "a":
        return _bass_pairs([50, 48, 43, 45], 0, 1920, 720, 480, 94, 70)
    if kit_id == "k01" and variation == "b":
        return one_per_bar([50, 57, 48, 55, 43, 60, 45, 52], 480, 360, 80)
    if kit_id == "k02" and variation == "a":
        return _bass_pairs([45, 50, 52, 54], 480, 2400, 600, 360, 90, 66)
    if kit_id == "k02" and variation == "b":
        return one_per_bar([45, 56, 50, 57, 52, 59, 54, 61], 240, 900, 76)
    if kit_id == "k03" and variation == "a":
        return _bass_pairs([43, 43, 50, 50], 960, 2880, 840, 300, 88, 64)
    if kit_id == "k03" and variation == "b":
        return one_per_bar([43, 50, 55, 59, 50, 57, 54, 62], 120, 480, 74)
    if kit_id == "k04" and variation == "a":
        return _bass_pairs([58, 53, 50, 48], 240, 1680, 540, 420, 92, 68)
    if kit_id == "k04" and variation == "b":
        # F#3 (54) on bar 8 is outside F major.
        return one_per_bar([58, 62, 53, 60, 50, 57, 48, 54], 720, 240, 78, departure_bars={7})
    raise ValueError(kit_id)


KEY_SPANS = {
    "k01": [
        (0, 2, [62, 66, 69, 72]),
        (2, 2, [60, 64, 67, 71]),
        (4, 2, [55, 59, 62, 66]),
        (6, 2, [57, 60, 64, 67]),
    ],
    "k02": [
        (0, 2, [57, 61, 64, 68]),
        (2, 2, [50, 54, 57]),
        (4, 2, [52, 56, 59]),
        (6, 2, [54, 57, 61]),
    ],
    "k03": [
        (0, 4, [55, 59, 62, 66]),
        (4, 4, [50, 54, 57, 61]),
    ],
    "k04": [
        (0, 2, [58, 62, 65, 69]),
        (2, 2, [53, 57, 60]),
        (4, 2, [50, 53, 57, 60]),
        (6, 2, [48, 52, 55]),
    ],
}
KEY_B = {
    "k01": [
        (0, [62, 69, 74]),
        (2, [60, 67, 72]),
        (4, [59, 66, 71]),
        (6, [57, 64, 69]),
    ],
    "k02": [
        (0, [57, 64]),
        (2, [50, 57]),
        (4, [52, 59]),
        (6, [55, 59, 62]),
    ],
    "k03": [
        (0, [55, 62]),
        (2, [59, 66]),
        (4, [54, 61]),
        (6, [60, 64, 67]),
    ],
    "k04": [
        (0, [58, 65]),
        (2, [53, 60]),
        (4, [50, 57]),
        (6, [62, 66, 69]),
    ],
}
KEY_B_DEPARTURE = {
    "k02": {(6, 55)},
    "k03": {(6, 60)},
    "k04": {(6, 66)},
}


def _keys(kit_id, variation):
    if variation == "a":
        spans = [(start, pitches) for start, _count, pitches in KEY_SPANS[kit_id]]
        if kit_id == "k01":
            return held_chords(spans, 0, 2880, 78)
        if kit_id == "k02":
            return held_chords(spans, 240, 2400, 74)
        if kit_id == "k03":
            return held_chords(spans, 0, 3000, 70)
        return held_chords(spans, 480, 700, 82)
    spans = KEY_B[kit_id]
    departures = KEY_B_DEPARTURE.get(kit_id, set())
    if kit_id == "k01":
        return held_chords(spans, 480, 700, 64)
    if kit_id == "k02":
        return held_chords(spans, 960, 600, 60, departures)
    if kit_id == "k03":
        return held_chords(spans, 1440, 480, 58, departures)
    return held_chords(spans, 0, 360, 68, departures)


def _lead(kit_id, variation):
    if kit_id == "k01" and variation == "a":
        return [
            (960, 1440, 78, 84, False),
            (BAR, 960, 81, 76, False),
            (BAR + 960, 1200, 74, 68, False),
            (3 * BAR + 480, 1920, 71, 80, False),
            (4 * BAR, 720, 79, 90, False),
            (4 * BAR + 1440, 960, 76, 72, False),
            (6 * BAR, 2400, 74, 78, False),
            (7 * BAR + 960, 1440, 72, 64, False),
            (7 * BAR + 2400, 960, 69, 58, False),
        ]
    if kit_id == "k01" and variation == "b":
        return [
            (0, 480, 76, 70, False),
            (720, 360, 74, 66, False),
            (1440, 600, 81, 78, False),
            (BAR + 240, 1440, 83, 86, False),
            (2 * BAR + 960, 720, 79, 74, False),
            (3 * BAR, 960, 68, 80, True),
            (5 * BAR + 480, 480, 71, 62, False),
            (6 * BAR + 240, 1200, 78, 84, False),
            (7 * BAR + 1680, 720, 74, 60, False),
        ]
    if kit_id == "k02" and variation == "a":
        return [
            (0, 1920, 73, 88, False),
            (1920, 960, 69, 70, False),
            (BAR + 480, 1440, 76, 82, False),
            (2 * BAR, 720, 80, 92, False),
            (2 * BAR + 1680, 1200, 73, 74, False),
            (4 * BAR + 960, 1920, 64, 66, False),
            (5 * BAR, 480, 68, 84, False),
            (5 * BAR + 1440, 960, 73, 78, False),
            (6 * BAR + 480, 2880, 76, 80, False),
            (7 * BAR + 1920, 1440, 69, 62, False),
        ]
    if kit_id == "k02" and variation == "b":
        return [
            (360, 600, 76, 72, False),
            (1200, 480, 80, 86, False),
            (BAR + 0, 960, 85, 90, False),
            (2 * BAR + 720, 360, 81, 68, False),
            (3 * BAR + 480, 1440, 73, 76, False),
            (4 * BAR + 240, 720, 67, 82, True),
            (5 * BAR + 960, 480, 69, 64, False),
            (6 * BAR + 0, 1200, 76, 78, False),
            (7 * BAR + 1440, 960, 73, 60, False),
        ]
    if kit_id == "k03" and variation == "a":
        return [
            (480, 2400, 71, 70, False),
            (BAR + 1440, 1920, 76, 78, False),
            (3 * BAR, 2880, 78, 74, False),
            (4 * BAR + 960, 1440, 74, 66, False),
            (5 * BAR, 480, 83, 86, False),
            (5 * BAR + 1920, 960, 79, 72, False),
            (6 * BAR + 480, 1200, 73, 68, False),
            (7 * BAR, 3360, 67, 60, False),
        ]
    if kit_id == "k03" and variation == "b":
        return [
            (0, 720, 74, 64, False),
            (960, 480, 78, 76, False),
            (BAR + 240, 360, 81, 82, False),
            (2 * BAR + 1440, 960, 76, 70, False),
            (3 * BAR + 480, 600, 71, 66, False),
            (4 * BAR + 0, 1440, 72, 84, True),
            (6 * BAR + 720, 480, 79, 74, False),
            (7 * BAR + 240, 1920, 67, 58, False),
        ]
    if kit_id == "k04" and variation == "a":
        return [
            (240, 480, 77, 92, False),
            (720, 480, 79, 86, False),
            (1440, 720, 76, 74, False),
            (BAR, 960, 81, 88, False),
            (BAR + 1920, 480, 77, 70, False),
            (2 * BAR + 480, 1440, 72, 76, False),
            (3 * BAR + 960, 1920, 70, 64, False),
            (4 * BAR, 360, 84, 96, False),
            (4 * BAR + 720, 600, 77, 80, False),
            (5 * BAR + 1440, 960, 74, 72, False),
            (6 * BAR, 1920, 69, 68, False),
            (7 * BAR + 480, 2400, 65, 60, False),
        ]
    if kit_id == "k04" and variation == "b":
        return [
            (0, 960, 72, 70, False),
            (1200, 720, 77, 82, False),
            (BAR + 480, 360, 81, 88, False),
            (2 * BAR + 0, 1440, 74, 74, False),
            (3 * BAR + 1680, 480, 70, 66, False),
            (4 * BAR + 240, 600, 66, 80, True),
            (5 * BAR + 0, 1920, 69, 72, False),
            (6 * BAR + 960, 480, 65, 60, False),
            (7 * BAR + 1440, 720, 77, 84, False),
        ]
    raise ValueError(kit_id)


def _rhythm(kit_id, variation):
    spans = KEY_SPANS[kit_id]
    if variation == "a":
        if kit_id == "k01":
            return arp(spans, 480, 360, 74, range(4))
        if kit_id == "k02":
            return arp(spans, 640, 480, 70, range(4))
        if kit_id == "k03":
            return arp(spans, 960, 700, 66, range(4))
        return arp(spans, 240, 180, 78, range(4))
    if kit_id == "k01":
        return one_per_bar([62, 66, 69, 72, 64, 67, 71, 74], 1200, 960, 62)
    if kit_id == "k02":
        return one_per_bar([57, 61, 64, 68, 54, 57, 61, 66], 600, 720, 58)
    if kit_id == "k03":
        return one_per_bar([55, 59, 62, 66, 61, 66, 71, 73], 1800, 480, 56)
    return one_per_bar([58, 62, 65, 69, 60, 64, 67, 72], 240, 1440, 64)


def _pad(kit_id, variation):
    if variation == "a":
        if kit_id == "k01":
            return held_chords([(0, [50, 57]), (2, [48, 55]), (4, [55, 62]), (6, [57, 64])], 0, 3200, 48)
        if kit_id == "k02":
            return held_chords([(0, [57, 64]), (2, [54, 61]), (4, [52, 59]), (6, [54, 61])], 480, 2800, 46)
        if kit_id == "k03":
            return held_chords([(0, [55, 62]), (2, [59, 66]), (4, [50, 57]), (6, [54, 61])], 960, 1600, 44)
        return held_chords([(0, [58, 65]), (2, [53, 60]), (4, [50, 57]), (6, [48, 55])], 240, 2000, 50)
    if kit_id == "k01":
        return one_per_bar([62, 67, 64, 71, 66, 69, 60, 74], 720, 1500, 42)
    if kit_id == "k02":
        return one_per_bar([68, 64, 61, 57, 59, 56, 61, 66], 1200, 900, 40)
    if kit_id == "k03":
        return one_per_bar([66, 71, 74, 62, 61, 66, 69, 73], 360, 1800, 38)
    return one_per_bar([65, 69, 72, 60, 57, 62, 64, 70], 1680, 600, 44)


def _percussion(kit_id, variation):
    if kit_id == "k01" and variation == "a":
        return loop([(480, 100, 37, 72), (2400, 120, 37, 68), (3360, 180, 39, 76)])
    if kit_id == "k01" and variation == "b":
        return loop([(720, 80, 40, 70), (1680, 90, 37, 66), (2880, 100, 39, 74)])
    if kit_id == "k02" and variation == "a":
        return loop([(480, 90, 37, 70), (2160, 100, 39, 78), (3120, 80, 38, 68)])
    if kit_id == "k02" and variation == "b":
        return [
            (0, 60, 39, 70, False),
            (BAR + 480, 80, 37, 62, False),
            (2 * BAR + 1920, 100, 40, 68, False),
            (3 * BAR + 720, 90, 39, 74, False),
            (4 * BAR, 70, 37, 66, False),
            (5 * BAR + 2400, 110, 40, 72, False),
            (6 * BAR + 960, 85, 39, 64, False),
            (7 * BAR + 2880, 95, 37, 60, False),
        ]
    if kit_id == "k03" and variation == "a":
        return loop([(600, 85, 37, 68), (2040, 95, 39, 74), (3480, 100, 38, 70)])
    if kit_id == "k03" and variation == "b":
        return loop([(1200, 75, 37, 62), (2640, 105, 39, 70), (3600, 85, 40, 64)])
    if kit_id == "k04" and variation == "a":
        return loop([(360, 80, 37, 74), (1800, 90, 39, 80), (3000, 70, 38, 68)])
    return loop([(840, 85, 37, 66), (2280, 95, 39, 72), (3240, 80, 40, 64)])


def _events(kit):
    kit_id = kit["id"]
    return {
        "drums": {"a": _drums(kit_id, "a"), "b": _drums(kit_id, "b")},
        "percussion": {"a": _percussion(kit_id, "a"), "b": _percussion(kit_id, "b")},
        "bass": {"a": _bass(kit_id, "a"), "b": _bass(kit_id, "b")},
        "rhythm": {"a": _rhythm(kit_id, "a"), "b": _rhythm(kit_id, "b")},
        "lead": {"a": _lead(kit_id, "a"), "b": _lead(kit_id, "b")},
        "pad": {"a": _pad(kit_id, "a"), "b": _pad(kit_id, "b")},
    }


FORMS = {
    kit_id: [
        ("Theme", 0, [("drums", "a"), ("percussion", "a"), ("bass", "a"), ("lead", "a"), ("pad", "a")]),
        ("Pulse", 8, [("drums", "b"), ("percussion", "b"), ("bass", "b"), ("rhythm", "a"), ("pad", "a")]),
        ("Open", 16, [("rhythm", "b"), ("pad", "b")]),
        ("Return", 24, [("drums", "a"), ("percussion", "a"), ("bass", "a"), ("lead", "a"), ("pad", "a")]),
    ]
    for kit_id in ("k01", "k02", "k03", "k04")
}


def _sig(notes):
    return tuple(sorted((note["performed_start"], note["pitch"], note["duration"]) for note in notes))


def _attacks(notes):
    return tuple(sorted((note["performed_start"], note["pitch"]) for note in notes))


def _contour(notes):
    ordered = sorted(notes, key=lambda note: (note["performed_start"], note["pitch"]))
    origin_pitch = ordered[0]["pitch"]
    origin_tick = ordered[0]["performed_start"]
    shape = tuple(
        (note["pitch"] - origin_pitch, note["duration"], note["performed_start"] - origin_tick)
        for note in ordered
    )
    return shape


def _same_velocity_transpose(left, right):
    ordered_left = sorted(left, key=lambda note: (note["performed_start"], note["pitch"]))
    ordered_right = sorted(right, key=lambda note: (note["performed_start"], note["pitch"]))
    if len(ordered_left) != len(ordered_right) or not ordered_left:
        return False
    for first, second in zip(ordered_left, ordered_right):
        if first["performed_start"] != second["performed_start"] or first["duration"] != second["duration"]:
            return False
        if first["velocity"] != second["velocity"]:
            return False
    deltas = {second["pitch"] - first["pitch"] for first, second in zip(ordered_left, ordered_right)}
    return len(deltas) == 1 and 0 not in deltas


def assert_collections(catalog_kits, parts):
    allowed = {kit["id"]: set(kit["pitch_classes"]) for kit in catalog_kits}
    for part in parts:
        if part["role"] in ("drums", "percussion"):
            continue
        pool = allowed[part["kit_id"]]
        for note in part["notes"]:
            inside = (note["pitch"] % 12) in pool
            if note["departure"] and inside:
                raise ValueError(f"{part['id']} departure {note['pitch']} is inside the collection")
            if not note["departure"] and not inside:
                raise ValueError(f"{part['id']} note {note['pitch']} left the collection")


def assert_identities(parts):
    by_role = {}
    signatures = {}
    for part in parts:
        by_role.setdefault(part["role"], {}).setdefault(part["kit_id"], {})[part["variation"]] = part
        signature = _sig(part["notes"])
        if signature in signatures:
            raise ValueError(f"{part['id']} duplicates {signatures[signature]}")
        signatures[signature] = part["id"]
    report = []
    shapes = {}
    for role, kits_map in by_role.items():
        attack_seen = {}
        start_seen = {}
        for kit_id, variations in kits_map.items():
            left = variations["a"]["notes"]
            right = variations["b"]["notes"]
            starts_a = {note["performed_start"] for note in left}
            starts_b = {note["performed_start"] for note in right}
            pitches_a = {note["pitch"] for note in left}
            pitches_b = {note["pitch"] for note in right}
            durations_a = {note["duration"] for note in left}
            durations_b = {note["duration"] for note in right}
            if starts_a == starts_b or pitches_a == pitches_b or durations_a == durations_b:
                raise ValueError(f"{kit_id} {role} variation is not distinct in start, pitch, and duration")
            if len(starts_a ^ starts_b) < 4:
                raise ValueError(f"{kit_id} {role} start sets barely differ")
            if _same_velocity_transpose(left, right):
                raise ValueError(f"{kit_id} {role} B is a transposition of A with the same velocities")
            attacks = _attacks(left)
            starts = tuple(sorted(note["performed_start"] for note in left))
            if attacks in attack_seen:
                raise ValueError(f"{kit_id} {role} A attacks repeat {attack_seen[attacks]}")
            if starts in start_seen:
                raise ValueError(f"{kit_id} {role} A starts repeat {start_seen[starts]}")
            attack_seen[attacks] = kit_id
            start_seen[starts] = kit_id
            if role == "lead":
                shape = _contour(left)
                if shape in shapes:
                    raise ValueError(f"{kit_id} lead A contour repeats {shapes[shape]}")
                shapes[shape] = kit_id
            report.append({
                "kit_id": kit_id,
                "role": role,
                "a": len(left),
                "b": len(right),
                "start_delta": len(starts_a ^ starts_b),
                "pitch_delta": len(pitches_a ^ pitches_b),
                "duration_delta": len(durations_a ^ durations_b),
            })
    pair_notes = [part for part in parts if part["role"] != "drums"]
    for index, left in enumerate(pair_notes):
        for right in pair_notes[index + 1:]:
            if _same_velocity_transpose(left["notes"], right["notes"]):
                raise ValueError(f"{left['id']} and {right['id']} are transposed copies with the same velocities")
    if len(shapes) != 4:
        raise ValueError("lead hooks are not four distinct contours")
    return {
        "kits": report,
        "method": (
            "Per core role, A and B differ in start, pitch, and duration. "
            "Variation A attack tuples are not shared across kits. "
            "Lead A contours are not transpositions of each other. "
            "No part is a transposition of another part that keeps the same velocities."
        ),
    }


def _arrangement(kit, parts_by_id):
    sections = []
    placements = {role: [] for role in ROLE_ORDER}
    for name, start, voices in FORMS[kit["id"]]:
        present = []
        for role, variation in voices:
            part_id = f"{kit['id']}.{SHORT[role]}.{variation}"
            placements[role].append({"source_part": part_id, "start_bar": start, "variation": variation})
            present.append(part_id)
        sections.append({"name": name, "start_bar": start, "bars": 8, "parts": present})
    for role, items in placements.items():
        spans = []
        for item in items:
            span = (item["start_bar"], item["start_bar"] + PART_BARS)
            for other in spans:
                if span[0] < other[1] and other[0] < span[1]:
                    raise ValueError(f"{kit['id']} {role} placements overlap")
            spans.append(span)
        if not items:
            raise ValueError(f"{kit['id']} {role} missing from the arrangement")
    tracks = [{"name": "Conductor", "source_part": None, "placements": None, "channel": None, "role": None}]
    for role in ROLE_ORDER:
        tracks.append({
            "name": ROLE_NAME[role],
            "role": role,
            "channel": CHANNEL[role],
            "source_part": None,
            "placements": placements[role],
        })
    return {
        "id": f"{kit['id']}-arrangement",
        "kit_id": kit["id"],
        "path": f"midi/{kit['slug']}/arrangement.mid",
        "format": 1,
        "container_ticks": ARRANGEMENT_BARS * BAR,
        "container_bars": ARRANGEMENT_BARS,
        "bpm": kit["bpm"],
        "tempo_us": kit["tempo_us"],
        "meter": "4/4",
        "sections": sections,
        "tracks": tracks,
    }


def section_activity(arrangement, parts_by_id):
    found = {}
    for section in arrangement["sections"]:
        start = section["start_bar"] * BAR
        notes = []
        roles = set()
        for track in arrangement["tracks"]:
            if not track.get("placements"):
                continue
            for placement in track["placements"]:
                if placement["start_bar"] != section["start_bar"]:
                    continue
                part = parts_by_id[placement["source_part"]]
                roles.add(track["role"])
                for note in part["notes"]:
                    notes.append({
                        "role": track["role"],
                        "start": note["performed_start"] + start,
                        "duration": note["duration"],
                        "pitch": note["pitch"],
                        "velocity": note["velocity"],
                        "source": part["id"],
                    })
        found[section["name"]] = {"notes": notes, "roles": roles, "start": start}
    return found


def assert_form(arrangement, parts_by_id):
    activity = section_activity(arrangement, parts_by_id)
    theme = activity["Theme"]
    pulse = activity["Pulse"]
    opened = activity["Open"]
    returning = activity["Return"]
    if not {"drums", "percussion", "bass", "lead"} <= theme["roles"]:
        raise ValueError(f"{arrangement['kit_id']} theme is missing drums, percussion, bass, or lead")
    if "rhythm" in theme["roles"] or "rhythm" in returning["roles"]:
        raise ValueError(f"{arrangement['kit_id']} theme or return still has the rhythmic synth")
    if "lead" in pulse["roles"]:
        raise ValueError(f"{arrangement['kit_id']} pulse section still has the lead")
    if "rhythm" not in pulse["roles"]:
        raise ValueError(f"{arrangement['kit_id']} pulse section has no rhythmic synth")
    forbidden = {"drums", "percussion", "bass", "lead"}
    if opened["roles"] & forbidden:
        raise ValueError(f"{arrangement['kit_id']} open section still has {opened['roles'] & forbidden}")
    if len(opened["notes"]) >= len(theme["notes"]) * 0.5:
        raise ValueError(
            f"{arrangement['kit_id']} open notes {len(opened['notes'])} "
            f"are not thinner than theme {len(theme['notes'])}"
        )
    if sum(note["duration"] for note in opened["notes"]) >= sum(note["duration"] for note in theme["notes"]):
        raise ValueError(f"{arrangement['kit_id']} open duration sum is not thinner")
    theme_lead = [note for note in theme["notes"] if note["role"] == "lead"]
    return_lead = [note for note in returning["notes"] if note["role"] == "lead"]
    if not theme_lead or not return_lead:
        raise ValueError(f"{arrangement['kit_id']} missing lead in theme or return")
    theme_rel = tuple(sorted(
        (note["start"] - theme["start"], note["pitch"], note["duration"], note["velocity"])
        for note in theme_lead
    ))
    return_rel = tuple(sorted(
        (note["start"] - returning["start"], note["pitch"], note["duration"], note["velocity"])
        for note in return_lead
    ))
    if theme_rel != return_rel:
        raise ValueError(f"{arrangement['kit_id']} return does not restate the lead")
    return {
        "theme_notes": len(theme["notes"]),
        "pulse_notes": len(pulse["notes"]),
        "open_notes": len(opened["notes"]),
        "return_notes": len(returning["notes"]),
        "theme_roles": sorted(theme["roles"]),
        "open_roles": sorted(opened["roles"]),
        "return_lead": sorted({note["source"] for note in return_lead})[0],
        "open_note_ratio": round(len(opened["notes"]) / len(theme["notes"]), 3),
    }


def _excerpt_ok(arrangement, parts_by_id):
    start = EXCERPT_START_BAR * BAR
    end = (EXCERPT_START_BAR + EXCERPT_BARS) * BAR
    for track in arrangement["tracks"]:
        for placement in track.get("placements") or []:
            part = parts_by_id[placement["source_part"]]
            shift = placement["start_bar"] * BAR
            for note in part["notes"]:
                abs_start = note["performed_start"] + shift
                abs_stop = abs_start + note["duration"]
                if abs_start < start < abs_stop or abs_start < end < abs_stop:
                    raise ValueError(f"excerpt split {part['id']} at {abs_start}")


def _rhythm_develops(part):
    bars = [[] for _ in range(8)]
    for note in part["notes"]:
        bars[note["performed_start"] // BAR].append(note["pitch"])
    if not bars[0] or not bars[1] or bars[0] == bars[1]:
        raise ValueError(f"{part['id']} pulse does not develop between bar 1 and bar 2")
    if any(bars[index] for index in range(4, 8)):
        raise ValueError(f"{part['id']} pulse A continues past bar 4")


def _region_notes(part, start_bar, bar_count):
    start = start_bar * BAR
    end = (start_bar + bar_count) * BAR
    found = [note for note in part["notes"] if start <= note["performed_start"] < end]
    pitches = sorted({note["pitch"] for note in found})
    return pitches


def _facts(kit, part_map):
    spell = kit["spell"]
    regions = []
    lead = part_map[f"{kit['id']}.lead.a"]
    ordered = sorted(lead["notes"], key=lambda note: (note["performed_start"], note["pitch"]))
    first, second = ordered[0], ordered[1]
    semitones = abs(second["pitch"] - first["pitch"])
    if semitones not in INTERVALS:
        raise ValueError(f"{lead['id']} opening interval {semitones}")
    opening = [spell_pitch(first["pitch"], spell), spell_pitch(second["pitch"], spell)]
    theme_line = (
        f"{lead['id']} opens {opening[0]} to {opening[1]}, a {INTERVALS[semitones]}."
    )
    bass = part_map[f"{kit['id']}.bass.a"]
    bass_hits = []
    for start_bar, _count, pitches in KEY_SPANS[kit["id"]]:
        notes = [note for note in bass["notes"] if note["performed_start"] // BAR == start_bar]
        if not notes:
            raise ValueError(f"{bass['id']} missing bar {start_bar + 1}")
        root = min(notes, key=lambda note: note["performed_start"])
        bass_hits.append(f"bar {start_bar + 1} {spell_pitch(root['pitch'], spell)}")
    bass_line = f"{bass['id']} starts {', '.join(bass_hits)}."
    departures = []
    for part in part_map.values():
        if part["kit_id"] != kit["id"]:
            continue
        for note in part["notes"]:
            if note["departure"]:
                departures.append(
                    f"{part['id']} {spell_pitch(note['pitch'], spell)} at tick {note['performed_start']} "
                    f"is outside {kit['collection_name']}."
                )
    return regions, theme_line, bass_line, departures, {
        "part_id": lead["id"],
        "opening": opening,
        "semitones": semitones,
        "interval": INTERVALS[semitones],
        "line": theme_line,
    }


def _copy(kit):
    if kit["id"] == "k01":
        return (
            "Iron Gate is D Mixolydian at 128. The keys hold one chord for two bars, then rest before the next. "
            "The motif leaves a rest on the downbeat, rises a minor third, and sits out two later bars. "
            "Drums keep the kick on beat 1 and the snare on beat 3. The pulse uses straight eighths for four bars and is silent after that.",
            "Motif B is an alternate file. It is not placed in the arrangement, so it does not sit on the theme. "
            "The pulse and the motif are in different sections. Do not stack them.",
            [
                "Keys A changes chord every two bars: D dominant seventh, C major seventh, G major seventh, A minor seventh.",
                "The open section is keys B, pulse B, and pad B. It has no drums, no bass, and no motif.",
                "The return places motif A again, with the same drums, bass, keys, and pad as the theme.",
            ],
        )
    if kit["id"] == "k02":
        return (
            "White Cove is A major at 126. The motif starts on the downbeat and falls a major third before it climbs. "
            "The keys enter late, after tick 240, and the drums use a clap on beat 3 instead of a snare. "
            "Keys B ends on G major. G3 in that chord and G4 in motif B are outside A major.",
            "The G major chord is only in keys B, and keys B is only in the open section. "
            "Motif B is not in the arrangement.",
            [
                "Keys A is A major seventh, D major, E major, then F# minor, two bars each.",
                "Sequence A steps every 640 ticks for four bars, then rests.",
                "Bass A follows A, D, E, and F#.",
            ],
        )
    if kit["id"] == "k03":
        return (
            "Glass Room is G Lydian at 132. Each keys A chord lasts four bars. The second chord includes C#, which is in G Lydian. "
            "The motif opens a perfect fourth and leaves long gaps. Sequence A moves in quarter notes. "
            "Keys B ends on C major. C4 in that chord and C5 in motif B are outside G Lydian.",
            "The raised fourth in motif A is C#5, and it is inside the collection. "
            "The C natural notes are the departures.",
            [
                "Keys A bars 1-4 are G major seventh. Bars 5-8 are D major seventh.",
                "The open section keeps the C major chord with a sparse pulse and a pad.",
                "Drums A still leave space: kick, hat, snare, hat, then a gap inside the bar.",
            ],
        )
    return (
        "Ferry Light is F major at 136. The motif moves by a major second, then a step down, with shorter notes than the other kits. "
        "The keys stab off the beat. The first chord is Bb major seventh. "
        "Bass B ends on F#3. Keys B ends on D major, which includes F#4. Motif B also sounds F#4.",
        "Bb is in F major. The three F# notes are outside F major. They are not a modulation. "
        "Motif B is an alternate and is not stacked on the return.",
        [
            "Keys A is Bb major seventh, F major, D minor seventh, then C major.",
            "Sequence A is sixteenth notes for four bars, then silence. It does not play with the motif.",
            "The return restates motif A from F5.",
        ],
    )


def compose():
    catalog_kits = kits()
    parts = []
    for kit in catalog_kits:
        bucket = _events(kit)
        for role in ROLE_ORDER:
            for variation in ("a", "b"):
                part = Part(kit, role, variation)
                paint(part, bucket[role][variation])
                parts.append(part.finish())
    assert_collections(catalog_kits, parts)
    identity = assert_identities(parts)
    if len(parts) != 48 or any(not part["core"] for part in parts):
        raise ValueError("expected 48 core parts")
    by_id = {part["id"]: part for part in parts}
    for kit in catalog_kits:
        _rhythm_develops(by_id[f"{kit['id']}.rhythm.a"])
        regions, theme_line, bass_line, departures, theme = _facts(kit, by_id)
        identity_text, limitations, cycles = _copy(kit)
        if not departures:
            raise ValueError(f"{kit['id']} expected a departure")
        kit["identity"] = identity_text
        kit["limitations"] = limitations
        kit["cycles"] = cycles
        kit["chord_regions"] = regions
        kit["chord_lines"] = [region["line"] for region in regions]
        kit["theme"] = theme
        kit["theme_line"] = theme_line
        kit["bass_line"] = bass_line
        kit["departures"] = departures
    arrangements = [_arrangement(kit, by_id) for kit in catalog_kits]
    form_report = {}
    for arrangement in arrangements:
        _excerpt_ok(arrangement, by_id)
        form_report[arrangement["kit_id"]] = assert_form(arrangement, by_id)
        stats = form_report[arrangement["kit_id"]]
        arrangement["description"] = (
            f"{arrangement['kit_id']} 32-bar arrangement. "
            f"Theme {stats['theme_notes']} notes. Pulse {stats['pulse_notes']} notes. "
            f"Open {stats['open_notes']} notes, roles {', '.join(stats['open_roles'])}, "
            f"ratio {stats['open_note_ratio']} of the theme, no drums, no bass, no motif. "
            f"Return {stats['return_notes']} notes and restates {stats['return_lead']}."
        )
    preview = arrangements[0]
    excerpt_ticks = EXCERPT_BARS * BAR
    start_tick = EXCERPT_START_BAR * BAR
    excerpt_seconds = (excerpt_ticks / PPQ) * (preview["tempo_us"] / 1_000_000)
    full_seconds = (preview["container_ticks"] / PPQ) * (preview["tempo_us"] / 1_000_000)
    if not 10 <= excerpt_seconds <= 40:
        raise ValueError(f"excerpt {excerpt_seconds}")
    if full_seconds <= 40:
        raise ValueError("32-bar arrangement unexpectedly fits the preview limit")
    catalog = {
        "pack_id": PACK_ID,
        "pack_name": PACK_NAME,
        "catalog_version": GENERATOR_VERSION,
        "generator_version": GENERATOR_VERSION,
        "kind": "construction-kit",
        "ppq": PPQ,
        "c4": 60,
        "meter": {"numerator": 4, "denominator": 4, "bar_ticks": BAR},
        "part_bars": PART_BARS,
        "arrangement_bars": ARRANGEMENT_BARS,
        "excerpt_bars": EXCERPT_BARS,
        "drum_channel_index": 9,
        "drum_channel_number": 10,
        "drum_map": {str(pitch): name for pitch, name in sorted(DRUM_MAP.items())},
        "channels": CHANNEL,
        "core_roles": list(ROLE_ORDER),
        "note_policy": "Note-only MIDI. No program changes, controllers, pitch bend, aftertouch, or SysEx.",
        "microtiming": "offset is 0; performed_start = nominal_start",
        "listening": "No human listening audition was performed for this build.",
        "form_note": (
            "Every arrangement is theme, pulse, open, return. "
            "The open section is thinner and has no drums, percussion, bass, or lead. "
            "The return restates motif A. Motif and pulse do not share a section. A bar stays 3840 ticks."
        ),
        "stochastic_draws": 0,
        "seed_meaning": "Seeds identify kits. Nothing is random.",
        "core_part_count": 48,
        "reference_part_count": 0,
        "style_note": (
            "Darksynth is a creative label here. It is not a claim of scene membership or a fixed genre boundary."
        ),
        "range_statement": (
            "Drums use MIDI channel index 9, the GM channel 10, and only the mapped pitches "
            "36 kick, 37 side stick, 38 acoustic snare, 39 clap, 40 electric snare, 42 closed hat, "
            "46 open hat, and 49 crash. Bass is monophonic, MIDI 41 to 62, channel 1, and it avoids the drum pitches. "
            "Harmonic keys allow four notes, MIDI 48 to 76, channel 2. "
            "Motif is monophonic, MIDI 60 to 86, channel 3. "
            "Sequence is monophonic, MIDI 52 to 81, channel 4. "
            "Pad allows four notes, MIDI 48 to 81, channel 5. C4 is 60."
        ),
        "kits": [{
            key: kit[key] for key in (
                "id", "slug", "title", "bpm", "tempo_us", "effective_bpm", "part_bars", "arrangement_bars",
                "meter", "bar_ticks", "tonic", "tonal_reference", "collection_name", "pitch_classes",
                "spell", "departures", "seed", "identity", "limitations", "cycles", "stochastic_draws",
                "chord_regions", "chord_lines", "theme", "theme_line", "bass_line",
            )
        } for kit in catalog_kits],
        "parts": [{
            "id": part["id"],
            "study_id": part["study_id"],
            "kit_id": part["kit_id"],
            "role": part["role"],
            "variation": part["variation"],
            "core": part["core"],
            "channel": part["channel"],
            "path": part["path"],
            "notes": len(part["notes"]),
            "container_bars": part["container_bars"],
            "bpm": part["bpm"],
            "monophonic": part["monophonic"],
        } for part in parts],
        "arrangements": arrangements,
        "arrangement": preview,
        "form_report": form_report,
        "preview_excerpt": {
            "kit_id": "k01",
            "arrangement_path": preview["path"],
            "bars": "17-31 of the 32-bar arrangement",
            "start_bar": EXCERPT_START_BAR,
            "start_tick": start_tick,
            "end_tick": start_tick + excerpt_ticks,
            "score_seconds": excerpt_seconds,
            "full_arrangement_seconds": full_seconds,
            "reason": (
                "The preview is an excerpt of the 32-bar Iron Gate arrangement. "
                "Bars 17-24 are the open section. Bars 25-31 are the start of the return, and the return restates lead A. "
                "Bars 1-16, the opening theme and the pulse, stay in the MIDI and are not in the MP3. "
                "The full arrangement is longer than 40 seconds."
            ),
        },
        "stack_warning": (
            "Use either the combined arrangement or the separate parts. "
            "Do not stack the part files on top of the combined file."
        ),
    }
    score = {
        "pack_id": PACK_ID,
        "generator_version": GENERATOR_VERSION,
        "ppq": PPQ,
        "parts": parts,
        "arrangements": arrangements,
        "arrangement": preview,
        "excerpt": catalog["preview_excerpt"],
        "identity_check": identity,
        "form_report": form_report,
    }
    return {"catalog": catalog, "score": score}
