"""Reopen delivered MIDI bytes and compare them with the canonical score.

The report records hashes of the files it checked. It does not hash itself.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from tools.compose import INTERVALS, chord_name, spell_pitch
from tools.midi_io import (
    BAR_TICKS_4_4,
    PPQ,
    bpm_to_us,
    effective_bpm,
    notes_to_events,
    pair_notes,
    parse_midi,
    preamble,
    write_midi,
)

VALIDATOR_VERSION = "1.0.0"
PITCH_LO = 28
PITCH_HI = 86
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
ROLE_LIMITS = {
    "drums": {"lo": 36, "hi": 49, "poly": 4},
    "percussion": {"lo": 36, "hi": 49, "poly": 4},
    "bass": {"lo": 41, "hi": 62, "poly": 1},
    "rhythm": {"lo": 52, "hi": 81, "poly": 1},
    "lead": {"lo": 60, "hi": 86, "poly": 1},
    "pad": {"lo": 48, "hi": 81, "poly": 4},
}
ROLE_NAME = {
    "drums": "Drums",
    "percussion": "Percussion",
    "bass": "Bass",
    "rhythm": "Rhythmic Synth",
    "lead": "Lead",
    "pad": "Pad",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def dump_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _shifted_notes(part: dict, start_bar: int) -> list[dict]:
    shift = start_bar * BAR_TICKS_4_4
    shifted = []
    for note in part["notes"]:
        copy = dict(note)
        copy["performed_start"] = note["performed_start"] + shift
        shifted.append(copy)
    return shifted


def _arrangement_tracks(arrangement: dict, by_id: dict) -> list[tuple[list[dict], int]]:
    container = arrangement["container_ticks"]
    tracks = [(preamble("Conductor", arrangement["tempo_us"], container), container)]
    musical = [track for track in arrangement["tracks"] if track.get("placements")]
    if len(musical) != len(arrangement["tracks"]) - 1:
        raise ValueError("arrangement spec needs one conductor and one track per placed role")
    for track in musical:
        events = [{"type": "track_name", "tick": 0, "name": track["name"]}]
        for placement in track["placements"]:
            part = by_id[placement["source_part"]]
            events += notes_to_events(_shifted_notes(part, placement["start_bar"]))
        tracks.append((events, container))
    return tracks


def write_midi_files(root: Path, score: dict) -> None:
    for part in score["parts"]:
        events = preamble(ROLE_NAME[part["role"]], part["tempo_us"], part["container_ticks"])
        events += notes_to_events(part["notes"])
        write_midi(root / part["path"], 0, [(events, part["container_ticks"])])
    by_id = {part["id"]: part for part in score["parts"]}
    seen = set()
    for arrangement in score.get("arrangements") or [score["arrangement"]]:
        if arrangement["path"] in seen:
            continue
        seen.add(arrangement["path"])
        write_midi(root / arrangement["path"], 1, _arrangement_tracks(arrangement, by_id))


def _meta(track: dict, meta_type: int) -> list[dict]:
    return [event for event in track["events"] if event["type"] == "meta" and event["meta_type"] == meta_type]


def _tempo_us(track: dict) -> int | None:
    found = _meta(track, 0x51)
    if len(found) != 1:
        return None
    data = found[0]["data"]
    if len(data) != 3 or found[0]["tick"] != 0:
        return None
    return (data[0] << 16) | (data[1] << 8) | data[2]


def _meter(track: dict) -> tuple[int, int] | None:
    found = _meta(track, 0x58)
    if len(found) != 1 or found[0]["tick"] != 0 or len(found[0]["data"]) != 4:
        return None
    numerator = found[0]["data"][0]
    denominator = 1 << found[0]["data"][1]
    return numerator, denominator


def _note_key(note: dict) -> tuple:
    return (note["channel"], note["pitch"], note["start"], note["duration"], note["velocity"])


def _overlaps(notes: list[dict], monophonic: bool) -> str | None:
    ordered = sorted(notes, key=lambda note: (note["start"], note["pitch"]))
    for index, left in enumerate(ordered):
        left_end = left["start"] + left["duration"]
        for right in ordered[index + 1:]:
            if right["start"] >= left_end:
                break
            if monophonic or left["pitch"] == right["pitch"]:
                return f"{left['pitch']}@{left['start']} overlaps {right['pitch']}@{right['start']}"
    return None


def _max_poly(notes: list[dict]) -> int:
    points = []
    for note in notes:
        points.append((note["start"], 1))
        points.append((note["start"] + note["duration"], -1))
    points.sort(key=lambda item: (item[0], item[1]))
    active = 0
    peak = 0
    for _, delta in points:
        active += delta
        peak = max(peak, active)
    return peak


def _same_tick_order(track: dict) -> str | None:
    by_tick: dict[int, list[str]] = {}
    for event in track["events"]:
        if event["type"] in ("note_on", "note_off"):
            by_tick.setdefault(event["tick"], []).append(event["type"])
    for tick, kinds in by_tick.items():
        seen_on = False
        for kind in kinds:
            if kind == "note_on":
                seen_on = True
            elif kind == "note_off" and seen_on:
                return f"note-off follows note-on at tick {tick}"
    return None


def _check_part_file(path: Path, part: dict, pitch_classes: set[int]) -> tuple[dict, list[str], list[dict]]:
    errors = []
    data = path.read_bytes()
    record = {
        "path": part["path"],
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "role": part["role"],
        "core": part["core"],
        "checks": {},
    }
    try:
        parsed = parse_midi(data)
    except Exception as exc:  # noqa: BLE001 - the message is the validation evidence
        record["checks"]["parse"] = f"FAIL {exc}"
        errors.append(f"{part['path']} parse: {exc}")
        return record, errors, []
    record["format"] = parsed["format"]
    record["ppq"] = parsed["ppq"]
    record["tracks"] = len(parsed["tracks"])
    if parsed["format"] != 0:
        errors.append(f"{part['path']} format {parsed['format']}")
    if parsed["ppq"] != PPQ:
        errors.append(f"{part['path']} ppq {parsed['ppq']}")
    if len(parsed["tracks"]) != 1:
        errors.append(f"{part['path']} track count")
        return record, errors, []
    track = parsed["tracks"][0]
    if track["eot_tick"] != part["container_ticks"]:
        errors.append(f"{part['path']} eot {track['eot_tick']} != {part['container_ticks']}")
    tempo = _tempo_us(track)
    meter = _meter(track)
    record["tempo_us"] = tempo
    record["requested_bpm"] = part["bpm"]
    record["effective_bpm"] = None if tempo is None else effective_bpm(tempo)
    record["meter"] = None if meter is None else f"{meter[0]}/{meter[1]}"
    if tempo != part["tempo_us"]:
        errors.append(f"{part['path']} tempo {tempo} != {part['tempo_us']}")
    if meter != (4, 4):
        errors.append(f"{part['path']} meter {meter}")
    unexpected = [
        event for event in track["events"]
        if event["type"] in ("sysex", "channel") or (event["type"] == "meta" and event["meta_type"] not in (0x03, 0x51, 0x58, 0x2F))
    ]
    if unexpected:
        errors.append(f"{part['path']} unexpected messages {[event['type'] for event in unexpected]}")
    order_error = _same_tick_order(track)
    if order_error:
        errors.append(f"{part['path']} {order_error}")
    try:
        notes = pair_notes(track)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{part['path']} pairing: {exc}")
        return record, errors, []
    record["notes"] = len(notes)
    record["channels"] = sorted({note["channel"] for note in notes})
    for note in notes:
        end = note["start"] + note["duration"]
        if note["start"] < 0 or note["duration"] <= 0 or note["start"] >= part["container_ticks"] or end > part["container_ticks"]:
            errors.append(f"{part['path']} boundary {note}")
            break
        if not 1 <= note["velocity"] <= 127:
            errors.append(f"{part['path']} velocity {note['velocity']}")
            break
    if part["role"] == "kick-reference":
        if any(note["channel"] != 9 or note["pitch"] != 36 for note in notes):
            errors.append(f"{part['path']} percussion map")
    elif part["role"] in ("drums", "percussion"):
        if any(note["channel"] != 9 or note["pitch"] not in DRUM_MAP for note in notes):
            errors.append(f"{part['path']} drum map")
    else:
        if any(note["channel"] != part["channel"] for note in notes):
            errors.append(f"{part['path']} channel")
        limits = ROLE_LIMITS[part["role"]]
        if any(not limits["lo"] <= note["pitch"] <= limits["hi"] for note in notes):
            errors.append(f"{part['path']} range")
        for note in notes:
            in_collection = (note["pitch"] % 12) in pitch_classes
            if not in_collection:
                record.setdefault("outside_collection", 0)
                record["outside_collection"] += 1
    overlap = _overlaps(notes, monophonic=part["monophonic"])
    if overlap:
        errors.append(f"{part['path']} {overlap}")
    limits = ROLE_LIMITS.get(part["role"])
    if limits and _max_poly(notes) > limits["poly"]:
        errors.append(f"{part['path']} polyphony {_max_poly(notes)} > {limits['poly']}")
    record["max_polyphony"] = _max_poly(notes)
    record["checks"] = {
        "parse": "PASS",
        "ppq": parsed["ppq"],
        "tempo": tempo,
        "meter": record["meter"],
        "eot": track["eot_tick"],
        "notes": len(notes),
        "overlap": "PASS" if overlap is None else overlap,
    }
    return record, errors, notes


def _negative_tests() -> dict:
    results = {}
    bad_notes = [
        {"channel": 0, "pitch": 40, "performed_start": 0, "duration": 480, "velocity": 80},
        {"channel": 0, "pitch": 42, "performed_start": 240, "duration": 240, "velocity": 80},
    ]
    events = preamble("Bassline", bpm_to_us(140), BAR_TICKS_4_4) + notes_to_events(bad_notes)
    path = Path("/tmp/darksynth-negative-overlap.mid")
    write_midi(path, 0, [(events, BAR_TICKS_4_4)])
    parsed = parse_midi(path.read_bytes())
    notes = pair_notes(parsed["tracks"][0])
    overlap = _overlaps(notes, monophonic=True)
    results["monophonic_overlap_detected"] = "PASS" if overlap else "FAIL"
    try:
        write_midi(path, 0, [(events, 100)])
        results["boundary_rejected_at_write"] = "FAIL"
    except ValueError:
        results["boundary_rejected_at_write"] = "PASS"
    path.unlink(missing_ok=True)
    return results


def _identity(parts_meta: list[dict], reopened: dict) -> dict:
    errors = []
    by_role = {}
    signatures = {}
    summary = []
    for part in parts_meta:
        if not part.get("core", True):
            continue
        notes = reopened.get(part["id"])
        if notes is None:
            errors.append(f"identity missing {part['id']}")
            continue
        signature = tuple(sorted((note["start"], note["pitch"], note["duration"]) for note in notes))
        if signature in signatures:
            errors.append(f"{part['id']} duplicates {signatures[signature]}")
        signatures[signature] = part["id"]
        kit_id = part.get("kit_id", part["study_id"])
        by_role.setdefault(part["role"], {}).setdefault(kit_id, {})[part["variation"]] = notes
    for role, kits_map in by_role.items():
        attack_seen = {}
        start_seen = {}
        for kit_id, variations in kits_map.items():
            if "a" not in variations or "b" not in variations:
                errors.append(f"{kit_id} {role} missing a variation")
                continue
            left = variations["a"]
            right = variations["b"]
            if {note["start"] for note in left} == {note["start"] for note in right}:
                errors.append(f"{kit_id} {role} A and B share starts")
            if {note["pitch"] for note in left} == {note["pitch"] for note in right}:
                errors.append(f"{kit_id} {role} A and B share pitches")
            if {note["duration"] for note in left} == {note["duration"] for note in right}:
                errors.append(f"{kit_id} {role} A and B share durations")
            attacks = tuple(sorted((note["start"], note["pitch"]) for note in left))
            starts = tuple(sorted(note["start"] for note in left))
            if attacks in attack_seen:
                errors.append(f"{kit_id} {role} A attack tuple repeats {attack_seen[attacks]}")
            if starts in start_seen:
                errors.append(f"{kit_id} {role} A start tuple repeats {start_seen[starts]}")
            attack_seen[attacks] = kit_id
            start_seen[starts] = kit_id
            if _same_velocity_transpose(left, right):
                errors.append(f"{kit_id} {role} B is a transposition of A with the same velocities")
            summary.append({"kit_id": kit_id, "role": role, "a": len(left), "b": len(right)})
    pitched = []
    for part in parts_meta:
        if part.get("role") == "drums" or part["id"] not in reopened:
            continue
        pitched.append((part["id"], reopened[part["id"]]))
    for index, (left_id, left) in enumerate(pitched):
        for right_id, right in pitched[index + 1:]:
            if _same_velocity_transpose(left, right):
                errors.append(f"{left_id} and {right_id} are transposed copies with the same velocities")
    return {
        "result": "FAIL" if errors else "PASS",
        "errors": errors,
        "kits": summary,
        "method": "Per core role, A and B differ in start, pitch, and duration. Variation A attack tuples are not shared across kits. No part is a transposition of another part that keeps the same velocities.",
    }


def _same_velocity_transpose(left, right):
    ordered_left = sorted(left, key=lambda note: (note["start"], note["pitch"]))
    ordered_right = sorted(right, key=lambda note: (note["start"], note["pitch"]))
    if len(ordered_left) != len(ordered_right) or not ordered_left:
        return False
    for first, second in zip(ordered_left, ordered_right):
        if first["start"] != second["start"] or first["duration"] != second["duration"] or first["velocity"] != second["velocity"]:
            return False
    deltas = {second["pitch"] - first["pitch"] for first, second in zip(ordered_left, ordered_right)}
    return len(deltas) == 1 and 0 not in deltas


def _bar_span(label: str) -> tuple[int, int]:
    left, right = label.split("-")
    start = int(left) - 1
    return start, int(right) - start


def _names(catalog: dict, reopened: dict) -> list[str]:
    errors = []
    for kit in catalog["kits"]:
        spell = kit["spell"]
        for region in kit["chord_regions"]:
            start, count = _bar_span(region["bars"])
            begin = start * BAR_TICKS_4_4
            end = (start + count) * BAR_TICKS_4_4
            notes = [note for note in reopened[region["part_id"]] if begin <= note["start"] < end]
            pitches = sorted({note["pitch"] for note in notes})
            if pitches != sorted(region["pitches"]):
                errors.append(f"{region['part_id']} bars {region['bars']} heard {pitches}")
                continue
            name = chord_name(pitches, spell)
            spelling = " ".join(spell_pitch(pitch, spell) for pitch in pitches)
            line = f"{region['part_id']} bars {region['bars']} are {name}: {spelling}."
            if name != region["name"] or spelling != region["spelling"] or region["line"] != line:
                errors.append(f"chord name drifted for {region['part_id']} bars {region['bars']}")
            if line not in kit["chord_lines"]:
                errors.append(f"catalog omitted {line}")
        lead_notes = sorted(reopened[kit["theme"]["part_id"]], key=lambda note: (note["start"], note["pitch"]))
        first, second = lead_notes[0], lead_notes[1]
        semitones = abs(second["pitch"] - first["pitch"])
        opening = [spell_pitch(first["pitch"], spell), spell_pitch(second["pitch"], spell)]
        line = f"{kit['theme']['part_id']} opens {opening[0]} to {opening[1]}, a {INTERVALS[semitones]}."
        if opening != kit["theme"]["opening"] or semitones != kit["theme"]["semitones"] or kit["theme_line"] != line:
            errors.append(f"{kit['id']} theme name does not match the lead")
    return errors


def _section_notes(arrangement: dict, reopened: dict, name: str) -> tuple[list[dict], set[str], int]:
    section = next(item for item in arrangement["sections"] if item["name"] == name)
    origin = section["start_bar"] * BAR_TICKS_4_4
    notes = []
    roles = set()
    for track in arrangement["tracks"]:
        if not track.get("placements"):
            continue
        for placement in track["placements"]:
            if placement["start_bar"] != section["start_bar"]:
                continue
            roles.add(track["role"])
            for note in reopened[placement["source_part"]]:
                notes.append({
                    "role": track["role"],
                    "start": note["start"] + origin,
                    "duration": note["duration"],
                    "pitch": note["pitch"],
                    "velocity": note["velocity"],
                    "source": placement["source_part"],
                })
    return notes, roles, origin


def _relative(notes: list[dict], origin: int, role: str) -> tuple:
    return tuple(sorted(
        (note["start"] - origin, note["pitch"], note["duration"], note["velocity"])
        for note in notes
        if note["role"] == role
    ))


def _lead_shape(notes: list[dict]) -> tuple:
    ordered = sorted(notes, key=lambda note: (note["start"], note["pitch"]))
    pitch0 = ordered[0]["pitch"]
    tick0 = ordered[0]["start"]
    return tuple(
        (note["pitch"] - pitch0, note["duration"], note["start"] - tick0)
        for note in ordered
    )


def _form_bytes(score: dict, reopened: dict) -> dict:
    errors = []
    kits = {}
    for arrangement in score["arrangements"]:
        theme, theme_roles, theme_origin = _section_notes(arrangement, reopened, "Theme")
        pulse, pulse_roles, _pulse_origin = _section_notes(arrangement, reopened, "Pulse")
        opened, open_roles, _open_origin = _section_notes(arrangement, reopened, "Open")
        returning, _return_roles, return_origin = _section_notes(arrangement, reopened, "Return")
        kit_id = arrangement["kit_id"]
        if open_roles & {"drums", "percussion", "bass", "lead"}:
            errors.append(f"{kit_id} open section still has drums, percussion, bass, or lead")
        if not {"drums", "percussion", "bass", "lead"} <= theme_roles:
            errors.append(f"{kit_id} theme is missing drums, percussion, bass, or lead")
        if "lead" in pulse_roles:
            errors.append(f"{kit_id} pulse section still has the lead")
        if "rhythm" not in pulse_roles:
            errors.append(f"{kit_id} pulse section has no rhythmic synth")
        if len(opened) >= len(theme) * 0.5:
            errors.append(f"{kit_id} open section is not thinner than the theme")
        if sum(note["duration"] for note in opened) >= sum(note["duration"] for note in theme):
            errors.append(f"{kit_id} open duration sum is not thinner")
        if _relative(theme, theme_origin, "lead") != _relative(returning, return_origin, "lead"):
            errors.append(f"{kit_id} return does not restate the lead")
        claimed = score["form_report"][kit_id]
        if claimed["theme_notes"] != len(theme) or claimed["open_notes"] != len(opened):
            errors.append(f"{kit_id} form report does not match reopened notes")
        kits[kit_id] = {
            "theme_notes": len(theme),
            "open_notes": len(opened),
            "open_roles": sorted(open_roles),
            "return_matches_theme": True,
        }
    shapes = {}
    for part in score["parts"]:
        if part["role"] != "lead" or part["variation"] != "a":
            continue
        shape = _lead_shape(reopened[part["id"]])
        if shape in shapes:
            errors.append(f"{part['kit_id']} lead A contour repeats {shapes[shape]}")
        shapes[shape] = part["id"]
    if len(shapes) != 4:
        errors.append("lead hooks are not four distinct lines")
    return {"errors": errors, "kits": kits, "lead_themes": len(shapes)}


def validate_tree(root: Path) -> dict:
    catalog = load_json(root / "catalog" / "catalog-Cursor.json")
    score = load_json(root / "score" / "canonical-score-Cursor.json")
    errors = []
    if catalog["pack_id"] != score["pack_id"]:
        errors.append("pack id mismatch")
    containers = catalog.get("kits") or catalog.get("studies") or []
    pitch_sets = {item["id"]: set(item["pitch_classes"]) for item in containers}
    file_records = []
    reopened = {}
    for part in score["parts"]:
        path = root / part["path"]
        if not path.is_file():
            errors.append(f"missing {part['path']}")
            continue
        kit_id = part.get("kit_id", part["study_id"])
        record, part_errors, notes = _check_part_file(path, part, pitch_sets[kit_id])
        errors.extend(part_errors)
        expected = Counter(_note_key({
            "channel": note["channel"],
            "pitch": note["pitch"],
            "start": note["performed_start"],
            "duration": note["duration"],
            "velocity": note["velocity"],
        }) for note in part["notes"])
        actual = Counter(_note_key(note) for note in notes)
        if expected != actual:
            errors.append(f"{part['path']} does not match the canonical score")
            record["score_agreement"] = "FAIL"
        else:
            record["score_agreement"] = "PASS"
        departures = [note for note in part["notes"] if note["departure"]]
        if part["role"] not in ("drums", "percussion", "kick-reference"):
            for note in departures:
                if (note["pitch"] % 12) in pitch_sets[kit_id]:
                    errors.append(f"{part['id']} departure {note['pitch']} is inside the collection")
            for note in part["notes"]:
                if note["departure"]:
                    continue
                if (note["pitch"] % 12) not in pitch_sets[kit_id]:
                    errors.append(f"{part['id']} note {note['pitch']} left the collection without a departure flag")
        record["departures"] = len(departures)
        file_records.append(record)
        reopened[part["id"]] = notes

    def check_arrangement(arrangement: dict) -> dict:
        record = {"path": arrangement["path"], "kit_id": arrangement.get("kit_id")}
        path = root / arrangement["path"]
        if not path.is_file():
            errors.append(f"missing {arrangement['path']}")
            return record
        data = path.read_bytes()
        record.update({"bytes": len(data), "sha256": sha256_bytes(data)})
        parsed = parse_midi(data)
        declared = len(arrangement["tracks"])
        musical = [track for track in arrangement["tracks"] if track.get("placements")]
        conductors = [track for track in arrangement["tracks"] if not track.get("placements")]
        record.update({
            "format": parsed["format"],
            "ppq": parsed["ppq"],
            "tracks": len(parsed["tracks"]),
            "declared_tracks": declared,
            "musical_tracks": len(musical),
        })
        if parsed["format"] != 1 or parsed["ppq"] != PPQ or len(parsed["tracks"]) != declared:
            errors.append(f"{arrangement['path']} header")
        if len(conductors) != 1 or len(musical) != declared - len(conductors):
            errors.append(f"{arrangement['path']} track count does not follow the arrangement spec")
        conductor = parsed["tracks"][0]
        if _tempo_us(conductor) != arrangement["tempo_us"] or _meter(conductor) != (4, 4):
            errors.append(f"{arrangement['path']} conductor tempo or meter")
        if pair_notes(conductor):
            errors.append(f"{arrangement['path']} conductor has notes")
        if conductor["eot_tick"] != arrangement["container_ticks"]:
            errors.append(f"{arrangement['path']} conductor boundary")
        for index, track_spec in enumerate(musical, start=1):
            if index >= len(parsed["tracks"]):
                errors.append(f"{arrangement['path']} missing {track_spec['name']}")
                continue
            track = parsed["tracks"][index]
            if _meta(track, 0x51) or _meta(track, 0x58):
                errors.append(f"tempo or meter leaked onto {track_spec['name']}")
            if track["eot_tick"] != arrangement["container_ticks"]:
                errors.append(f"{track_spec['name']} boundary")
            if _same_tick_order(track):
                errors.append(f"{track_spec['name']} note order")
            notes = pair_notes(track)
            expected = Counter()
            role = track_spec.get("role")
            limits = ROLE_LIMITS.get(role) if role else None
            for placement in track_spec["placements"]:
                source = reopened.get(placement["source_part"], [])
                shift = placement["start_bar"] * BAR_TICKS_4_4
                for note in source:
                    moved = dict(note)
                    moved["start"] = note["start"] + shift
                    if moved["start"] + moved["duration"] > arrangement["container_ticks"]:
                        errors.append(f"{track_spec['name']} placement overflows")
                    expected[_note_key(moved)] += 1
            if Counter(_note_key(note) for note in notes) != expected:
                errors.append(f"arrangement {track_spec['name']} disagrees with its placements")
            if role in ("drums", "percussion") and any(note["channel"] != 9 or note["pitch"] not in DRUM_MAP for note in notes):
                errors.append(f"{track_spec['name']} drum map")
            mono = role in ("bass", "rhythm", "lead")
            overlap = _overlaps(notes, monophonic=mono)
            if overlap:
                errors.append(f"{arrangement['path']} {track_spec['name']} {overlap}")
            if limits and _max_poly(notes) > limits["poly"]:
                errors.append(f"{arrangement['path']} {track_spec['name']} polyphony")
        record["agreement"] = "PASS" if not any(arrangement["path"] in item or item.startswith("arrangement") or item.startswith("tempo") for item in errors) else "FAIL"
        return record

    arrangement_records = [check_arrangement(item) for item in (score.get("arrangements") or [score["arrangement"]])]
    preview_path = score["arrangement"]["path"]
    arrangement_record = next(record for record in arrangement_records if record["path"] == preview_path)
    identity = _identity(score["parts"], reopened)
    if identity["result"] != "PASS":
        errors.extend(identity["errors"])
    if len(reopened) == len(score["parts"]):
        form_check = _form_bytes(score, reopened)
        errors.extend(form_check["errors"])
    else:
        form_check = {"errors": ["form check skipped because a part failed to reopen"], "kits": {}}
        errors.extend(form_check["errors"])
    if len(reopened) == len(score["parts"]):
        name_errors = _names(catalog, reopened)
        errors.extend(name_errors)
    else:
        name_errors = ["name check skipped because a part failed to reopen"]
        errors.extend(name_errors)
    negative = _negative_tests()
    if any(value != "PASS" for value in negative.values()):
        errors.append(f"negative tests {negative}")
    report = {
        "validator_version": VALIDATOR_VERSION,
        "generator_version": score["generator_version"],
        "pack_id": score["pack_id"],
        "catalog_path": "catalog/catalog-Cursor.json",
        "catalog_sha256": sha256_file(root / "catalog" / "catalog-Cursor.json"),
        "score_path": "score/canonical-score-Cursor.json",
        "score_sha256": sha256_file(root / "score" / "canonical-score-Cursor.json"),
        "result": "FAIL" if errors else "PASS",
        "errors": errors,
        "files": file_records,
        "arrangement": arrangement_record,
        "arrangements": arrangement_records,
        "identity_check": identity,
        "form_check": form_check,
        "name_check": name_errors,
        "negative_tests": negative,
        "percussion_map": {str(pitch): f"{name}, GM channel 10, MIDI channel index 9" for pitch, name in sorted(DRUM_MAP.items())},
        "repairs": [],
        "repair_note": "No repairs were applied. This report is the first validation pass of the delivered bytes.",
        "listening": "No human listening audition was performed for this build.",
        "rules": [
            "file exists and parses",
            "PPQ 960",
            "encoded tempo and 4/4 meter",
            "one end-of-track at the declared container",
            "explicit note pairing",
            "boundaries, velocity, range, monophonic bass, rhythm, and lead, percussion and pad polyphony cap",
            "drums use the explicit GM map on channel 10 (MIDI channel index 9)",
            "note-offs precede note-ons that share a tick",
            "no program changes or other channel messages",
            "reopened notes match the canonical score",
            "each arrangement track count follows that arrangement spec",
            "arrangement notes are the placed part files and carry no tempo",
            "core A and B differ in start, pitch, and duration; variation A attacks are not shared across kits",
            "open section is thinner and has no drums, percussion, bass, or lead",
            "return restates the theme lead with the same pitches, durations, and velocities",
            "lead and rhythmic synth do not share a section",
            "lead A contours are not transpositions of each other",
            "chord names and theme intervals match the reopened pitches",
        ],
    }
    return report
