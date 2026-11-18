"""Back up Postal 2 original packages, build Doki skins/meshes, and patch player classes."""
from __future__ import annotations

import os
import shlex
import shutil
import stat
import struct
from typing import Dict, List

import retarget
import ue2_io

P2_ROOT = retarget.P2_ROOT
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESTORE_SH = os.path.join(_SCRIPT_DIR, "restore_postal2_originals.sh")

MANAGED_REL_FILES = [
    "Animations/Characters.ukx",
    "Animations/MoreHeads.ukx",
    "Animations/heads.ukx",
    "System/AWPStuff.u",
    "System/BasePeople.u",
    "System/People.u",
    "System/GameTypes.u",
    "System/Inventory.u",
    "Paradise Lost/System/PLGame.u",
    "Paradise Lost/System/PLInventory.u",
    "Paradise Lost/System/PLPawns.u",
    "ShareThePain/Animations/Characters.ukx",
    "ShareThePain/Animations/heads.ukx",
    "ShareThePain/System/BasePeople.u",
    "ShareThePain/System/People.u",
    "ShareThePain/System/Inventory.u",
    "ShareThePain/System/MultiStuff.u",
]

ADDED_REL_FILES = [
    "Textures/DokiSkins.utx",
]


def create_backups_and_restore_script() -> None:
    """Create non-overwriting .bak_orig backups of all target files and write restore script."""
    restore_lines: List[str] = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f"P2_ROOT={shlex.quote(P2_ROOT)}",
        "",
    ]

    for rel in MANAGED_REL_FILES:
        src = os.path.join(P2_ROOT, rel)
        bak = src + ".bak_orig"
        assert os.path.exists(src), f"Missing target file: {src}"
        if not os.path.exists(bak):
            shutil.copy2(src, bak)
            print(f"BACKUP CREATED: {bak}")
        else:
            print(f"BACKUP EXISTS : {bak}")
        q_rel = shlex.quote(rel)
        restore_lines.append(
            f'cp -a "$P2_ROOT/"{q_rel}.bak_orig "$P2_ROOT/"{q_rel}'
        )

    for rel in ADDED_REL_FILES:
        q_rel = shlex.quote(rel)
        restore_lines.append(f'rm -f "$P2_ROOT/"{q_rel}')

    restore_lines.append('echo "Restored all original Postal 2 files from .bak_orig backups."')
    with open(RESTORE_SH, "w", encoding="utf-8") as f:
        f.write("\n".join(restore_lines) + "\n")
    st = os.stat(RESTORE_SH)
    os.chmod(RESTORE_SH, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"WROTE RESTORE SCRIPT: {RESTORE_SH}")


def _imp_skel(pkg: ue2_io.UE2Package, ukx_pkg_name: str, mesh_name: str) -> int:
    ukx_pkg = pkg.ensure_import("Core", "Package", 0, ukx_pkg_name)
    return pkg.ensure_import("Engine", "SkeletalMesh", ukx_pkg, mesh_name)


def _imp_tex(pkg: ue2_io.UE2Package, utx_pkg_name: str, tex_name: str) -> int:
    utx_pkg = pkg.ensure_import("Core", "Package", 0, utx_pkg_name)
    return pkg.ensure_import("Engine", "Texture", utx_pkg, tex_name)


def _patch_dog_helper_class(
    pkg: ue2_io.UE2Package,
    cls_name: str,
    anchor_prop: str,
    mesh_ref: int,
    null_tex_ref: int,
) -> None:
    """Apply Characters.Doki_Yuri mesh/scale/height/null-slot0 to a cheat-summoned helper pawn class."""
    props = [
        ("Mesh", ue2_io.encode_prop_obj(pkg.ensure_name("Mesh"), mesh_ref)),
        ("DrawScale", ue2_io.encode_prop_float(pkg.ensure_name("DrawScale"), 1.0)),
        ("CollisionHeight", ue2_io.encode_prop_float(pkg.ensure_name("CollisionHeight"), 75.0)),
        ("Skins", ue2_io.encode_prop_obj_array(pkg.ensure_name("Skins"), [null_tex_ref])),
    ]
    ue2_io.upsert_class_defprops(pkg, cls_name, anchor_prop, props)


def patch_u_file(rel_path: str, ops) -> None:
    dst = os.path.join(P2_ROOT, rel_path)
    bak = dst + ".bak_orig"
    assert os.path.exists(bak), f"Backup missing before write: {bak}"
    pkg = ue2_io.UE2Package.load(bak)
    ops(pkg)
    pkg.save(dst)
    print(f"PATCHED {rel_path}")


def verify_u_obj(rel_path: str, cls_name: str, anchor: str, prop: str, expected_name: str) -> None:
    pkg = ue2_io.UE2Package.load(os.path.join(P2_ROOT, rel_path))
    ei = pkg.find_export_ci(cls_name)
    assert ei is not None
    st, en, info, _sn, _ai = ue2_io.find_defprop_span(pkg, ei, anchor, prop)
    assert (info & 0x0F) == 5
    ex = pkg.exports[ei - 1]
    buf = pkg.raw[ex.serial_offset : ex.serial_offset + ex.serial_size]
    # Header tag end starts value
    pos = st
    _, pos = ue2_io.read_ci(buf, pos)
    pinfo = buf[pos]
    pos += 1
    stype = (pinfo >> 4) & 0x07
    if stype == 5:
        pos += 1
    if (pinfo & 0x80) != 0:
        _, pos = ue2_io.read_ci(buf, pos)
    ref, _ = ue2_io.read_ci(buf, pos)
    got = pkg.obj_name(ref)
    assert got == expected_name, f"{rel_path}::{cls_name}.{prop}: expected {expected_name}, got {got}"
    print(f"  VERIFIED {rel_path} :: {cls_name}.{prop} == {got}")


def _install_doki_ini_bindings(p2_root: str) -> None:
    """Install 4-Doki Selector (Natsuki/Sayori/Monika/Yuri, Doki1..Doki4) aliases and keybinds."""
    import re
    ini_paths = [
        os.path.join(p2_root, "System/Default.ini"),
        os.path.join(p2_root, "Paradise Lost/System/Default.ini"),
        os.path.join(p2_root, "ShareThePain/System/Default.ini"),
        os.path.expanduser("~/.lgp/postal2/System/User.ini"),
        os.path.expanduser("~/.lgp/postal2/System/PLUser.ini"),
    ]
    doki_aliases = [
        ('Natsuki', 'Aliases[29]=(Command="Sissy | Sissy | ForceSissy | SetClothes Inventory.DudeClothesInv | BehindView 1",Alias="Natsuki")'),
        ('Sayori', 'Aliases[30]=(Command="Sissy | Sissy | ForceSissy | SetClothes Inventory.GimpClothesInv | BehindView 1",Alias="Sayori")'),
        ('Monika', 'Aliases[31]=(Command="Sissy | Sissy | ForceSissy | SetClothes Inventory.CopClothesInv | BehindView 1",Alias="Monika")'),
        ('Yuri', 'Aliases[32]=(Command="Sissy | Sissy | ForceSissy | SetClothes Inventory.ClothesInv | BehindView 1",Alias="Yuri")'),
        ('Doki1', 'Aliases[33]=(Command="Sissy | Sissy | ForceSissy | SetClothes Inventory.DudeClothesInv | BehindView 1",Alias="Doki1")'),
        ('Doki2', 'Aliases[34]=(Command="Sissy | Sissy | ForceSissy | SetClothes Inventory.GimpClothesInv | BehindView 1",Alias="Doki2")'),
        ('Doki3', 'Aliases[35]=(Command="Sissy | Sissy | ForceSissy | SetClothes Inventory.CopClothesInv | BehindView 1",Alias="Doki3")'),
        ('Doki4', 'Aliases[36]=(Command="Sissy | Sissy | ForceSissy | SetClothes Inventory.ClothesInv | BehindView 1",Alias="Doki4")'),
    ]
    for path in ini_paths:
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="latin1") as f:
            txt = f.read()
        for idx_num in range(29, 37):
            pat = re.compile(rf'^Aliases\[{idx_num}\]=\(.*$', re.MULTILINE)
            alias_line = doki_aliases[idx_num - 29][1]
            if pat.search(txt):
                txt = pat.sub(alias_line, txt, count=1)
            else:
                txt = txt.replace("[Engine.Input]\n", "[Engine.Input]\n" + alias_line + "\n", 1)
        # Clear any leftover split-screen aliases/keybinds
        for idx_num in (37, 38, 39):
            txt = re.sub(rf'^Aliases\[{idx_num}\]=\(Command="[^"]*",Alias="(?:SplitScreen|CoopDoki|SplitScreenOff)"\)\r?\n?', "", txt, flags=re.MULTILINE)
        txt = re.sub(r'^F9=SplitScreen\r?$', "F9=Shot", txt, flags=re.MULTILINE)
        txt = re.sub(r'^F10=SplitScreenOff\r?$', "F10=Cancel", txt, flags=re.MULTILINE)
        # Bind F2/F3/F4/F7 and NumPad1..4 to the 4 Dokis, F12 to ConsoleToggle
        for key_name, cmd_val in [
            ("F2", "Natsuki"),
            ("F3", "Sayori"),
            ("F4", "Monika"),
            ("F7", "Yuri"),
            ("F12", "ConsoleToggle"),
            ("NumPad1", "Natsuki"),
            ("NumPad2", "Sayori"),
            ("NumPad3", "Monika"),
            ("NumPad4", "Yuri"),
        ]:
            kpat = re.compile(rf'^{key_name}=.*$', re.MULTILINE)
            if kpat.search(txt):
                txt = kpat.sub(f"{key_name}={cmd_val}", txt, count=1)
        with open(path, "w", encoding="latin1") as f:
            f.write(txt)
    print("  INSTALLED 4-Doki Selector aliases in .ini files")


def main() -> None:
    # 1. Always create .bak_orig backups and executable restore script BEFORE touching game files
    create_backups_and_restore_script()

    out_dir = os.path.join(_SCRIPT_DIR, "out")
    os.makedirs(out_dir, exist_ok=True)

    # 2. Build & deploy DokiSkins.utx
    utx_out = os.path.join(out_dir, "DokiSkins.utx")
    mat_map: Dict[str, Dict[str, str]] = retarget.build_doki_textures(utx_out)
    shutil.copy2(utx_out, os.path.join(P2_ROOT, "Textures/DokiSkins.utx"))
    print("INSTALLED Textures/DokiSkins.utx")

    # 3. Build & deploy .ukx meshes cleanly from .bak_orig sources
    for ukx_rel in ("Animations/Characters.ukx", "ShareThePain/Animations/Characters.ukx"):
        src_bak = os.path.join(P2_ROOT, ukx_rel + ".bak_orig")
        dst = os.path.join(P2_ROOT, ukx_rel)
        retarget.inject_dokis_into_characters(src_bak, dst, mat_map)
        for mname, *_ in retarget.DOKI_SPECS:
            retarget.verify_skeletal_mesh_export(dst, mname)
        retarget.verify_skeletal_mesh_export(dst, "Doki_YuriDog")

    for ukx_rel, tmpl_head in (
        ("Animations/MoreHeads.ukx", "AW_Dude"),
        ("Animations/heads.ukx", "AvgDude"),
        ("ShareThePain/Animations/heads.ukx", "AvgDude"),
    ):
        src_bak = os.path.join(P2_ROOT, ukx_rel + ".bak_orig")
        dst = os.path.join(P2_ROOT, ukx_rel)
        retarget.inject_null_head(src_bak, dst, tmpl_head)
        retarget.verify_skeletal_mesh_export(dst, "Doki_NullHead")

    # 4. Patch all player & clothes .u classes cleanly from .bak_orig
    def ops_base_people(pkg: ue2_io.UE2Package) -> None:
        nat = _imp_skel(pkg, "Characters", "Doki_Natsuki")
        nh = _imp_skel(pkg, "MoreHeads", "Doki_NullHead")
        ue2_io.patch_class_defprop_obj(pkg, "AWDude", "LeprechaunDrawScale", "Mesh", nat)
        ue2_io.patch_class_defprop_obj(pkg, "AWDude", "LeprechaunDrawScale", "HeadMesh", nh)
        ue2_io.patch_class_defprop_obj(pkg, "Dude", "FootstepSounds", "CoreSPMesh", nat)

        # Patch PersonPawn.Tick(float DeltaTime):
        # 1) When !bHasHead && myHead != None, immediately call DestroyHeadBoltons(); DestroyBoltons();
        #    myHead.Destroy(); myHead = None; so Yuri/PartnerPawns NEVER show a random NPC head
        #    (even if loaded from an older .usa save file!).
        # 2) Secondary inertia spring-damper physics on jiggle_L and jiggle_R via SetBoneRotation.
        eng_pkg = pkg.ensure_import("Core", "Package", 0, "Engine")
        cls_actor = pkg.ensure_import("Core", "Class", eng_pkg, "Actor")
        fn_sbr = pkg.ensure_import("Core", "Function", cls_actor, "SetBoneRotation")
        nm_jiggle_l = pkg.ensure_name("jiggle_L")
        nm_jiggle_r = pkg.ensure_name("jiggle_R")
        nm_destroy = pkg.ensure_name("Destroy")
        nm_dhb = pkg.ensure_name("DestroyHeadBoltons")
        nm_db = pkg.ensure_name("DestroyBoltons")

        for i, exp in enumerate(pkg.exports):
            if pkg.obj_name(exp.outer_idx) == "PersonPawn" and pkg.names[exp.object_name][0] == "Tick":
                raw = pkg.raw[exp.serial_offset:exp.serial_offset + exp.serial_size]
                hdr = raw[:22]
                tail = raw[-7:]
                orig_prefix = bytes.fromhex("1cdf0800691316071c007701062a161b7c0116")
                if raw[22:22 + len(orig_prefix)] == orig_prefix:
                    cond_head = (
                        b"\x82\x81\x2d\x01\xc3\x06\x16"
                        b"\x18\x09\x00\x77\x01\xac\x2a\x16\x16"
                    )
                    body_head = (
                        b"\x1b" + ue2_io.write_ci(nm_dhb) + b"\x16"
                        + b"\x1b" + ue2_io.write_ci(nm_db) + b"\x16"
                        + b"\x19\x01\xac\x06\x00\x00\x1b" + ue2_io.write_ci(nm_destroy) + b"\x16"
                        + b"\x0f\x01\xac\x2a"
                    )
                    stmt_head = b"\x07" + struct.pack("<H", 28 + 3 + 21 + 34) + cond_head + body_head

                    f_1_4 = struct.pack("<f", 1.4)
                    f_520 = struct.pack("<f", 520.0)
                    f_14 = struct.pack("<f", 14.0)
                    f_0_75 = struct.pack("<f", 0.75)
                    f_280 = struct.pack("<f", 280.0)
                    f_7 = struct.pack("<f", 7.0)
                    f_1 = struct.pack("<f", 1.0)

                    pitch_expr = (
                        b"\x0f\x36\xca\x06\x01\xe8\x06"
                        b"\x39\x44\xab"
                        b"\xf4\xab\xe1\x01\xf6\x01\x16\x1e" + f_1_4 + b"\x16\x1e" + f_520 + b"\x16"
                        b"\xbb\xab\x19\x01\x98\x05\x00\x04\x01\xc1\x04\x1e" + f_14 + b"\x16\x16\x16"
                    )
                    roll_expr = (
                        b"\x0f\x36\xcb\x06\x01\xe8\x06"
                        b"\x39\x44\xab"
                        b"\xf4\xab\xe1\x01\xf6\x01\x16\x1e" + f_0_75 + b"\x16\x1e" + f_280 + b"\x16"
                        b"\xbc\xab\x19\x01\x98\x05\x00\x04\x01\xc1\x04\x1e" + f_7 + b"\x16\x16\x16"
                    )
                    yaw_expr = b"\x0f\x36\xe7\x04\x01\xe8\x06\x25"
                    call_l = (
                        b"\x1c" + ue2_io.write_ci(fn_sbr)
                        + b"\x21" + ue2_io.write_ci(nm_jiggle_l)
                        + b"\x01\xe8\x06\x25\x1e" + f_1 + b"\x16"
                    )
                    call_r = (
                        b"\x1c" + ue2_io.write_ci(fn_sbr)
                        + b"\x21" + ue2_io.write_ci(nm_jiggle_r)
                        + b"\x01\xe8\x06\x25\x1e" + f_1 + b"\x16"
                    )
                    stmt_jiggle = pitch_expr + roll_expr + yaw_expr + call_l + call_r
                    new_script_size = 28 + 3 + 21 + 34 + 59 + 59 + 12 + 22 + 22 + 2
                    new_body = orig_prefix + stmt_head + stmt_jiggle + b"\x04\x0b"
                    new_raw = hdr[:18] + struct.pack("<I", new_script_size) + new_body + tail
                    pkg.replace_export_payload(i + 1, new_raw)
                break

    def ops_people(pkg: ue2_io.UE2Package) -> None:
        nat = _imp_skel(pkg, "Characters", "Doki_Natsuki")
        nh_hd = _imp_skel(pkg, "heads", "Doki_NullHead")
        ue2_io.patch_class_defprop_obj(pkg, "PostalDude", "Mesh", "Mesh", nat)
        ue2_io.patch_class_defprop_obj(pkg, "PostalDude", "HeadSkin", "HeadMesh", nh_hd)

    def ops_gametypes(pkg: ue2_io.UE2Package) -> None:
        nh_mh = _imp_skel(pkg, "MoreHeads", "Doki_NullHead")
        nh_hd = _imp_skel(pkg, "heads", "Doki_NullHead")
        null_tex = _imp_tex(pkg, "DokiSkins", "Doki_NullTex")
        ue2_io.patch_class_defprop_obj(pkg, "AWPostalDude", "ExpectedHeadMesh", "ExpectedHeadMesh", nh_mh)
        ue2_io.patch_class_defprop_obj(pkg, "AWPostalDude", "ExpectedHeadMesh", "OldHeadMesh", nh_hd)
        ue2_io.upsert_class_defprops(
            pkg,
            "P2CheatManager",
            "DogSkins",
            [("DogSkins", ue2_io.encode_prop_obj_array(pkg.ensure_name("DogSkins"), [null_tex]))],
        )

        # 1) Patch DudePlayer.SetClothes (exp+1849) so it is an exec function (FUNC_Exec = 0x00000200),
        #    preloads Inventory.CopClothesInv (Monika) via EX_ObjectConst, and accepts all 4 Dokis!
        inv_pkg = pkg.ensure_import("Core", "Package", 0, "Inventory")
        cls_cop_clothes = pkg.ensure_import("Core", "Class", inv_pkg, "CopClothesInv")
        for i, exp in enumerate(pkg.exports):
            if pkg.obj_name(exp.outer_idx) == "DudePlayer" and pkg.names[exp.object_name][0] == "SetClothes":
                raw = pkg.raw[exp.serial_offset:exp.serial_offset + exp.serial_size]
                if len(raw) == 53:
                    new_body = (
                        b"\x07\x16\x00\x72\x00\x68\x09\x2a\x16"
                        b"\x0f\x00\x68\x09\x20" + ue2_io.write_ci(cls_cop_clothes)
                        + b"\x0f\x01\xc4\x04\x00\x68\x09"
                        b"\x1b\x59\x06\x16\x04\x0b"
                    )
                    new_raw = (
                        raw[:18]
                        + struct.pack("<I", 41)
                        + new_body
                        + bytes.fromhex("00000202020000")
                    )
                    pkg.replace_export_payload(i + 1, new_raw)
                break

    def ops_awp_stuff(pkg: ue2_io.UE2Package) -> None:
        yuri_dog = _imp_skel(pkg, "Characters", "Doki_YuriDog")
        null_tex = _imp_tex(pkg, "DokiSkins", "Doki_NullTex")
        _patch_dog_helper_class(pkg, "AWPDoghousePawn", "ControllerClass", yuri_dog, null_tex)
        _patch_dog_helper_class(pkg, "SuperChamp", "ControllerClass", yuri_dog, null_tex)

    def ops_pl_pawns(pkg: ue2_io.UE2Package) -> None:
        yuri_dog = _imp_skel(pkg, "Characters", "Doki_YuriDog")
        yuri_human = _imp_skel(pkg, "Characters", "Doki_Yuri")
        nh_hd = _imp_skel(pkg, "heads", "Doki_NullHead")
        null_tex = _imp_tex(pkg, "DokiSkins", "Doki_NullTex")
        _patch_dog_helper_class(pkg, "PLSuperChamp", "ControllerClass", yuri_dog, null_tex)
        _patch_dog_helper_class(pkg, "MutantDoghousePawn", "ControllerClass", yuri_dog, null_tex)

        rws_sim_ei = pkg.find_export_ci("PartnerPawn_RWSSim")
        assert rws_sim_ei is not None, "PartnerPawn_RWSSim not found in PLPawns.u"
        ue2_io.patch_class_defprop_obj(pkg, "PartnerRadioWeapon", "CommandList", "PartnerClass", rws_sim_ei)

        headless_props = [
            ("bHasHead", ue2_io.encode_prop_bool(pkg.ensure_name("bHasHead"), False)),
            ("bHeadCanComeOff", ue2_io.encode_prop_bool(pkg.ensure_name("bHeadCanComeOff"), False)),
            ("bChameleon", ue2_io.encode_prop_bool(pkg.ensure_name("bChameleon"), False)),
            ("bNoChamelBoltons", ue2_io.encode_prop_bool(pkg.ensure_name("bNoChamelBoltons"), True)),
            ("HeadClass", ue2_io.encode_prop_obj(pkg.ensure_name("HeadClass"), 0)),
        ]

        # Patch base PartnerPawn, PLUncleDave, and PartnerPawn_Pisstrap too so NO partner class can ever spawn a head!
        ue2_io.upsert_class_defprops(
            pkg,
            "PartnerPawn",
            "PartnerSpeedScale",
            headless_props + [
                ("Mesh", ue2_io.encode_prop_obj(pkg.ensure_name("Mesh"), yuri_human)),
                ("HeadMesh", ue2_io.encode_prop_obj(pkg.ensure_name("HeadMesh"), nh_hd)),
                ("HeadSkin", ue2_io.encode_prop_obj(pkg.ensure_name("HeadSkin"), null_tex)),
                ("Skins", ue2_io.encode_prop_obj_array(pkg.ensure_name("Skins"), [null_tex])),
            ],
        )
        ue2_io.upsert_class_defprops(
            pkg,
            "PLUncleDave",
            "TakesOnFireDamage",
            headless_props + [
                ("Mesh", ue2_io.encode_prop_obj(pkg.ensure_name("Mesh"), yuri_human)),
                ("HeadMesh", ue2_io.encode_prop_obj(pkg.ensure_name("HeadMesh"), nh_hd)),
                ("HeadSkin", ue2_io.encode_prop_obj(pkg.ensure_name("HeadSkin"), null_tex)),
                ("Skins", ue2_io.encode_prop_obj_array(pkg.ensure_name("Skins"), [null_tex])),
            ],
        )
        ue2_io.upsert_class_defprops(
            pkg,
            "PartnerPawn_Pisstrap",
            "bHasHead",
            headless_props + [
                ("Mesh", ue2_io.encode_prop_obj(pkg.ensure_name("Mesh"), yuri_human)),
                ("HeadMesh", ue2_io.encode_prop_obj(pkg.ensure_name("HeadMesh"), nh_hd)),
                ("HeadSkin", ue2_io.encode_prop_obj(pkg.ensure_name("HeadSkin"), null_tex)),
                ("Skins", ue2_io.encode_prop_obj_array(pkg.ensure_name("Skins"), [null_tex])),
            ],
        )

        for pname in (
            "PLUncleDaveHelper",
            "PartnerPawn_RWSSim",
            "PartnerPawn_UncleDave",
            "PartnerPawn_RWSRikki",
            "PartnerPawn_RWSRickF",
            "PartnerPawn_RWSMikeJ",
            "PartnerPawn_RWSMick",
            "PartnerPawn_RWSKurt",
            "PartnerPawn_RWSJon",
            "PartnerPawn_RWSBob",
        ):
            ue2_io.patch_class_defprop_obj(pkg, pname, "ExtraAnims", "Mesh", yuri_human)
            ue2_io.patch_class_defprop_obj(pkg, pname, "ExtraAnims", "HeadMesh", nh_hd)
            ue2_io.patch_class_defprop_obj(pkg, pname, "ExtraAnims", "HeadSkin", null_tex)
            ue2_io.clear_class_defprop_array(pkg, pname, "ExtraAnims", "RandomizedBoltons")
            ue2_io.upsert_class_defprops(
                pkg,
                pname,
                "ExtraAnims",
                headless_props + [
                    ("Skins", ue2_io.encode_prop_obj_array(pkg.ensure_name("Skins"), [null_tex])),
                ],
            )
            ue2_io.null_class_struct_inner_obj(pkg, pname, "ExtraAnims", "Boltons", "StaticMesh")

        # Also patch PartnerRadioWeapon.SpawnPartner so Pawn(Owner).Controller.MonitoredPawn = Partner
        # for Split-Screen Co-op camera tracking!
        eng_pkg = pkg.ensure_import("Core", "Package", 0, "Engine")
        cls_ctrl = pkg.ensure_import("Core", "Class", eng_pkg, "Controller")
        prop_monitored = pkg.ensure_import("Core", "ObjectProperty", cls_ctrl, "MonitoredPawn")
        for i, exp in enumerate(pkg.exports):
            if pkg.obj_name(exp.outer_idx) == "PartnerRadioWeapon" and pkg.names[exp.object_name][0] == "SpawnPartner":
                raw = pkg.raw[exp.serial_offset:exp.serial_offset + exp.serial_size]
                if len(raw) == 261:
                    hdr = raw[:17]
                    orig_script_size = struct.unpack("<I", raw[17:21])[0]
                    body = raw[21:-7]
                    tail = raw[-7:]
                    assign_monitored = (
                        b"\x0f\x19\x19\x2e\x87\x01\xd4\x01\x05\x00\x04\x01\xa7"
                        b"\x05\x00\x04\x01" + ue2_io.write_ci(prop_monitored)
                        + b"\x01\x6f\x02"
                    )
                    new_body = body[:-2] + assign_monitored + b"\x04\x0b"
                    new_raw = hdr + struct.pack("<I", orig_script_size + 34) + new_body + tail
                    pkg.replace_export_payload(i + 1, new_raw)
                break

    def ops_pl_game(pkg: ue2_io.UE2Package) -> None:
        null_tex = _imp_tex(pkg, "DokiSkins", "Doki_NullTex")
        plpawns_pkg = pkg.ensure_import("Core", "Package", 0, "PLPawns")
        rws_sim_cls = pkg.ensure_import("Core", "Class", plpawns_pkg, "PartnerPawn_RWSSim")
        partner_entry = (
            ue2_io.encode_prop_float(pkg.ensure_name("Weight"), 100.0)
            + ue2_io.encode_prop_obj(pkg.ensure_name("PawnClass"), rws_sim_cls)
            + ue2_io.write_ci(pkg.ensure_name("None"))
        )
        ue2_io.upsert_class_defprops(
            pkg,
            "PLCheatManager",
            "PossiblePartners",
            [
                (
                    "PossiblePartners",
                    ue2_io.encode_prop_struct_array(pkg.ensure_name("PossiblePartners"), [partner_entry]),
                ),
                ("MutantSkins", ue2_io.encode_prop_obj_array(pkg.ensure_name("MutantSkins"), [null_tex])),
                ("DogSkins", ue2_io.encode_prop_obj_array(pkg.ensure_name("DogSkins"), [null_tex])),
            ],
        )

    def ops_base_inventory(pkg: ue2_io.UE2Package) -> None:
        nat = _imp_skel(pkg, "Characters", "Doki_Natsuki")
        say = _imp_skel(pkg, "Characters", "Doki_Sayori")
        mon = _imp_skel(pkg, "Characters", "Doki_Monika")
        yur = _imp_skel(pkg, "Characters", "Doki_Yuri")
        nh_hd = _imp_skel(pkg, "heads", "Doki_NullHead")
        null_tex = _imp_tex(pkg, "DokiSkins", "Doki_NullTex")

        # 4-Doki Selector mapping via SetClothes:
        # 1) DudeClothesInv -> Doki_Natsuki (default player clothes + SetClothes Inventory.DudeClothesInv)
        # 2) GimpClothesInv -> Doki_Sayori  (SetClothes Inventory.GimpClothesInv)
        # 3) CopClothesInv  -> Doki_Monika  (SetClothes Inventory.CopClothesInv)
        # 4) ClothesInv     -> Doki_Yuri    (SetClothes Inventory.ClothesInv, bAllowKeep=False)
        ue2_io.upsert_class_defprops(
            pkg,
            "DudeClothesInv",
            "bPaidFor",
            [
                ("BodyMesh", ue2_io.encode_prop_obj(pkg.ensure_name("BodyMesh"), nat)),
                ("BodySkin", ue2_io.encode_prop_obj(pkg.ensure_name("BodySkin"), null_tex)),
                ("HeadMesh", ue2_io.encode_prop_obj(pkg.ensure_name("HeadMesh"), nh_hd)),
                ("HeadSkin", ue2_io.encode_prop_obj(pkg.ensure_name("HeadSkin"), null_tex)),
            ],
        )
        ue2_io.patch_class_defprop_obj(pkg, "ClothesInv", "BodyMesh", "BodyMesh", yur)
        ue2_io.patch_class_defprop_obj(pkg, "ClothesInv", "BodyMesh", "HeadMesh", nh_hd)
        ue2_io.upsert_class_defprops(
            pkg,
            "ClothesInv",
            "BodyMesh",
            [
                ("BodySkin", ue2_io.encode_prop_obj(pkg.ensure_name("BodySkin"), null_tex)),
                ("HeadSkin", ue2_io.encode_prop_obj(pkg.ensure_name("HeadSkin"), null_tex)),
                ("bAllowKeep", ue2_io.encode_prop_bool(pkg.ensure_name("bAllowKeep"), False)),
            ],
        )
        ue2_io.patch_class_defprop_obj(pkg, "GimpClothesInv", "BodyMesh", "BodyMesh", say)
        ue2_io.patch_class_defprop_obj(pkg, "GimpClothesInv", "BodyMesh", "HeadMesh", nh_hd)
        ue2_io.patch_class_defprop_obj(pkg, "CopClothesInv", "BodyMesh", "BodyMesh", mon)
        ue2_io.clear_class_defprop_array(pkg, "CopClothesInv", "BodyMesh", "xBoltons")

    def ops_pl_inventory(pkg: ue2_io.UE2Package) -> None:
        mon = _imp_skel(pkg, "Characters", "Doki_Monika")
        nh_mh = _imp_skel(pkg, "MoreHeads", "Doki_NullHead")
        ue2_io.patch_class_defprop_obj(pkg, "LawmanClothesInv", "BodyMesh", "BodyMesh", mon)
        ue2_io.patch_class_defprop_obj(pkg, "LawmanClothesInv", "BodyMesh", "HeadMesh", nh_mh)
        ue2_io.null_class_struct_inner_obj(pkg, "LawmanClothesInv", "BodyMesh", "Bolton", "StaticMesh")

    def ops_stp_base_people(pkg: ue2_io.UE2Package) -> None:
        ei = pkg.find_export_ci("Dude")
        assert ei is not None
        try:
            ue2_io.find_defprop_span(pkg, ei, "CoreSPMesh", "CoreSPMesh")
            nat = _imp_skel(pkg, "Characters", "Doki_Natsuki")
            ue2_io.patch_class_defprop_obj(pkg, "Dude", "CoreSPMesh", "CoreSPMesh", nat)
        except KeyError:
            print("  NOTE: ShareThePain BasePeople.u::Dude has no CoreSPMesh defaultprop; skipped")

    def ops_stp_inventory(pkg: ue2_io.UE2Package) -> None:
        nat = _imp_skel(pkg, "Characters", "Doki_Natsuki")
        say = _imp_skel(pkg, "Characters", "Doki_Sayori")
        mon = _imp_skel(pkg, "Characters", "Doki_Monika")
        nh_hd = _imp_skel(pkg, "heads", "Doki_NullHead")
        ue2_io.patch_class_defprop_obj(pkg, "ClothesInv", "BodyMesh", "BodyMesh", nat)
        ue2_io.patch_class_defprop_obj(pkg, "ClothesInv", "BodyMesh", "HeadMesh", nh_hd)
        ue2_io.patch_class_defprop_obj(pkg, "GimpClothesInv", "BodyMesh", "BodyMesh", say)
        ue2_io.patch_class_defprop_obj(pkg, "GimpClothesInv", "BodyMesh", "HeadMesh", nh_hd)
        ue2_io.patch_class_defprop_obj(pkg, "CopClothesInv", "BodyMesh", "BodyMesh", mon)

    def ops_stp_multistuff(pkg: ue2_io.UE2Package) -> None:
        nat = _imp_skel(pkg, "Characters", "Doki_Natsuki")
        say = _imp_skel(pkg, "Characters", "Doki_Sayori")
        nh_hd = _imp_skel(pkg, "heads", "Doki_NullHead")
        ue2_io.patch_class_defprop_obj(pkg, "MpDude", "Mesh", "Mesh", nat)
        ue2_io.patch_class_defprop_obj(pkg, "MpDude", "HeadSkin", "HeadMesh", nh_hd)
        ue2_io.patch_class_defprop_obj(pkg, "MpGimp", "Mesh", "Mesh", say)
        ue2_io.patch_class_defprop_obj(pkg, "MpGimp", "HeadSkin", "HeadMesh", nh_hd)

    patch_u_file("System/AWPStuff.u", ops_awp_stuff)
    patch_u_file("System/BasePeople.u", ops_base_people)
    patch_u_file("System/People.u", ops_people)
    patch_u_file("System/GameTypes.u", ops_gametypes)
    patch_u_file("System/Inventory.u", ops_base_inventory)
    patch_u_file("Paradise Lost/System/PLGame.u", ops_pl_game)
    patch_u_file("Paradise Lost/System/PLInventory.u", ops_pl_inventory)
    patch_u_file("Paradise Lost/System/PLPawns.u", ops_pl_pawns)
    patch_u_file("ShareThePain/System/BasePeople.u", ops_stp_base_people)
    patch_u_file("ShareThePain/System/People.u", ops_people)
    patch_u_file("ShareThePain/System/Inventory.u", ops_stp_inventory)
    patch_u_file("ShareThePain/System/MultiStuff.u", ops_stp_multistuff)

    # 5. Reload & verify every patched .u property
    verify_u_obj("System/AWPStuff.u", "AWPDoghousePawn", "ControllerClass", "Mesh", "Doki_YuriDog")
    verify_u_obj("System/AWPStuff.u", "SuperChamp", "ControllerClass", "Mesh", "Doki_YuriDog")
    verify_u_obj("System/BasePeople.u", "AWDude", "LeprechaunDrawScale", "Mesh", "Doki_Natsuki")
    verify_u_obj("System/BasePeople.u", "AWDude", "LeprechaunDrawScale", "HeadMesh", "Doki_NullHead")
    verify_u_obj("System/BasePeople.u", "Dude", "FootstepSounds", "CoreSPMesh", "Doki_Natsuki")
    verify_u_obj("System/People.u", "PostalDude", "Mesh", "Mesh", "Doki_Natsuki")
    verify_u_obj("System/People.u", "PostalDude", "HeadSkin", "HeadMesh", "Doki_NullHead")
    verify_u_obj("System/GameTypes.u", "AWPostalDude", "ExpectedHeadMesh", "ExpectedHeadMesh", "Doki_NullHead")
    verify_u_obj("System/GameTypes.u", "AWPostalDude", "ExpectedHeadMesh", "OldHeadMesh", "Doki_NullHead")
    verify_u_obj("System/Inventory.u", "DudeClothesInv", "bPaidFor", "BodyMesh", "Doki_Natsuki")
    verify_u_obj("System/Inventory.u", "ClothesInv", "BodyMesh", "BodyMesh", "Doki_Yuri")
    verify_u_obj("System/Inventory.u", "ClothesInv", "BodyMesh", "HeadMesh", "Doki_NullHead")
    verify_u_obj("System/Inventory.u", "GimpClothesInv", "BodyMesh", "BodyMesh", "Doki_Sayori")
    verify_u_obj("System/Inventory.u", "GimpClothesInv", "BodyMesh", "HeadMesh", "Doki_NullHead")
    verify_u_obj("System/Inventory.u", "CopClothesInv", "BodyMesh", "BodyMesh", "Doki_Monika")
    verify_u_obj("Paradise Lost/System/PLInventory.u", "LawmanClothesInv", "BodyMesh", "BodyMesh", "Doki_Monika")
    verify_u_obj("Paradise Lost/System/PLInventory.u", "LawmanClothesInv", "BodyMesh", "HeadMesh", "Doki_NullHead")
    verify_u_obj("Paradise Lost/System/PLPawns.u", "PLSuperChamp", "ControllerClass", "Mesh", "Doki_YuriDog")
    verify_u_obj("Paradise Lost/System/PLPawns.u", "MutantDoghousePawn", "ControllerClass", "Mesh", "Doki_YuriDog")
    verify_u_obj("Paradise Lost/System/PLPawns.u", "PLUncleDaveHelper", "ExtraAnims", "Mesh", "Doki_Yuri")
    verify_u_obj("Paradise Lost/System/PLPawns.u", "PartnerPawn_RWSSim", "ExtraAnims", "Mesh", "Doki_Yuri")
    verify_u_obj("Paradise Lost/System/PLPawns.u", "PartnerPawn_RWSSim", "ExtraAnims", "HeadMesh", "Doki_NullHead")
    verify_u_obj("Paradise Lost/System/PLPawns.u", "PartnerRadioWeapon", "CommandList", "PartnerClass", "PartnerPawn_RWSSim")
    verify_u_obj("ShareThePain/System/People.u", "PostalDude", "Mesh", "Mesh", "Doki_Natsuki")
    verify_u_obj("ShareThePain/System/People.u", "PostalDude", "HeadSkin", "HeadMesh", "Doki_NullHead")
    verify_u_obj("ShareThePain/System/Inventory.u", "ClothesInv", "BodyMesh", "BodyMesh", "Doki_Natsuki")
    verify_u_obj("ShareThePain/System/Inventory.u", "ClothesInv", "BodyMesh", "HeadMesh", "Doki_NullHead")
    verify_u_obj("ShareThePain/System/Inventory.u", "GimpClothesInv", "BodyMesh", "BodyMesh", "Doki_Sayori")
    verify_u_obj("ShareThePain/System/Inventory.u", "GimpClothesInv", "BodyMesh", "HeadMesh", "Doki_NullHead")
    verify_u_obj("ShareThePain/System/Inventory.u", "CopClothesInv", "BodyMesh", "BodyMesh", "Doki_Monika")
    verify_u_obj("ShareThePain/System/MultiStuff.u", "MpDude", "Mesh", "Mesh", "Doki_Natsuki")
    verify_u_obj("ShareThePain/System/MultiStuff.u", "MpDude", "HeadSkin", "HeadMesh", "Doki_NullHead")
    verify_u_obj("ShareThePain/System/MultiStuff.u", "MpGimp", "Mesh", "Mesh", "Doki_Sayori")
    verify_u_obj("ShareThePain/System/MultiStuff.u", "MpGimp", "HeadSkin", "HeadMesh", "Doki_NullHead")
    print("ALL PATCHED PACKAGES VERIFIED!")

    # 6. Clean any stale NPC head (myHead) in existing Paradise Lost .usa save files
    import glob
    for usa_path in sorted(glob.glob(os.path.expanduser("~/.lgp/postal2/PLSave/*.usa"))):
        try:
            usa = ue2_io.UE2Package.load(usa_path)
            modified = False
            for idx_e, exp in enumerate(usa.exports):
                cls_nm = usa.obj_name(exp.class_idx)
                if "PartnerPawn" in cls_nm or "UncleDave" in cls_nm:
                    raw = bytearray(usa.raw[exp.serial_offset:exp.serial_offset + exp.serial_size])
                    for idx_n, (n_str, _) in enumerate(usa.names):
                        if n_str == "myHead":
                            pat = ue2_io.write_ci(idx_n) + b"\x15"
                            pos = raw.find(pat)
                            if pos >= 0:
                                _, ci_len = ue2_io.read_ci(raw, pos + len(pat))
                                if raw[pos + len(pat):pos + len(pat) + ci_len] != b"\x00":
                                    raw[pos:pos + len(pat) + ci_len] = ue2_io.write_ci(idx_n) + b"\x15\x00"
                                    usa.replace_export_payload(idx_e + 1, bytes(raw))
                                    modified = True
            if modified:
                usa.save(usa_path)
                print(f"  Cleaned stale NPC myHead from save: {usa_path}")
        except Exception as exc:
            print(f"  Warning cleaning save {usa_path}: {exc}")

    # 7. Install 4-Doki Selector & Split-Screen Co-op aliases / keybinds in User.ini & Default.ini
    _install_doki_ini_bindings(P2_ROOT)

    try:
        import install_doki_audio
        install_doki_audio.write_restore_script()
    except ImportError:
        pass


if __name__ == "__main__":
    main()

