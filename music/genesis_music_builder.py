#!/usr/bin/env python3
"""Reproduce the accepted GENESIS Theatrical Pass 14R4 MIDI from the locked R2 master.

Usage:
    python GENESIS_Pass14R4_MIDI_Builder.py
    python GENESIS_Pass14R4_MIDI_Builder.py --source GENESIS_Theatrical_Pass_14R2.mid --output GENESIS_Theatrical_Pass_14R4.mid

The R4 revision is tempo-only. All non-tempo MIDI events and all verse-marker ticks
are preserved exactly. The script verifies the approved R2 source hash and refuses
to keep an output unless the resulting R4 file is byte-identical to the accepted
master hash.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path

from mido import MetaMessage, MidiFile, MidiTrack

EXPECTED_SOURCE_SHA256 = "1cc80b4f2c13491fbfc7bce3442d7032249cf1346cf4f2be3d310da43dcc5857"
EXPECTED_OUTPUT_SHA256 = "3cdc83a8aa9c24d8ed122c757953a207a17752515a532b399f08dea4d3f679ac"
EXPECTED_TRACKS = 29
EXPECTED_VERSE_MARKERS = 544
EXPECTED_NOTE_ONS = 7447
EXPECTED_NOTE_OFFS = 7447
EXPECTED_DURATION_SECONDS = 4074.7370496958333

# Exact accepted tempo replacements in the meta track: tick -> (R2 tempo, R4 tempo).
TEMPO_REPLACEMENTS = {
    30720: (833333, 1149921),
    34560: (909091, 1254460),
    42240: (967742, 1335393),
    49920: (1071429, 1478471),
    65280: (1034483, 1427489),
    76800: (1111111, 1533229),
    84480: (909091, 1195034),
    99840: (857143, 1126746),
    115200: (937500, 1232379),
    130560: (1000000, 1314537),
    145920: (909091, 1195034),
    161280: (952381, 1251940),
    168960: (1071429, 1349697),
    207360: (1000000, 1259717),
    287817: (1071429, 1349697),
    733669: (714286, 721108),
    789929: (681818, 688330),
    850021: (731707, 738696),
    890022: (1111111, 1121723),
    976464: (1000000, 1009551),
    1066507: (882353, 890781),
}

# Exact boundary tempos inserted before pre-existing marker events at these ticks.
INSERTED_TEMPOS = {
    168933: 1199730,  # Episode I begins
    373100: 1071429,  # restore accepted tempo at Stasimon I boundary
    733637: 1316806,  # Episode III expansion begins
    1222920: 882353,  # restore accepted tempo at Stasimon III boundary
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def absolute_events(track) -> list[tuple[int, int, object]]:
    tick = 0
    out: list[tuple[int, int, object]] = []
    for index, message in enumerate(track):
        tick += message.time
        out.append((tick, index, copy.copy(message)))
    return out


# noinspection unresolved-references
def rebuild_meta_track(source_track) -> MidiTrack:
    events = absolute_events(source_track)
    seen_replacements: set[int] = set()

    rebuilt: list[tuple[int, int, object]] = []
    for tick, order, message in events:
        if message.type == "set_tempo" and tick in TEMPO_REPLACEMENTS:
            expected_old, accepted_new = TEMPO_REPLACEMENTS[tick]
            if message.tempo != expected_old:
                raise RuntimeError(
                    f"Unexpected R2 tempo at tick {tick}: {message.tempo} != {expected_old}"
                )
            message.tempo = accepted_new
            seen_replacements.add(tick)
        rebuilt.append((tick, order, message))

    missing = set(TEMPO_REPLACEMENTS) - seen_replacements
    if missing:
        raise RuntimeError(f"Missing expected R2 tempo events at ticks: {sorted(missing)}")

    # order=-1 guarantees that a boundary tempo precedes any marker at the same tick,
    # matching the accepted R4 event ordering exactly.
    for tick, tempo in INSERTED_TEMPOS.items():
        rebuilt.append((tick, -1, MetaMessage("set_tempo", tempo=tempo, time=0)))

    rebuilt.sort(key=lambda item: (item[0], 0 if item[2].type == 'set_tempo' else 1, item[1]))

    track = MidiTrack()
    previous_tick = 0
    for tick, _, message in rebuilt:
        message = copy.copy(message)
        message.time = tick - previous_tick
        previous_tick = tick
        track.append(message)
    return track


def marker_ticks(midi: MidiFile) -> dict[int, int]:
    import re

    result: dict[int, int] = {}
    tick = 0
    for message in midi.tracks[0]:
        tick += message.time
        if message.type == "marker":
            match = re.fullmatch(r"v(\d{1,3})", str(getattr(message, "text", "")).strip())
            if match:
                result[int(match.group(1))] = tick
    return result


def validate_midi(path: Path) -> None:
    midi = MidiFile(path)
    if len(midi.tracks) != EXPECTED_TRACKS:
        raise RuntimeError(f"Track-count mismatch: {len(midi.tracks)} != {EXPECTED_TRACKS}")

    markers = marker_ticks(midi)
    if set(markers) != set(range(1, EXPECTED_VERSE_MARKERS + 1)):
        raise RuntimeError(f"Verse-marker coverage mismatch: {len(markers)} / {EXPECTED_VERSE_MARKERS}")

    note_ons = 0
    note_offs = 0
    for track_index, track in enumerate(midi.tracks):
        active: dict[tuple[int, int], int] = {}
        for message in track:
            if message.type == "note_on" and message.velocity > 0:
                note_ons += 1
                key = (message.channel, message.note)
                active[key] = active.get(key, 0) + 1
            elif message.type == "note_off" or (message.type == "note_on" and message.velocity == 0):
                note_offs += 1
                key = (message.channel, message.note)
                if active.get(key, 0) <= 0:
                    raise RuntimeError(
                        f"Orphan note-off in track {track_index}: channel={key[0]} note={key[1]}"
                    )
                active[key] -= 1
        leftovers = sum(active.values())
        if leftovers:
            raise RuntimeError(f"Unclosed notes in track {track_index}: {leftovers}")

    if note_ons != EXPECTED_NOTE_ONS:
        raise RuntimeError(f"Note-on mismatch: {note_ons} != {EXPECTED_NOTE_ONS}")
    if note_offs != EXPECTED_NOTE_OFFS:
        raise RuntimeError(f"Note-off mismatch: {note_offs} != {EXPECTED_NOTE_OFFS}")
    if abs(midi.length - EXPECTED_DURATION_SECONDS) > 1e-6:
        raise RuntimeError(
            f"Duration mismatch: {midi.length:.9f} != {EXPECTED_DURATION_SECONDS:.9f}"
        )


# noinspection string-format
def build(source: Path, output: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)

    source_hash = sha256(source)
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            "The input is not the locked GENESIS Theatrical Pass 14R2 master.\n"
            f"Expected SHA-256: {EXPECTED_SOURCE_SHA256}\n"
            f"Actual SHA-256:   {source_hash}"
        )

    midi = MidiFile(source)
    original_markers = marker_ticks(midi)
    midi.tracks[0] = rebuild_meta_track(midi.tracks[0])

    output.parent.mkdir(parents=True, exist_ok=True)
    midi.save(output)

    try:
        validate_midi(output)
        rebuilt = MidiFile(output)
        if marker_ticks(rebuilt) != original_markers:
            raise RuntimeError("Verse-marker ticks changed during the R4 build.")

        output_hash = sha256(output)
        if output_hash != EXPECTED_OUTPUT_SHA256:
            raise RuntimeError(
                "Output hash mismatch; refusing to keep a non-identical R4 artifact.\n"
                f"Expected SHA-256: {EXPECTED_OUTPUT_SHA256}\n"
                f"Actual SHA-256:   {output_hash}"
            )
    except Exception:
        output.unlink(missing_ok=True)
        raise

    print(f"PASS: {output}")
    print(f"SHA-256: {output_hash}")
    print(f"Duration: {rebuilt.length:.6f} s ({rebuilt.length / 60:.3f} min)")
    print(f"Tracks: {len(rebuilt.tracks)}")
    print(f"Verse markers: {EXPECTED_VERSE_MARKERS}")
    print(f"Note-on events: {EXPECTED_NOTE_ONS}")
    print("Revision rule: tempo-only; all non-tempo events and marker ticks preserved.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reproduce the accepted GENESIS Theatrical Pass 14R4 MIDI from the locked R2 master."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("GENESIS_Theatrical_Pass_14R2.mid"),
        help="Locked R2 MIDI source.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("GENESIS_Theatrical_Pass_14R4.mid"),
        help="R4 output path.",
    )
    args = parser.parse_args()
    build(args.source, args.output)


if __name__ == "__main__":
    main()
