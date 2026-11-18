#!/usr/bin/env python3
"""Install custom Doki menu theme and high-pitched kawaii Anime Dude voice into Postal 2 & Paradise Lost."""

from __future__ import annotations

import os
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ue2_io

import retarget

P2_ROOT = Path(retarget.P2_ROOT)
_LOCAL_THEME = Path(__file__).resolve().parent / "DokiMenu.ogg"
UPLOADED_THEME = (
    _LOCAL_THEME
    if _LOCAL_THEME.is_file()
    else Path(
        "/home/foidslayer/.gemini/antigravity/brain/60a250bd-79dc-411f-ade5-fffc381bc719/.user_uploaded/uploaded_media_1794615081046.m4a"
    )
)
RESTORE_SH = Path(__file__).resolve().parent / "restore_postal2_originals.sh"

# Rubber Band R3 settings auditioned and verified clean for kawaii high-pitched anime Dude voice
PITCH_SEMITONES = "12.5"
TEMPO_FACTOR = "0.88"

SKIN_MANAGED_REL_FILES = [
    "Animations/Characters.ukx",
    "Animations/heads.ukx",
    "Animations/MoreHeads.ukx",
    "Paradise Lost/System/Default.ini",
    "Paradise Lost/System/PLGame.u",
    "Paradise Lost/System/PLInventory.u",
    "Paradise Lost/System/PLPawns.u",
    "ShareThePain/Animations/Characters.ukx",
    "ShareThePain/Animations/heads.ukx",
    "ShareThePain/System/BasePeople.u",
    "ShareThePain/System/Default.ini",
    "ShareThePain/System/Inventory.u",
    "ShareThePain/System/MultiStuff.u",
    "ShareThePain/System/People.u",
    "ShareThePain/System/Postal2MP.ini",
    "System/AWPStuff.u",
    "System/BasePeople.u",
    "System/Default.ini",
    "System/GameTypes.u",
    "System/Inventory.u",
    "System/People.u",
]

AUDIO_MANAGED_REL_FILES = [
    "Paradise Lost/Music/HeadAboveTheWater.ogg",
    "Paradise Lost/Music/PL-MenuMusic.ogg",
    "Paradise Lost/Music/menu2mk2.ogg",
    "Maps/Startup.fuk",
    "Maps/Startup-Halloween.fuk",
    "Maps/AWstartup.fuk",
    "Paradise Lost/Maps/Startup.fuk",
    "Paradise Lost/Maps/Startup-Apocalypse.fuk",
    "Sounds/DudeDialog.uax",
    "Sounds/AWDialog.uax",
    "Paradise Lost/Sounds/PL-Dialog.uax",
    "Paradise Lost/Sounds/PL-Dialog2.uax",
    "Paradise Lost/Sounds/PL-Dialog3.uax",
]

ADDED_REL_FILES = [
    "Textures/DokiSkins.utx",
    "Music/DokiMenu.ogg",
    "Paradise Lost/Music/DokiMenu.ogg",
]


def ensure_backup(rel_path: str) -> Path:
    """Create a one-time .bak_orig snapshot of a Postal 2 file and return the snapshot path."""
    target = P2_ROOT / rel_path
    bak = Path(f"{target}.bak_orig")
    if not bak.exists():
        if not target.exists():
            raise FileNotFoundError(f"Missing Postal 2 file: {target}")
        shutil.copy2(target, bak)
    return bak


def build_prop_str(pkg: ue2_io.UE2Package, name: str, text: str) -> bytes:
    """Serialize a UE2 StrProperty (type=13)."""
    ni = pkg.ensure_name(name)
    val = ue2_io.write_fstring(text)
    if len(val) < 256:
        info = 13 | (5 << 4)
        sz_hdr = bytes([len(val)])
    else:
        info = 13 | (6 << 4)
        sz_hdr = struct.pack("<H", len(val))
    return ue2_io.write_ci(ni) + bytes([info]) + sz_hdr + val


def build_prop_float(pkg: ue2_io.UE2Package, name: str, val_f: float) -> bytes:
    """Serialize a UE2 FloatProperty (type=4, 4 bytes)."""
    ni = pkg.ensure_name(name)
    info = 4 | (2 << 4)
    return ue2_io.write_ci(ni) + bytes([info]) + struct.pack("<f", val_f)


def build_prop_bool(pkg: ue2_io.UE2Package, name: str, value: bool) -> bytes:
    """Serialize a UE2 BoolProperty (type=3, bit 7 holds boolean state)."""
    ni = pkg.ensure_name(name)
    info = 3 | ((1 if value else 0) << 7)
    return ue2_io.write_ci(ni) + bytes([info])


def build_prop_obj(pkg: ue2_io.UE2Package, name: str, obj_idx: int) -> bytes:
    """Serialize a UE2 ObjectProperty (type=5)."""
    ni = pkg.ensure_name(name)
    ci = ue2_io.write_ci(obj_idx)
    size_code = {1: 0, 2: 1, 4: 2}.get(len(ci))
    if size_code is not None:
        info = 5 | (size_code << 4)
        sz_hdr = b""
    else:
        info = 5 | (5 << 4)
        sz_hdr = bytes([len(ci)])
    return ue2_io.write_ci(ni) + bytes([info]) + sz_hdr + ci


def build_prop_name(pkg: ue2_io.UE2Package, name: str, target_name: str) -> bytes:
    """Serialize a UE2 NameProperty (type=6)."""
    ni = pkg.ensure_name(name)
    ci = ue2_io.write_ci(pkg.ensure_name(target_name))
    size_code = {1: 0, 2: 1, 4: 2}.get(len(ci))
    if size_code is not None:
        info = 6 | (size_code << 4)
        sz_hdr = b""
    else:
        info = 6 | (5 << 4)
        sz_hdr = bytes([len(ci)])
    return ue2_io.write_ci(ni) + bytes([info]) + sz_hdr + ci


def build_songthing_payload(
    pkg: ue2_io.UE2Package,
    header15: bytes,
    song_filename: str,
    tag_name: str,
    level_info_idx: int,
) -> bytes:
    """Build a non-attenuated auto-starting SongThing Actor payload."""
    props = bytearray()
    props.extend(header15)
    props.extend(build_prop_bool(pkg, "bInitiallyTurnedOn", True))
    props.extend(build_prop_str(pkg, "SongName", song_filename))
    props.extend(build_prop_float(pkg, "FadeInTime", 1.0))
    props.extend(build_prop_float(pkg, "VolumeOverride", 0.95))
    props.extend(build_prop_bool(pkg, "bAttenuate", False))
    props.extend(build_prop_name(pkg, "Tag", tag_name))
    props.extend(build_prop_obj(pkg, "Level", level_info_idx))
    props.extend(ue2_io.write_ci(pkg.ensure_name("None")))
    return bytes(props)


def install_menu_music(theme_src: Path) -> None:
    """Transcode user menu audio to Ogg Vorbis and install across Postal 2 & Paradise Lost."""
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tf:
        tmp_ogg = Path(tf.name)
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(theme_src),
            "-vn",
            "-c:a",
            "libvorbis",
            "-q:a",
            "6",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(tmp_ogg),
        ]
        subprocess.run(cmd, check=True)

        # Direct menu tracks
        for rel in [
            "Music/DokiMenu.ogg",
            "Paradise Lost/Music/DokiMenu.ogg",
        ]:
            dst = P2_ROOT / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tmp_ogg, dst)

        for rel in [
            "Paradise Lost/Music/HeadAboveTheWater.ogg",
            "Paradise Lost/Music/PL-MenuMusic.ogg",
            "Paradise Lost/Music/menu2mk2.ogg",
        ]:
            ensure_backup(rel)
            shutil.copy2(tmp_ogg, P2_ROOT / rel)
    finally:
        tmp_ogg.unlink(missing_ok=True)


def patch_startup_maps() -> None:
    """Update existing SongThing actors or add one in Startup maps so DokiMenu.ogg plays in menus."""
    for rel in [
        "Maps/AWstartup.fuk",
        "Paradise Lost/Maps/Startup.fuk",
        "Paradise Lost/Maps/Startup-Apocalypse.fuk",
        "Maps/Startup.fuk",
        "Maps/Startup-Halloween.fuk",
    ]:
        src_bak = ensure_backup(rel)
        pkg = ue2_io.UE2Package.load(str(src_bak))
        level_info_idx = pkg.find_export("LevelInfo0")
        mylevel_idx = pkg.find_export("MyLevel")
        if level_info_idx is None or mylevel_idx is None:
            raise RuntimeError(f"Missing LevelInfo0 or MyLevel in {rel}")

        existing = [
            (i + 1, e)
            for i, e in enumerate(pkg.exports)
            if pkg.obj_name(e.class_idx) == "SongThing"
        ]
        if existing:
            for exp_idx, exp in existing:
                old_raw = pkg.raw[exp.serial_offset : exp.serial_offset + exp.serial_size]
                tag = "StartAfterFirstTime" if "Apocalypse" in rel else "SongThing"
                payload = build_songthing_payload(
                    pkg, old_raw[:15], "DokiMenu.ogg", tag, level_info_idx
                )
                pkg.replace_export_payload(exp_idx, payload)
            print(f"[menu] Patched {len(existing)} SongThing(s) in {rel}")
        else:
            fps_pkg = pkg.ensure_import("Core", "Package", 0, "FPSGame")
            song_cls = pkg.ensure_import("Core", "Class", fps_pkg, "SongThing")
            hdr = (
                ue2_io.write_ci(song_cls)
                + ue2_io.write_ci(song_cls)
                + (b"\xff" * 8)
                + b"\x00\x00\x00\x00"
                + ue2_io.write_ci(-1)
            )
            payload = build_songthing_payload(
                pkg, hdr, "DokiMenu.ogg", "SongThing", level_info_idx
            )
            new_exp_idx = pkg.add_export_builder(
                class_idx=song_cls,
                super_idx=0,
                outer_idx=0,
                name="SongThing_Doki",
                flags=0x02070001,
                build_fn=lambda _off: payload,
            )

            # Append new actor reference into MyLevel ULevel::Actors TTransArray
            ml_exp = pkg.exports[mylevel_idx - 1]
            ml_raw = pkg.raw[ml_exp.serial_offset : ml_exp.serial_offset + ml_exp.serial_size]
            db_num, db_max = struct.unpack_from("<ii", ml_raw, 1)
            pos = 9
            refs_bytes = bytearray()
            for _ in range(db_num):
                r, next_pos = ue2_io.read_ci(ml_raw, pos)
                refs_bytes.extend(ue2_io.write_ci(r))
                pos = next_pos
            refs_bytes.extend(ue2_io.write_ci(new_exp_idx))
            new_ml = (
                ml_raw[:1]
                + struct.pack("<ii", db_num + 1, max(db_max + 1, db_num + 1))
                + bytes(refs_bytes)
                + ml_raw[pos:]
            )
            pkg.replace_export_payload(mylevel_idx, new_ml)
            print(f"[menu] Added SongThing_Doki (exp {new_exp_idx}) to {rel}")

        pkg.save(str(P2_ROOT / rel))


def parse_sound_export(pkg: ue2_io.UE2Package, exp: ue2_io.UE2Export) -> Tuple[bytes, bytes, bytes]:
    """Return (prefix_props_plus_filetype, wav_bytes) up to EndOffset uint32 field."""
    raw = pkg.raw[exp.serial_offset : exp.serial_offset + exp.serial_size]
    pos = 0
    while pos < len(raw):
        ni, pos = ue2_io.read_ci(raw, pos)
        if pkg.names[ni][0] == "None":
            break
        info = raw[pos]
        pos += 1
        ptype = info & 0x0F
        sc = (info >> 4) & 0x07
        af = (info >> 7) & 1
        if ptype == 10:
            _, pos = ue2_io.read_ci(raw, pos)
        sz = {0: 1, 1: 2, 2: 4, 3: 12, 4: 16}.get(sc)
        if sz is None:
            if sc == 5:
                sz = raw[pos]
                pos += 1
            elif sc == 6:
                (sz,) = struct.unpack_from("<H", raw, pos)
                pos += 2
            elif sc == 7:
                (sz,) = struct.unpack_from("<I", raw, pos)
                pos += 4
        if af and ptype != 3:
            _, pos = ue2_io.read_ci(raw, pos)
        pos += sz

    _, pos = ue2_io.read_ci(raw, pos)  # FileType ('WAV')
    prefix = raw[:pos]
    pos += 4  # EndOffset uint32 LE
    wlen, pos2 = ue2_io.read_ci(raw, pos)
    wav_bytes = raw[pos2 : pos2 + wlen]
    return prefix, wav_bytes, raw[pos2 + wlen :]


def pitch_shift_wav(task: Tuple[int, str, bytes, bytes]) -> Tuple[int, str, bytes, bytes]:
    """Convert one WAV byte buffer using rubberband R3 kawaii high-pitch settings."""
    exp_idx, name, prefix, wav_bytes = task
    with tempfile.TemporaryDirectory() as td:
        in_p = Path(td) / "in.wav"
        norm_p = Path(td) / "norm.wav"
        out_p = Path(td) / "out.wav"
        in_p.write_bytes(wav_bytes)
        res = subprocess.run(
            [
                "rubberband",
                "-3",
                "-q",
                "-p",
                PITCH_SEMITONES,
                "-t",
                TEMPO_FACTOR,
                str(in_p),
                str(out_p),
            ],
            capture_output=True,
        )
        if res.returncode != 0 or not out_p.exists():
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", str(in_p), "-acodec", "pcm_s16le", str(norm_p)],
                check=True,
            )
            subprocess.run(
                [
                    "rubberband",
                    "-3",
                    "-q",
                    "-p",
                    PITCH_SEMITONES,
                    "-t",
                    TEMPO_FACTOR,
                    str(norm_p),
                    str(out_p),
                ],
                check=True,
            )
        shifted = out_p.read_bytes()
        if not shifted.startswith(b"RIFF"):
            raise RuntimeError(f"Invalid WAV output for {name}")
        return exp_idx, name, prefix, shifted


def install_kawaii_dude_voices() -> None:
    """Pitch-shift all Postal Dude voice lines across base, AW, and Paradise Lost UAX packages."""
    specs: List[Tuple[str, Callable[[str, str], bool]]] = [
        ("Sounds/DudeDialog.uax", lambda _n, _g: True),
        ("Sounds/AWDialog.uax", lambda n, g: "dude" in g.lower() or n.lower().startswith("dude")),
        ("Paradise Lost/Sounds/PL-Dialog.uax", lambda n, _g: "dude" in n.lower()),
        ("Paradise Lost/Sounds/PL-Dialog2.uax", lambda n, g: "dude" in g.lower() or n.lower().startswith("dude")),
        ("Paradise Lost/Sounds/PL-Dialog3.uax", lambda _n, g: "dude" in g.lower()),
    ]

    total = 0
    for rel, pred in specs:
        src_bak = ensure_backup(rel)
        pkg = ue2_io.UE2Package.load(str(src_bak))
        tasks: List[Tuple[int, str, bytes, bytes]] = []
        for i, e in enumerate(pkg.exports):
            if pkg.obj_name(e.class_idx) != "Sound":
                continue
            name = pkg.names[e.object_name][0]
            group = pkg.obj_name(e.outer_idx)
            if pred(name, group):
                prefix, wav_bytes, tail = parse_sound_export(pkg, e)
                if tail:
                    raise RuntimeError(f"Unexpected tail bytes in {rel}:{name}")
                tasks.append((i + 1, name, prefix, wav_bytes))

        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as ex:
            results = list(ex.map(pitch_shift_wav, tasks))

        for exp_idx, _name, prefix, shifted_wav in results:
            wav_ci = ue2_io.write_ci(len(shifted_wav))
            payload_size = len(prefix) + 4 + len(wav_ci) + len(shifted_wav)
            end_offset = pkg.append_space_offset() + payload_size
            payload = prefix + struct.pack("<I", end_offset) + wav_ci + shifted_wav
            pkg.replace_export_payload(exp_idx, payload)

        out_path = P2_ROOT / rel
        pkg.save(str(out_path))
        total += len(results)
        print(f"[voice] Converted {len(results)} Dude lines in {rel}")

    print(f"[voice] Total Dude voice clips converted: {total}")


def write_restore_script() -> None:
    """Regenerate restore_postal2_originals.sh to cleanly restore both skins and audio/menu files."""
    all_managed = list(dict.fromkeys(SKIN_MANAGED_REL_FILES + AUDIO_MANAGED_REL_FILES))
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f'P2="{P2_ROOT}"',
        "MANAGED=(",
    ]
    for rel in all_managed:
        lines.append(f'  "{rel}"')
    lines.extend([")", "ADDED=("])
    for rel in ADDED_REL_FILES:
        lines.append(f'  "{rel}"')
    lines.extend(
        [
            ")",
            'for rel in "${MANAGED[@]}"; do',
            '  if [[ -f "$P2/$rel.bak_orig" ]]; then',
            '    mv -f "$P2/$rel.bak_orig" "$P2/$rel"',
            '    echo "Restored $rel"',
            "  fi",
            "done",
            'for rel in "${ADDED[@]}"; do',
            '  if [[ -f "$P2/$rel" ]]; then',
            '    rm -f "$P2/$rel"',
            '    echo "Removed $rel"',
            "  fi",
            "done",
            'echo "Original Postal 2 files restored."',
        ]
    )
    RESTORE_SH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(RESTORE_SH, os.stat(RESTORE_SH).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> int:
    if not UPLOADED_THEME.exists():
        raise FileNotFoundError(f"Uploaded menu theme missing: {UPLOADED_THEME}")
    print("[audio] Installing uploaded menu theme across Postal 2 & Paradise Lost...")
    install_menu_music(UPLOADED_THEME)
    patch_startup_maps()
    print("[voice] Pitch-shifting Postal Dude voices to kawaii anime tone...")
    install_kawaii_dude_voices()
    write_restore_script()
    print("[done] Menu music + kawaii Dude voice installed cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

