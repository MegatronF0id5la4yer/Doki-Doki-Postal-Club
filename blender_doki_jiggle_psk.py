"""Blender (bpy) pipeline script for Yuri & Monika:
1. Smooth anterior upper-torso / pectoral volume deformation with front-axis falloff
   (preserves topology, vertex order, and UVs 100%).
2. Adds child bones `jiggle_L` and `jiggle_R` parented to `MALE01 spine2` (`Spine2`)
   at the end of the bone list so original bone indices/names stay intact for `.psa`.
3. Assigns smooth dual-lobe pectoral weights to `jiggle_L` and `jiggle_R` balanced with `Spine2`.
4. Re-exports ActorX `.psk` (ACTRHEAD / PNTS0000 / VTXW0000 / FACE0000 / MATT0000 / REFSKELT / RAWWEIGHTS).
"""
from __future__ import annotations

import math
import os
import struct
from typing import Dict, List, Optional, Tuple

try:
    import bpy
    import mathutils
except ImportError:
    bpy = None  # Allows importing helper math / PSK writer outside Blender


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge1 <= edge0:
        return 1.0 if x >= edge1 else 0.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def pectoral_falloff(
    x: float, y_front: float, z: float, character: str = "Yuri"
) -> Tuple[float, float, float, float]:
    """Compute C1-smooth anterior pectoral falloff & displacement (dx, dy_front, dz, weight).
    Preserves topology and UVs.
    """
    is_yuri = "yuri" in character.lower()
    z_c = 51.8 if is_yuri else 52.2
    amp_y = 1.45 if is_yuri else 1.15

    if y_front <= 0.6 or z < 47.5 or z > 56.2 or abs(x) > 4.6:
        return 0.0, 0.0, 0.0, 0.0

    fy = _smoothstep(0.6, 2.3, y_front) * (1.0 - 0.20 * _smoothstep(4.8, 7.2, y_front))
    r2_l = ((x - 1.65) / 2.15) ** 2 + ((z - z_c) / 2.85) ** 2
    r2_r = ((x + 1.65) / 2.15) ** 2 + ((z - z_c) / 2.85) ** 2
    lobe_l = max(0.0, 1.0 - r2_l) ** 2
    lobe_r = max(0.0, 1.0 - r2_r) ** 2
    f_pec = fy * min(1.0, lobe_l + lobe_r)
    if f_pec <= 1e-4:
        return 0.0, 0.0, 0.0, 0.0

    dy_front = amp_y * f_pec
    dz = 0.18 * f_pec * ((z - z_c) / 2.85)
    dx = 0.16 * f_pec * (1.0 if x >= 0.0 else -1.0) * _smoothstep(0.3, 1.8, abs(x))
    return dx, dy_front, dz, f_pec


def apply_blender_pectoral_and_jiggle_rig(
    armature_obj,
    mesh_obj,
    character: str = "Yuri",
    spine2_bone_name: str = "MALE01 spine2",
) -> None:
    """Apply pectoral volume falloff, add jiggle_L / jiggle_R bones under Spine2, and weight paint."""
    if bpy is None:
        raise RuntimeError("This function must be executed inside Blender (bpy).")

    # 1. Add jiggle_L and jiggle_R parented to Spine2 in Edit Mode
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode="EDIT")
    ebones = armature_obj.data.edit_bones
    parent_bone = ebones.get(spine2_bone_name) or ebones.get("Spine2") or ebones.get("ValveBiped.Bip01_Spine2")
    if parent_bone is None:
        raise KeyError(f"Parent spine2 bone '{spine2_bone_name}' not found in armature.")

    for bname, x_off in (("jiggle_L", 1.65), ("jiggle_R", -1.65)):
        jb = ebones.get(bname)
        if jb is None:
            jb = ebones.new(bname)
        jb.parent = parent_bone
        jb.use_connect = False
        jb.head = parent_bone.head + mathutils.Vector((x_off, -2.8, 3.2))
        jb.tail = jb.head + mathutils.Vector((0.0, -2.0, 0.4))

    bpy.ops.object.mode_set(mode="OBJECT")

    # 2. Ensure vertex groups exist for jiggle_L and jiggle_R
    vg_sp2 = mesh_obj.vertex_groups.get(parent_bone.name)
    vg_jl = mesh_obj.vertex_groups.get("jiggle_L") or mesh_obj.vertex_groups.new(name="jiggle_L")
    vg_jr = mesh_obj.vertex_groups.get("jiggle_R") or mesh_obj.vertex_groups.new(name="jiggle_R")

    # 3. Deform anterior upper torso vertices and assign smooth weights
    mesh = mesh_obj.data
    for v in mesh.vertices:
        sx, sy_raw, sz = v.co.x, v.co.y, v.co.z
        y_front = -sy_raw
        dx, dy_front, dz, f_pec = pectoral_falloff(sx, y_front, sz, character)
        if f_pec <= 1e-4:
            continue

        # Update vertex position (preserving topology & UVs)
        v.co.x += dx
        v.co.y -= dy_front
        v.co.z += dz

        if vg_sp2 is not None and f_pec > 0.02:
            try:
                w_sp2 = vg_sp2.weight(v.index)
            except RuntimeError:
                w_sp2 = 0.0
            if w_sp2 > 0.15:
                j_share = min(0.68, 0.72 * f_pec) * w_sp2
                lr_j = _smoothstep(-1.2, 1.2, sx)
                vg_sp2.add([v.index], max(0.0, w_sp2 - j_share), "REPLACE")
                if j_share * lr_j > 0.004:
                    vg_jl.add([v.index], j_share * lr_j, "REPLACE")
                if j_share * (1.0 - lr_j) > 0.004:
                    vg_jr.add([v.index], j_share * (1.0 - lr_j), "REPLACE")

    mesh.update()


def _pack_psk_chunk_header(chunk_id: bytes, type_flag: int, data_size: int, data_count: int) -> bytes:
    return struct.pack("<20s3i", chunk_id.ljust(20, b"\x00"), type_flag, data_size, data_count)


def export_psk_preserving_bone_order(
    out_psk_path: str,
    pts: List[Tuple[float, float, float]],
    wdgs: List[Tuple[int, float, float]],
    fcs: List[Tuple[int, int, int, int]],
    mat_names: List[str],
    bones: List[Tuple[str, int, Tuple[float, float, float, float], Tuple[float, float, float], Tuple[float, float, float, float], int, int]],
    infs: List[Tuple[float, int, int]],
) -> None:
    """Write an ActorX .psk file preserving exact bone order (0..55 original + 56:jiggle_L, 57:jiggle_R)."""
    with open(out_psk_path, "wb") as f:
        f.write(_pack_psk_chunk_header(b"ACTRHEAD", 1999801, 0, 0))

        f.write(_pack_psk_chunk_header(b"PNTS0000", 1999801, 12, len(pts)))
        for x, y, z in pts:
            f.write(struct.pack("<3f", x, y, z))

        f.write(_pack_psk_chunk_header(b"VTXW0000", 1999801, 16, len(wdgs)))
        for pi, u, v in wdgs:
            f.write(struct.pack("<HxxffBxH", pi, u, v, 0, 0))

        f.write(_pack_psk_chunk_header(b"FACE0000", 1999801, 12, len(fcs)))
        for w0, w1, w2, mat_idx in fcs:
            f.write(struct.pack("<3HBBI", w0, w1, w2, mat_idx & 0xFF, 0, 1))

        f.write(_pack_psk_chunk_header(b"MATT0000", 1999801, 88, len(mat_names)))
        for idx, mname in enumerate(mat_names):
            f.write(struct.pack("<64s6i", mname.encode("ascii", "ignore")[:63], idx, 0, 0, 0, 0, 0))

        f.write(_pack_psk_chunk_header(b"REFSKELT", 1999801, 120, len(bones)))
        for bname, bflags, quat, pos, _misc, num_children, parent_idx in bones:
            f.write(
                struct.pack(
                    "<64s3i4f3f4f",
                    bname.encode("ascii", "ignore")[:63],
                    bflags,
                    num_children,
                    parent_idx,
                    quat[0],
                    quat[1],
                    quat[2],
                    quat[3],
                    pos[0],
                    pos[1],
                    pos[2],
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                )
            )

        f.write(_pack_psk_chunk_header(b"RAWWEIGHTS", 1999801, 12, len(infs)))
        for weight, pt_idx, bone_idx in infs:
            f.write(struct.pack("<fii", weight, pt_idx, bone_idx))

