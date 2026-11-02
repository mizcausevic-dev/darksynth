"""Note-only Standard MIDI File writer and parser.

PPQ is 960. C4 is MIDI note 60. Release velocity on explicit note-offs is 0.
This module does not write program changes, controllers, pitch bend, aftertouch,
keyswitches, SysEx, or tuning messages.
"""

from __future__ import annotations

import struct
from pathlib import Path

PPQ = 960
BAR_TICKS_4_4 = 3840  # numerator * PPQ * 4 / denominator

META_ORDER = {
    "track_name": 0,
    "tempo": 1,
    "meter": 2,
    "note_off": 3,
    "note_on": 4,
}

CHANNEL_DATA_LEN = {
    0x8: 2,
    0x9: 2,
    0xA: 2,
    0xB: 2,
    0xC: 1,
    0xD: 1,
    0xE: 2,
}


def bpm_to_us(bpm: int) -> int:
    if not isinstance(bpm, int) or isinstance(bpm, bool) or bpm <= 0:
        raise ValueError(f"BPM must be a positive integer, got {bpm!r}")
    return int((60_000_000 / bpm) + 0.5)


def effective_bpm(tempo_us: int) -> float:
    return 60_000_000 / tempo_us


def vlq(value: int) -> bytes:
    if value < 0:
        raise ValueError(f"negative VLQ {value}")
    buffer = [value & 0x7F]
    value >>= 7
    while value:
        buffer.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(buffer))


def _read_vlq(data: bytes, index: int) -> tuple[int, int]:
    value = 0
    consumed = 0
    while True:
        if index >= len(data):
            raise ValueError("truncated VLQ")
        byte = data[index]
        index += 1
        consumed += 1
        value = (value << 7) | (byte & 0x7F)
        if consumed > 4:
            raise ValueError("VLQ too long")
        if not (byte & 0x80):
            return value, index


def encode_event(event: dict) -> bytes:
    kind = event["type"]
    if kind == "track_name":
        raw = event["name"].encode("ascii")
        return bytes([0xFF, 0x03]) + vlq(len(raw)) + raw
    if kind == "tempo":
        us = event["us"]
        if not 1 <= us <= 0xFFFFFF:
            raise ValueError(f"tempo out of range: {us}")
        return bytes([0xFF, 0x51, 0x03, (us >> 16) & 0xFF, (us >> 8) & 0xFF, us & 0xFF])
    if kind == "meter":
        numerator = event["numerator"]
        denominator = event["denominator"]
        if denominator <= 0 or (denominator & (denominator - 1)) != 0:
            raise ValueError("denominator must be a positive power of two")
        dd = denominator.bit_length() - 1
        return bytes([0xFF, 0x58, 0x04, numerator, dd, 24, 8])
    if kind == "note_on":
        channel = event["channel"]
        pitch = event["pitch"]
        velocity = event["velocity"]
        if not 0 <= channel <= 15:
            raise ValueError(channel)
        if not 0 <= pitch <= 127 or not 1 <= velocity <= 127:
            raise ValueError((pitch, velocity))
        return bytes([0x90 | channel, pitch, velocity])
    if kind == "note_off":
        channel = event["channel"]
        pitch = event["pitch"]
        if not 0 <= channel <= 15 or not 0 <= pitch <= 127:
            raise ValueError((channel, pitch))
        return bytes([0x80 | channel, pitch, 0])
    raise ValueError(f"unsupported event {kind}")


def _sort_key(event: dict) -> tuple:
    return (
        event["tick"],
        META_ORDER[event["type"]],
        event.get("pitch", 0),
        event.get("channel", 0),
        event.get("name", ""),
    )


def encode_track(events: list[dict], container_ticks: int) -> bytes:
    if container_ticks <= 0:
        raise ValueError("container_ticks must be positive")
    ordered = sorted(events, key=_sort_key)
    payload = bytearray()
    last = 0
    for event in ordered:
        tick = event["tick"]
        if tick < last:
            raise ValueError("events moved backwards")
        if tick > container_ticks:
            raise ValueError(f"event at {tick} is past container {container_ticks}")
        payload += vlq(tick - last)
        payload += encode_event(event)
        last = tick
    if last > container_ticks:
        raise ValueError("track overruns container")
    payload += vlq(container_ticks - last)
    payload += bytes([0xFF, 0x2F, 0x00])
    return bytes(payload)


def write_midi(path: Path | str, format_type: int, tracks: list[tuple[list[dict], int]], ppq: int = PPQ) -> bytes:
    """Write a MIDI file and return the exact bytes written.

    Each track is (events, container_ticks). Format 0 must contain one track.
    """
    if format_type not in (0, 1):
        raise ValueError(format_type)
    if format_type == 0 and len(tracks) != 1:
        raise ValueError("format 0 requires exactly one track")
    if ppq != PPQ:
        raise ValueError("this pack fixes PPQ at 960")
    body = bytearray()
    body += b"MThd"
    body += struct.pack(">IHHH", 6, format_type, len(tracks), ppq)
    for events, container in tracks:
        chunk = encode_track(events, container)
        body += b"MTrk"
        body += struct.pack(">I", len(chunk))
        body += chunk
    data = bytes(body)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def parse_midi(data: bytes) -> dict:
    if len(data) < 14 or data[0:4] != b"MThd":
        raise ValueError("missing MThd")
    header_len, format_type, ntrks, division = struct.unpack(">IHHH", data[4:14])
    if header_len != 6:
        raise ValueError(f"unexpected header length {header_len}")
    if division & 0x8000:
        raise ValueError("SMPTE division is not used")
    index = 14
    tracks = []
    for _ in range(ntrks):
        if data[index:index + 4] != b"MTrk":
            raise ValueError("missing MTrk")
        length = struct.unpack(">I", data[index + 4:index + 8])[0]
        index += 8
        end = index + length
        if end > len(data):
            raise ValueError("truncated track")
        tracks.append(_parse_track(data[index:end]))
        index = end
    if index != len(data):
        raise ValueError(f"trailing bytes: {len(data) - index}")
    return {
        "format": format_type,
        "ppq": division,
        "tracks": tracks,
    }


def _parse_track(chunk: bytes) -> dict:
    index = 0
    tick = 0
    running = None
    events = []
    eot_tick = None
    while index < len(chunk):
        delta, index = _read_vlq(chunk, index)
        tick += delta
        if index >= len(chunk):
            raise ValueError("truncated event")
        status = chunk[index]
        if status < 0x80:
            if running is None:
                raise ValueError("running status without a prior status")
            status = running
        else:
            index += 1
            if status < 0xF0:
                running = status
            elif status < 0xF8:
                running = None
        if status == 0xFF:
            if index >= len(chunk):
                raise ValueError("truncated meta")
            meta_type = chunk[index]
            index += 1
            length, index = _read_vlq(chunk, index)
            payload = chunk[index:index + length]
            if len(payload) != length:
                raise ValueError("truncated meta payload")
            index += length
            if meta_type == 0x2F:
                if length != 0:
                    raise ValueError("end-of-track payload")
                if eot_tick is not None:
                    raise ValueError("more than one end-of-track")
                eot_tick = tick
                if index != len(chunk):
                    raise ValueError("bytes after end-of-track")
            events.append({"tick": tick, "type": "meta", "meta_type": meta_type, "data": bytes(payload)})
            continue
        if status in (0xF0, 0xF7):
            length, index = _read_vlq(chunk, index)
            index += length
            events.append({"tick": tick, "type": "sysex", "status": status})
            continue
        if status >= 0xF0:
            raise ValueError(f"unsupported system message {status:#x}")
        kind = status & 0xF0
        channel = status & 0x0F
        needed = CHANNEL_DATA_LEN[kind >> 4]
        data_bytes = chunk[index:index + needed]
        if len(data_bytes) != needed:
            raise ValueError("truncated channel message")
        index += needed
        if kind == 0x90 and data_bytes[1] == 0:
            events.append({
                "tick": tick,
                "type": "note_off",
                "channel": channel,
                "pitch": data_bytes[0],
                "velocity": 0,
                "implicit": True,
            })
        elif kind == 0x90:
            events.append({
                "tick": tick,
                "type": "note_on",
                "channel": channel,
                "pitch": data_bytes[0],
                "velocity": data_bytes[1],
            })
        elif kind == 0x80:
            events.append({
                "tick": tick,
                "type": "note_off",
                "channel": channel,
                "pitch": data_bytes[0],
                "velocity": data_bytes[1],
            })
        else:
            events.append({
                "tick": tick,
                "type": "channel",
                "status": kind,
                "channel": channel,
                "data": bytes(data_bytes),
            })
    if eot_tick is None:
        raise ValueError("missing end-of-track")
    return {"events": events, "eot_tick": eot_tick}


def pair_notes(track: dict) -> list[dict]:
    """Pair note-ons with later note-offs. Active interval is [start, end)."""
    open_notes: dict[tuple[int, int], list[dict]] = {}
    paired = []
    for event in track["events"]:
        if event["type"] == "note_on":
            key = (event["channel"], event["pitch"])
            open_notes.setdefault(key, []).append(event)
        elif event["type"] == "note_off":
            key = (event["channel"], event["pitch"])
            stack = open_notes.get(key) or []
            if not stack:
                raise ValueError(f"note-off without note-on at tick {event['tick']} pitch {event['pitch']}")
            start_event = stack.pop(0)
            duration = event["tick"] - start_event["tick"]
            if duration <= 0:
                raise ValueError("non-positive duration")
            paired.append({
                "channel": start_event["channel"],
                "pitch": start_event["pitch"],
                "start": start_event["tick"],
                "duration": duration,
                "velocity": start_event["velocity"],
                "offset": 0,
            })
    for key, stack in open_notes.items():
        if stack:
            raise ValueError(f"unclosed note channel {key[0]} pitch {key[1]}")
    return paired


def notes_to_events(notes: list[dict], channel: int | None = None) -> list[dict]:
    events = []
    for note in notes:
        ch = channel if channel is not None else note["channel"]
        start = note["performed_start"]
        end = start + note["duration"]
        events.append({
            "type": "note_on",
            "tick": start,
            "channel": ch,
            "pitch": note["pitch"],
            "velocity": note["velocity"],
        })
        events.append({
            "type": "note_off",
            "tick": end,
            "channel": ch,
            "pitch": note["pitch"],
        })
    return events


def preamble(name: str, tempo_us: int, container_ticks: int) -> list[dict]:
    return [
        {"type": "track_name", "tick": 0, "name": name},
        {"type": "tempo", "tick": 0, "us": tempo_us},
        {"type": "meter", "tick": 0, "numerator": 4, "denominator": 4},
    ]


def self_test() -> None:
    notes = [
        {"channel": 0, "pitch": 33, "performed_start": 240, "duration": 150, "velocity": 90},
        {"channel": 0, "pitch": 34, "performed_start": 480, "duration": 150, "velocity": 80},
    ]
    events = preamble("Bassline", bpm_to_us(140), 3840) + notes_to_events(notes)
    data = write_midi(Path("/tmp/midi-io-self-test.mid"), 0, [(events, 3840)])
    parsed = parse_midi(data)
    if parsed["format"] != 0 or parsed["ppq"] != 960:
        raise AssertionError("header mismatch")
    paired = pair_notes(parsed["tracks"][0])
    if len(paired) != 2 or paired[0]["pitch"] != 33 or paired[0]["start"] != 240:
        raise AssertionError(paired)
    if parsed["tracks"][0]["eot_tick"] != 3840:
        raise AssertionError("eot boundary")
    # Same-tick note-off must be ordered before the next note-on in the file bytes.
    back_to_back = [
        {"channel": 0, "pitch": 40, "performed_start": 0, "duration": 240, "velocity": 70},
        {"channel": 0, "pitch": 40, "performed_start": 240, "duration": 240, "velocity": 70},
    ]
    events = preamble("Bassline", bpm_to_us(140), 960) + notes_to_events(back_to_back)
    data = write_midi(Path("/tmp/midi-io-self-test.mid"), 0, [(events, 960)])
    parsed = parse_midi(data)
    kinds = [event["type"] for event in parsed["tracks"][0]["events"] if event["type"] in ("note_on", "note_off")]
    if kinds != ["note_on", "note_off", "note_on", "note_off"]:
        raise AssertionError(kinds)
