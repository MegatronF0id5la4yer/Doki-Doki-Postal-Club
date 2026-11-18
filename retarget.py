"""Retarget L4D2 Source Engine Doki characters to Postal 2 USkeletalMesh packages."""
from __future__ import annotations

import math
import os
import struct
from typing import Dict, List, Optional, Tuple

import source_loader
import ue2_io

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_p2_root() -> str:
    for cand in (
        os.environ.get("POSTAL2_ROOT", ""),
        os.path.expanduser("~/.local/share/Steam/steamapps/common/POSTAL2Complete"),
        os.path.expanduser("~/.steam/steam/steamapps/common/POSTAL2Complete"),
        "/home/foidslayer/.local/share/Steam/steamapps/common/POSTAL2Complete",
    ):
        if cand and os.path.isdir(cand):
            return cand
    return os.path.expanduser("~/.local/share/Steam/steamapps/common/POSTAL2Complete")


def _resolve_workshop_dir() -> str:
    for cand in (
        os.environ.get("L4D2_WORKSHOP_DIR", ""),
        os.path.join(_SCRIPT_DIR, "l4d2_workshop_vpks"),
        os.path.join(os.path.dirname(_SCRIPT_DIR), "l4d2_workshop_vpks"),
        os.path.expanduser("~/.local/share/Steam/steamapps/common/Left 4 Dead 2/left4dead2/addons/workshop"),
        os.path.expanduser("~/.steam/steam/steamapps/common/Left 4 Dead 2/left4dead2/addons/workshop"),
        "/home/foidslayer/.local/share/Steam/steamapps/common/Left 4 Dead 2/left4dead2/addons/workshop",
    ):
        if cand and os.path.isfile(os.path.join(cand, "2565563118.vpk")):
            return cand
    return os.path.join(_SCRIPT_DIR, "l4d2_workshop_vpks")


P2_ROOT = _resolve_p2_root()
WORKSHOP_DIR = _resolve_workshop_dir()

DOKI_SPECS = [
    (
        "Doki_Natsuki",
        "Natsuki",
        os.path.join(WORKSHOP_DIR, "2565563118.vpk"),
        "models/survivors/survivor_gambler.mdl",
        set(),
    ),
    (
        "Doki_Sayori",
        "Sayori",
        os.path.join(WORKSHOP_DIR, "2567184223.vpk"),
        "models/survivors/survivor_producer.mdl",
        set(),
    ),
    (
        "Doki_Monika",
        "Monika",
        os.path.join(WORKSHOP_DIR, "2561380893.vpk"),
        "models/survivors/survivor_mechanic.mdl",
        # Monika has duplicate coincident eye/eye2; eye2 has richer iris/lash detail
        {"eye"},
    ),
    (
        "Doki_Yuri",
        "Yuri",
        os.path.join(WORKSHOP_DIR, "2564088900.vpk"),
        "models/survivors/survivor_coach.mdl",
        set(),
    ),
]

# Map DogPawn / animDog sequence names -> human Characters.ukx::animAvg sequences for Yuri helper NPC
YURI_DOG_ANIM_MAP: List[Tuple[str, str]] = [
    ("lay_in", "cd_base_in"),
    ("lay_on", "cd_base"),
    ("lay_out", "cd_base_out"),
    ("run_scared", "sf_run1"),
    ("pounce", "s_runjump"),
    ("Die", "p_death3"),
    ("Walk", "sf_walk1"),
    ("Run", "sf_run2"),
    ("stand", "sf_base1"),
    ("bark", "s_angry"),
    ("piss", "s_piss"),
    ("attack", "sd_baton1"),
    ("limp", "s_walk4"),
    ("WindowJump", "s_jump"),
    ("WindowJump_inplace", "s_jump"),
]

SOURCE_TO_UE2_BONE = {
    "ValveBiped.Bip01_Pelvis": "MALE01 pelvis",
    "ValveBiped.Bip01_Spine": "MALE01 spine",
    "ValveBiped.Bip01_Spine1": "MALE01 spine1",
    "ValveBiped.Bip01_Spine2": "MALE01 spine2",
    "ValveBiped.Bip01_Spine4": "MALE01 spine2",
    "ValveBiped.Bip01_Neck1": "MALE01 neck",
    "ValveBiped.Bip01_Head1": "MALE01 head",
    "ValveBiped.Bip01_L_Clavicle": "MALE01 L Clavicle",
    "ValveBiped.Bip01_L_UpperArm": "MALE01 L UpperArm",
    "ValveBiped.Bip01_L_Forearm": "MALE01 L Forearm",
    "ValveBiped.Bip01_L_Ulna": "MALE01 L Forearm",
    "ValveBiped.Bip01_L_Wrist": "MALE01 L Forearm",
    "ValveBiped.Bip01_L_Hand": "MALE01 L Hand",
    "ValveBiped.Bip01_L_Finger0": "MALE01 L Finger0",
    "ValveBiped.Bip01_L_Finger01": "MALE01 L Finger01",
    "ValveBiped.Bip01_L_Finger02": "MALE01 L Finger01",
    "ValveBiped.Bip01_L_Finger1": "MALE01 L Finger1",
    "ValveBiped.Bip01_L_Finger11": "MALE01 L Finger11",
    "ValveBiped.Bip01_L_Finger12": "MALE01 L Finger11",
    "ValveBiped.Bip01_L_Finger2": "MALE01 L Finger2",
    "ValveBiped.Bip01_L_Finger21": "MALE01 L Finger21",
    "ValveBiped.Bip01_L_Finger22": "MALE01 L Finger21",
    "ValveBiped.Bip01_L_Finger3": "MALE01 L Finger3",
    "ValveBiped.Bip01_L_Finger31": "MALE01 L Finger31",
    "ValveBiped.Bip01_L_Finger32": "MALE01 L Finger31",
    "ValveBiped.Bip01_L_Finger4": "MALE01 L Finger4",
    "ValveBiped.Bip01_L_Finger41": "MALE01 L Finger41",
    "ValveBiped.Bip01_L_Finger42": "MALE01 L Finger41",
    "ValveBiped.Bip01_R_Clavicle": "MALE01 R Clavicle",
    "ValveBiped.Bip01_R_UpperArm": "MALE01 R UpperArm",
    "ValveBiped.Bip01_R_Forearm": "MALE01 R Forearm",
    "ValveBiped.Bip01_R_Ulna": "MALE01 R Forearm",
    "ValveBiped.Bip01_R_Wrist": "MALE01 R Forearm",
    "ValveBiped.Bip01_R_Hand": "MALE01 r hand",
    "ValveBiped.Bip01_R_Finger0": "MALE01 R Finger0",
    "ValveBiped.Bip01_R_Finger01": "MALE01 R Finger01",
    "ValveBiped.Bip01_R_Finger02": "MALE01 R Finger01",
    "ValveBiped.Bip01_R_Finger1": "MALE01 R Finger1",
    "ValveBiped.Bip01_R_Finger11": "MALE01 R Finger11",
    "ValveBiped.Bip01_R_Finger12": "MALE01 R Finger11",
    "ValveBiped.Bip01_R_Finger2": "MALE01 R Finger2",
    "ValveBiped.Bip01_R_Finger21": "MALE01 R Finger21",
    "ValveBiped.Bip01_R_Finger22": "MALE01 R Finger21",
    "ValveBiped.Bip01_R_Finger3": "MALE01 R Finger3",
    "ValveBiped.Bip01_R_Finger31": "MALE01 R Finger31",
    "ValveBiped.Bip01_R_Finger32": "MALE01 R Finger31",
    "ValveBiped.Bip01_R_Finger4": "MALE01 R Finger4",
    "ValveBiped.Bip01_R_Finger41": "MALE01 R Finger41",
    "ValveBiped.Bip01_R_Finger42": "MALE01 R Finger41",
    "ValveBiped.Bip01_L_Thigh": "MALE01 L Thigh",
    "ValveBiped.Bip01_L_Calf": "MALE01 L Calf",
    "ValveBiped.Bip01_L_Foot": "MALE01 L Foot",
    "ValveBiped.Bip01_L_Toe0": "MALE01 L Toe0",
    "ValveBiped.Bip01_R_Thigh": "MALE01 R Thigh",
    "ValveBiped.Bip01_R_Calf": "MALE01 r calf",
    "ValveBiped.Bip01_R_Foot": "MALE01 r foot",
    "ValveBiped.Bip01_R_Toe0": "MALE01 R Toe0",
}


Vec3 = Tuple[float, float, float]
Mat3 = List[List[float]]


def _vadd(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _vsub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vscale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _vdot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _vcross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _vlen(a: Vec3) -> float:
    return math.sqrt(_vdot(a, a))


def _vunit(a: Vec3) -> Vec3:
    l = _vlen(a)
    return (a[0] / l, a[1] / l, a[2] / l) if l > 1e-9 else (1.0, 0.0, 0.0)


def _eye3() -> Mat3:
    return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _mat3_mul(A: Mat3, B: Mat3) -> Mat3:
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _mat3_vec(A: Mat3, v: Vec3) -> Vec3:
    return (
        A[0][0] * v[0] + A[0][1] * v[1] + A[0][2] * v[2],
        A[1][0] * v[0] + A[1][1] * v[1] + A[1][2] * v[2],
        A[2][0] * v[0] + A[2][1] * v[1] + A[2][2] * v[2],
    )


def _mat3_inv(M: Mat3) -> Mat3:
    a, b, c = M[0]
    d, e, f = M[1]
    g, h, i = M[2]
    A = e * i - f * h
    B = -(d * i - f * g)
    C = d * h - e * g
    D = -(b * i - c * h)
    E = a * i - c * g
    F = -(a * h - b * g)
    G = b * f - c * e
    H = -(a * f - c * d)
    I = a * e - b * d
    det = a * A + b * B + c * C
    if abs(det) < 1e-12:
        return _eye3()
    inv_d = 1.0 / det
    return [
        [A * inv_d, D * inv_d, G * inv_d],
        [B * inv_d, E * inv_d, H * inv_d],
        [C * inv_d, F * inv_d, I * inv_d],
    ]


def _mat3_T(M: Mat3) -> Mat3:
    return [[M[j][i] for j in range(3)] for i in range(3)]


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def _closest_on_seg(p: Vec3, a: Vec3, b: Vec3) -> Tuple[float, float, Vec3]:
    ab = _vsub(b, a)
    ab2 = _vdot(ab, ab)
    if ab2 <= 1e-9:
        return _vlen(_vsub(p, a)), 0.0, a
    t = max(0.0, min(1.0, _vdot(_vsub(p, a), ab) / ab2))
    q = _vadd(a, _vscale(ab, t))
    return _vlen(_vsub(p, q)), t, q


def _rot_vec_to_vec(u: Vec3, v: Vec3) -> Mat3:
    u = _vunit(u)
    v = _vunit(v)
    c = max(-1.0, min(1.0, _vdot(u, v)))
    if c > 1.0 - 1e-7:
        return _eye3()
    w = _vcross(u, v)
    s = _vlen(w)
    if s < 1e-7:
        axis = _vcross(u, (0.0, 1.0, 0.0))
        if _vlen(axis) < 1e-5:
            axis = _vcross(u, (0.0, 0.0, 1.0))
        axis = _vunit(axis)
        x, y, z = axis
        return [
            [2 * x * x - 1, 2 * x * y, 2 * x * z],
            [2 * x * y, 2 * y * y - 1, 2 * y * z],
            [2 * x * z, 2 * y * z, 2 * z * z - 1],
        ]
    kx, ky, kz = (w[0] / s, w[1] / s, w[2] / s)
    # Rodrigues: R = I + sin*K + (1-cos)*K^2
    K = [[0.0, -kz, ky], [kz, 0.0, -kx], [-ky, kx, 0.0]]
    K2 = _mat3_mul(K, K)
    omc = 1.0 - c
    return [
        [_eye3()[r][col] + s * K[r][col] + omc * K2[r][col] for col in range(3)]
        for r in range(3)
    ]


def _seg_transform(
    a_src: Vec3,
    b_src: Vec3,
    a_dst: Vec3,
    b_dst: Vec3,
    stretch_axis: bool = True,
) -> Tuple[Mat3, Vec3]:
    """Build affine transform (M, t) mapping a_src->a_dst, b_src->b_dst without cross-section distortion."""
    vs = _vsub(b_src, a_src)
    vd = _vsub(b_dst, a_dst)
    ls = _vlen(vs)
    ld = _vlen(vd)
    assert ls > 1e-5 and ld > 1e-5, (vs, vd)
    us = _vscale(vs, 1.0 / ls)
    ud = _vscale(vd, 1.0 / ld)
    R = _rot_vec_to_vec(us, ud)
    if stretch_axis:
        k = (ld / ls) - 1.0
        S = [[(1.0 if i == j else 0.0) + k * ud[i] * ud[j] for j in range(3)] for i in range(3)]
        M = _mat3_mul(S, R)
    else:
        M = R
    Ma = _mat3_vec(M, a_src)
    t = _vsub(a_dst, Ma)
    return M, t


def _quat_to_mat3(q: Tuple[float, ...], conj: bool) -> Mat3:
    x, y, z, w = q
    if conj:
        x, y, z = -x, -y, -z
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return [
        [1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy)],
        [2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx)],
        [2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy)],
    ]


def compute_ue2_bone_world(template: ue2_io.SkelMeshTemplate) -> Dict[str, Vec3]:
    """Compute world positions of UE2 RefSkeleton bones (root non-conjugated, child conjugated)."""
    R_list: List[Mat3] = []
    P_list: List[Vec3] = []
    out: Dict[str, Vec3] = {}
    for i, (bname, _flags, q, p, _dims, _nchild, par) in enumerate(template.bones):
        rl = _quat_to_mat3(q, conj=(i > 0))
        if i == 0 or par < 0 or par >= i:
            R_list.append(rl)
            P_list.append(p)
        else:
            dp = _mat3_vec(R_list[par], p)
            R_list.append(_mat3_mul(R_list[par], rl))
            P_list.append(_vadd(P_list[par], dp))
        out[bname] = P_list[i]
    return out


def _apply_affine(M: Mat3, t: Vec3, p: Vec3) -> Vec3:
    return _vadd(_mat3_vec(M, p), t)


def build_doki_textures(out_utx_path: str) -> Dict[str, Dict[str, str]]:
    """Build DokiSkins.utx with Doki_NullTex plus TwoSided Shaders for all 3 Dokis."""
    utx = ue2_io.UE2Package.new_empty()
    core_pkg = utx.ensure_import("Core", "Package", 0, "Core")
    eng_pkg = utx.ensure_import("Core", "Package", 0, "Engine")
    cls_pkg = utx.ensure_import("Core", "Class", core_pkg, "Package")
    cls_tex = utx.ensure_import("Core", "Class", eng_pkg, "Texture")
    cls_shd = utx.ensure_import("Core", "Class", eng_pkg, "Shader")

    null_mips = [
        b"\x00\x00\x00\x00" * 16,
        b"\x00\x00\x00\x00" * 4,
        b"\x00\x00\x00\x00",
        b"\x00\x00\x00\x00",
    ]
    utx.add_export_builder(
        cls_tex,
        0,
        0,
        "Doki_NullTex",
        ue2_io.RF_DEFAULT_TEX,
        lambda off: ue2_io.build_utexture_payload(utx, 4, 4, 5, null_mips, off),
    )

    mat_map: Dict[str, Dict[str, str]] = {}
    for mesh_name, grp_name, vpk_path, mdl_path, skip_mats in DOKI_SPECS:
        ch = source_loader.load_source_character(vpk_path, mdl_path)
        grp_ref = utx.add_group_export(cls_pkg, grp_name, 0)
        m_dict: Dict[str, str] = {}
        for part in ch.parts:
            if part.material_name in skip_mats or part.material_name in m_dict:
                continue
            stex = ch.textures[part.material_name]
            ue2_fmt = 8 if stex.vtf_format == 15 else 5
            clean_nm = part.material_name.replace("/", "_").replace(".", "_")
            tex_ref = utx.add_export_builder(
                cls_tex,
                0,
                grp_ref,
                clean_nm + "_T",
                ue2_io.RF_DEFAULT_TEX,
                lambda off, st=stex, fm=ue2_fmt: ue2_io.build_utexture_payload(
                    utx, st.width, st.height, fm, st.mips_largest_first, off
                ),
            )
            utx.add_export_builder(
                cls_shd,
                0,
                grp_ref,
                clean_nm,
                ue2_io.RF_DEFAULT_OBJ,
                lambda off, tr=tex_ref: ue2_io.build_shader_payload(
                    utx, tr, two_sided=True
                ),
            )
            m_dict[part.material_name] = clean_nm
        mat_map[mesh_name] = m_dict

    utx.save(out_utx_path)
    return mat_map


def retarget_source_character(
    template: ue2_io.SkelMeshTemplate,
    vpk_path: str,
    mdl_rel_path: str,
    skip_mats: set,
    mesh_name: str = "",
) -> Tuple[
    List[Vec3],
    List[Vec3],
    List[Tuple[int, float, float]],
    List[Tuple[int, int, int, int]],
    List[Tuple[float, int, int]],
    List[str],
]:
    """Retarget a Source character into Avg_Dude UE2 RefPose coordinates & skinning."""
    ch = source_loader.load_source_character(vpk_path, mdl_rel_path)
    dst_world = compute_ue2_bone_world(template)
    dst_name_to_idx = {b[0].lower(): i for i, b in enumerate(template.bones)}

    src_name_to_idx = {b.name: i for i, b in enumerate(ch.bones)}
    used_parts = [p for p in ch.parts if p.material_name not in skip_mats and len(p.triangles) > 0]
    used_vi = set()
    for p in used_parts:
        for i0, i1, i2 in p.triangles:
            used_vi.update((i0, i1, i2))

    # Source bone world positions in flipY space: (x, -y, z)
    z_min_src = min(ch.vertices[vi].pos[2] for vi in used_vi)
    raw_src_flip: List[Vec3] = [
        (m[3], -m[7], m[11]) for m in ch.bone_world_mats
    ]

    def rsf(name: str) -> Vec3:
        return raw_src_flip[src_name_to_idx[name]]

    # Center Y around midpoint of thighs & upper arms, keep X=0 symmetric, rest feet on Z=0
    y_center = 0.5 * (
        rsf("ValveBiped.Bip01_L_Thigh")[1] + rsf("ValveBiped.Bip01_L_UpperArm")[1]
    )
    # Match leg scale cleanly so Foot->Thigh matches Avg_Dude (and overall height ~153..157)
    d_leg_src = rsf("ValveBiped.Bip01_L_Thigh")[2] - rsf("ValveBiped.Bip01_L_Foot")[2]
    d_leg_dst = dst_world["MALE01 L Thigh"][2] - dst_world["MALE01 L Foot"][2]
    pre_scale = d_leg_dst / d_leg_src

    def to_pre(p_flip: Vec3) -> Vec3:
        return (
            p_flip[0] * pre_scale,
            (p_flip[1] - y_center) * pre_scale,
            (p_flip[2] - z_min_src) * pre_scale,
        )

    pre_src: List[Vec3] = [to_pre(p) for p in raw_src_flip]

    def ps(name: str) -> Vec3:
        return pre_src[src_name_to_idx[name]]

    def pd(name: str) -> Vec3:
        return dst_world[name]

    # Build piecewise C0-continuous affine transforms (M_b, t_b) in pre_src space
    bone_xforms: Dict[int, Tuple[Mat3, Vec3]] = {}

    # 1. Torso spine (Pelvis -> Neck1 mapped smoothly to Avg_Dude Pelvis -> Neck)
    M_torso, t_torso = _seg_transform(
        ps("ValveBiped.Bip01_Pelvis"),
        ps("ValveBiped.Bip01_Neck1"),
        pd("MALE01 pelvis"),
        pd("MALE01 neck"),
        stretch_axis=True,
    )
    for bname in (
        "ValveBiped.Bip01_Pelvis",
        "ValveBiped.Bip01_Spine",
        "ValveBiped.Bip01_Spine1",
        "ValveBiped.Bip01_Spine2",
        "ValveBiped.Bip01_Spine4",
    ):
        if bname in src_name_to_idx:
            bone_xforms[src_name_to_idx[bname]] = (M_torso, t_torso)

    # 2. Neck & Head stay purely rigid (uniform pre_scale, ZERO distortion on face/hair)
    neck_dst_anchor = _apply_affine(M_torso, t_torso, ps("ValveBiped.Bip01_Neck1"))
    t_head = _vsub(neck_dst_anchor, ps("ValveBiped.Bip01_Neck1"))
    for bname in ("ValveBiped.Bip01_Neck1", "ValveBiped.Bip01_Head1"):
        bone_xforms[src_name_to_idx[bname]] = (_eye3(), t_head)

    # 3. Legs (connected seamlessly from Pelvis/Thigh -> Calf -> Foot, Shoes unstretched!)
    th_xforms: Dict[str, Tuple[Mat3, Vec3]] = {}
    for side_s, calf_d, foot_d, thigh_d in (
        ("L", "MALE01 L Calf", "MALE01 L Foot", "MALE01 L Thigh"),
        ("R", "MALE01 r calf", "MALE01 r foot", "MALE01 R Thigh"),
    ):
        s_th = ps(f"ValveBiped.Bip01_{side_s}_Thigh")
        s_ca = ps(f"ValveBiped.Bip01_{side_s}_Calf")
        s_ft = ps(f"ValveBiped.Bip01_{side_s}_Foot")
        d_th = pd(thigh_d)
        d_ca = pd(calf_d)
        # Keep shoe soles resting flat near Z=0
        d_ft = (pd(foot_d)[0], pd(foot_d)[1], s_ft[2])

        M_th, t_th = _seg_transform(s_th, s_ca, d_th, d_ca, stretch_axis=True)
        M_ca, t_ca = _seg_transform(s_ca, s_ft, d_ca, d_ft, stretch_axis=True)
        # Rigid rotation only on Foot so shoes never squash vertically
        M_ft, _ = _seg_transform(s_ca, s_ft, d_ca, d_ft, stretch_axis=False)
        t_ft = _vsub(d_ft, _mat3_vec(M_ft, s_ft))

        th_xforms[side_s] = (M_th, t_th)
        bone_xforms[src_name_to_idx[f"ValveBiped.Bip01_{side_s}_Thigh"]] = (M_th, t_th)
        bone_xforms[src_name_to_idx[f"ValveBiped.Bip01_{side_s}_Calf"]] = (M_ca, t_ca)
        bone_xforms[src_name_to_idx[f"ValveBiped.Bip01_{side_s}_Foot"]] = (M_ft, t_ft)

    # 4. Arms (Clavicle -> UpperArm -> Forearm -> Hand -> Fingers)
    for side_s, clav_d, ua_d, fa_d, hd_d, f2_d in (
        (
            "L",
            "MALE01 L Clavicle",
            "MALE01 L UpperArm",
            "MALE01 L Forearm",
            "MALE01 L Hand",
            "MALE01 L Finger2",
        ),
        (
            "R",
            "MALE01 R Clavicle",
            "MALE01 R UpperArm",
            "MALE01 R Forearm",
            "MALE01 r hand",
            "MALE01 R Finger2",
        ),
    ):
        s_cl = ps(f"ValveBiped.Bip01_{side_s}_Clavicle")
        s_ua = ps(f"ValveBiped.Bip01_{side_s}_UpperArm")
        s_fa = ps(f"ValveBiped.Bip01_{side_s}_Forearm")
        s_hd = ps(f"ValveBiped.Bip01_{side_s}_Hand")
        s_f2 = ps(f"ValveBiped.Bip01_{side_s}_Finger2")

        cl_anchor = _apply_affine(M_torso, t_torso, s_cl)
        d_ua = pd(ua_d)
        d_fa = pd(fa_d)
        d_hd = pd(hd_d)
        d_f2 = pd(f2_d)

        M_cl, t_cl = _seg_transform(s_cl, s_ua, cl_anchor, d_ua, stretch_axis=True)
        M_ua, t_ua = _seg_transform(s_ua, s_fa, d_ua, d_fa, stretch_axis=True)
        M_fa, t_fa = _seg_transform(s_fa, s_hd, d_fa, d_hd, stretch_axis=True)

        # Fingers & Hand: match Avg_Dude knuckle direction & gentle uniform hand scale
        hand_scale = _vlen(_vsub(d_f2, d_hd)) / _vlen(_vsub(s_f2, s_hd))
        R_hand = _rot_vec_to_vec(_vsub(s_f2, s_hd), _vsub(d_f2, d_hd))
        M_hd = [[R_hand[r][c] * hand_scale for c in range(3)] for r in range(3)]
        t_hd = _vsub(d_hd, _mat3_vec(M_hd, s_hd))

        for bn in (f"ValveBiped.Bip01_{side_s}_Clavicle",):
            bone_xforms[src_name_to_idx[bn]] = (M_cl, t_cl)
        for bn in (f"ValveBiped.Bip01_{side_s}_UpperArm",):
            bone_xforms[src_name_to_idx[bn]] = (M_ua, t_ua)
        for bn in (
            f"ValveBiped.Bip01_{side_s}_Forearm",
            f"ValveBiped.Bip01_{side_s}_Ulna",
            f"ValveBiped.Bip01_{side_s}_Wrist",
        ):
            if bn in src_name_to_idx:
                bone_xforms[src_name_to_idx[bn]] = (M_fa, t_fa)
        bone_xforms[src_name_to_idx[f"ValveBiped.Bip01_{side_s}_Hand"]] = (M_hd, t_hd)
        for fnum in (0, 1, 2, 3, 4):
            for fsuf in ("", "1", "2"):
                fbn = f"ValveBiped.Bip01_{side_s}_Finger{fnum}{fsuf}"
                if fbn in src_name_to_idx:
                    bone_xforms[src_name_to_idx[fbn]] = (M_hd, t_hd)

    # Resolve parent transform + UE2 bone index for every Source bone (including hair/skirt)
    src_to_dst_bi: List[int] = [1] * len(ch.bones)
    src_xforms: List[Tuple[Mat3, Vec3, Mat3]] = []
    pelvis_dst_bi = dst_name_to_idx["male01 pelvis"]
    spine2_dst_bi = dst_name_to_idx["male01 spine2"]
    l_thigh_dst_bi = dst_name_to_idx["male01 l thigh"]
    r_thigh_dst_bi = dst_name_to_idx["male01 r thigh"]
    jiggle_l_bi = dst_name_to_idx.get("jiggle_l")
    jiggle_r_bi = dst_name_to_idx.get("jiggle_r")

    def _pectoral_factor(sv_pos: Vec3) -> float:
        if mesh_name not in ("Doki_Yuri", "Doki_Monika"):
            return 0.0
        sx, sy_raw, sz = sv_pos
        y_front = -sy_raw
        if y_front <= 0.6 or sz < 47.5 or sz > 56.2 or abs(sx) > 4.6:
            return 0.0
        z_c = 51.8 if mesh_name == "Doki_Yuri" else 52.2
        fy = _smoothstep(0.6, 2.3, y_front) * (1.0 - 0.20 * _smoothstep(4.8, 7.2, y_front))
        r2_l = ((sx - 1.65) / 2.15) ** 2 + ((sz - z_c) / 2.85) ** 2
        r2_r = ((sx + 1.65) / 2.15) ** 2 + ((sz - z_c) / 2.85) ** 2
        lobe_l = max(0.0, 1.0 - r2_l) ** 2
        lobe_r = max(0.0, 1.0 - r2_r) ** 2
        return fy * min(1.0, lobe_l + lobe_r)

    skirt_vis = [
        vi
        for part in used_parts
        if "skirt" in part.material_name.lower()
        for tri in part.triangles
        for vi in tri
    ]
    if skirt_vis:
        skirt_z_min = min(ch.vertices[vi].pos[2] for vi in skirt_vis)
        skirt_z_max = max(ch.vertices[vi].pos[2] for vi in skirt_vis)
        skirt_h = max(1.0, skirt_z_max - skirt_z_min)
    else:
        skirt_z_max, skirt_h = 0.0, 1.0

    d_l_th, d_l_ca = pd("MALE01 L Thigh"), pd("MALE01 L Calf")
    d_r_th, d_r_ca = pd("MALE01 R Thigh"), pd("MALE01 r calf")
    d_pel = pd("MALE01 pelvis")
    M_th_L, t_th_L = th_xforms["L"]
    M_th_R, t_th_R = th_xforms["R"]
    invT_torso = _mat3_T(_mat3_inv(M_torso))
    invT_th_L = _mat3_T(_mat3_inv(M_th_L))
    invT_th_R = _mat3_T(_mat3_inv(M_th_R))

    for bi, b in enumerate(ch.bones):
        cur = bi
        dst_bi = None
        xf = None
        visited = set()
        while cur >= 0 and cur not in visited:
            visited.add(cur)
            cname = ch.bones[cur].name
            if dst_bi is None and cname in SOURCE_TO_UE2_BONE:
                dst_bi = dst_name_to_idx[SOURCE_TO_UE2_BONE[cname].lower()]
            if xf is None and cur in bone_xforms:
                xf = bone_xforms[cur]
            if dst_bi is not None and xf is not None:
                break
            cur = ch.bones[cur].parent
        if dst_bi is None:
            dst_bi = pelvis_dst_bi
        if xf is None:
            xf = (M_torso, t_torso)
        M_b, t_b = xf
        src_to_dst_bi[bi] = dst_bi
        src_xforms.append((M_b, t_b, _mat3_T(_mat3_inv(M_b))))

    def map_vertex_weights(
        sv: source_loader.SourceVertex,
        p_out: Vec3,
        is_skirt: bool,
    ) -> Tuple[Tuple[int, float], ...]:
        if is_skirt:
            # Blend smoothly from 100% pelvis at waistband to 86% left/right thigh toward hem
            # so walking, running, and crouching swing skirt panels naturally with both thighs.
            s_t = max(0.0, min(1.0, (skirt_z_max - sv.pos[2]) / skirt_h))
            blend_w = _smoothstep(0.14, 0.84, s_t)
            if blend_w <= 0.005:
                return ((pelvis_dst_bi, 1.0),)
            leg_share = 0.86 * blend_w
            w_pel = 1.0 - leg_share
            lr_u = _smoothstep(-3.6, 3.6, p_out[0])
            w_l = leg_share * lr_u
            w_r = leg_share * (1.0 - lr_u)
            pairs = [(db, wt) for db, wt in ((pelvis_dst_bi, w_pel), (l_thigh_dst_bi, w_l), (r_thigh_dst_bi, w_r)) if wt > 0.005]
            tot = sum(wt for _, wt in pairs) or 1.0
            return tuple((db, round(wt / tot, 6)) for db, wt in pairs)

        acc: Dict[int, float] = {}
        for bi, w in sv.weights:
            if w <= 0.0:
                continue
            db = src_to_dst_bi[bi]
            acc[db] = acc.get(db, 0.0) + w
        if not acc:
            return ((pelvis_dst_bi, 1.0),)
        if jiggle_l_bi is not None and jiggle_r_bi is not None and acc.get(spine2_dst_bi, 0.0) > 0.15:
            f_pec = _pectoral_factor(sv.pos)
            if f_pec > 0.02:
                w_sp2 = acc[spine2_dst_bi]
                j_share = min(0.68, 0.72 * f_pec) * w_sp2
                lr_j = _smoothstep(-1.2, 1.2, sv.pos[0])
                acc[spine2_dst_bi] = max(0.0, w_sp2 - j_share)
                acc[jiggle_l_bi] = acc.get(jiggle_l_bi, 0.0) + j_share * lr_j
                acc[jiggle_r_bi] = acc.get(jiggle_r_bi, 0.0) + j_share * (1.0 - lr_j)
        top4 = sorted((kv for kv in acc.items() if kv[1] > 0.004), key=lambda kv: (-kv[1], kv[0]))[:4]
        tot = sum(w for _, w in top4) or 1.0
        return tuple((db, round(w / tot, 6)) for db, w in top4)

    def xform_vertex(sv: source_loader.SourceVertex, is_skirt: bool) -> Tuple[Vec3, Vec3]:
        sx, sy_raw, sz = sv.pos
        nx_f, ny_f, nz_f = sv.normal[0], -sv.normal[1], sv.normal[2]
        y_front = -sy_raw
        if not is_skirt:
            f_pec = _pectoral_factor(sv.pos)
            if f_pec > 1e-4:
                amp_y = 1.45 if mesh_name == "Doki_Yuri" else 1.15
                z_c = 51.8 if mesh_name == "Doki_Yuri" else 52.2
                y_front += amp_y * f_pec
                sz += 0.18 * f_pec * ((sz - z_c) / 2.85)
                sx += 0.16 * f_pec * (1.0 if sx >= 0.0 else -1.0) * _smoothstep(0.3, 1.8, abs(sx))
                ny_f += 0.28 * f_pec
                nz_f += 0.12 * f_pec * ((sz - z_c) / 2.85)
        p_pre = to_pre((sx, y_front, sz))
        n_flip = _vunit((nx_f, ny_f, nz_f))
        if is_skirt:
            # 1. Eliminate torso-vs-thigh RefPose pitch shear smoothly below the waistband
            s_t = max(0.0, min(1.0, (skirt_z_max - sv.pos[2]) / skirt_h))
            lr_s = _smoothstep(-3.0, 3.0, sv.pos[0])
            p_tor = _apply_affine(M_torso, t_torso, p_pre)
            p_leg_l = _apply_affine(M_th_L, t_th_L, p_pre)
            p_leg_r = _apply_affine(M_th_R, t_th_R, p_pre)
            p_leg = _vadd(_vscale(p_leg_l, lr_s), _vscale(p_leg_r, 1.0 - lr_s))
            align_w = 0.90 * _smoothstep(0.10, 0.62, s_t)
            px, py, pz = _vadd(_vscale(p_tor, 1.0 - align_w), _vscale(p_leg, align_w))

            n_tor = _mat3_vec(invT_torso, n_flip)
            n_leg = _vadd(
                _vscale(_mat3_vec(invT_th_L, n_flip), lr_s),
                _vscale(_mat3_vec(invT_th_R, n_flip), 1.0 - lr_s),
            )
            nx, ny, nz = _vadd(_vscale(n_tor, 1.0 - align_w), _vscale(n_leg, align_w))

            # 2. Gentle A-line hem flare & guaranteed UE2 thigh capsule clearance
            hem_flare = (0.8 + 2.8 * _smoothstep(0.18, 1.0, s_t))
            cx_hip = max(-d_l_th[0], min(d_l_th[0], px * 0.45))
            # Track leg axis Y slope smoothly down from pelvis (Y=0.48) toward thigh pitch
            t_below = max(0.0, (d_pel[2] - pz) / max(1.0, d_l_th[2] - d_l_ca[2]))
            cy_hip = d_pel[1] + (d_l_ca[1] - d_l_th[1]) * t_below * 0.85
            rx, ry = px - cx_hip, py - cy_hip
            rlen = math.hypot(rx, ry)
            if rlen > 1e-4:
                px += (rx / rlen) * hem_flare * _smoothstep(0.12, 0.45, s_t)
                py += (ry / rlen) * hem_flare * _smoothstep(0.12, 0.45, s_t)

            clear_mask = _smoothstep(0.14, 0.42, s_t)
            if clear_mask > 1e-4:
                r_guard_top = 8.4
                r_guard_hem = 10.2
                r_band = r_guard_top + (r_guard_hem - r_guard_top) * _smoothstep(0.18, 0.65, s_t)
                for th_a, th_b in ((d_l_th, d_l_ca), (d_r_th, d_r_ca)):
                    dist, seg_t, q = _closest_on_seg((px, py, pz), th_a, th_b)
                    if 0.04 <= seg_t <= 0.85:
                        r_min = r_band - 0.8 * seg_t
                        if dist < r_min and dist > 1e-4:
                            push = (r_min - dist) * clear_mask
                            ox, oy, oz = (px - q[0]) / dist, (py - q[1]) / dist, (pz - q[2]) / dist
                            px += ox * push
                            py += oy * push
                            pz += oz * push
                            nx += ox * 0.25 * clear_mask
                            ny += oy * 0.25 * clear_mask
                            nz += oz * 0.25 * clear_mask

            return (px, py, pz), _vunit((nx, ny, nz))

        px = py = pz = 0.0
        nx = ny = nz = 0.0
        w_sum = 0.0
        for bi, w in sv.weights:
            if w <= 0.0:
                continue
            M_b, t_b, invT_b = src_xforms[bi]
            tp = _apply_affine(M_b, t_b, p_pre)
            tn = _mat3_vec(invT_b, n_flip)
            px += w * tp[0]
            py += w * tp[1]
            pz += w * tp[2]
            nx += w * tn[0]
            ny += w * tn[1]
            nz += w * tn[2]
            w_sum += w
        if w_sum <= 1e-6:
            tp = _apply_affine(M_torso, t_torso, p_pre)
            return tp, _vunit(n_flip)
        inv = 1.0 / w_sum
        return (px * inv, py * inv, pz * inv), _vunit((nx * inv, ny * inv, nz * inv))

    # Material slot 0 = Doki_NullTex dummy triangle protection against Skins[0] / BodySkin overrides
    mat_names: List[str] = ["__NULL__"]
    tmp_pts: List[Vec3] = []
    tmp_norms: List[Vec3] = []
    tmp_wts: List[Tuple[Tuple[int, float], ...]] = []
    pt_map: Dict[Tuple, int] = {}

    tmp_wdgs: List[Tuple[int, float, float]] = []
    wdg_map: Dict[Tuple, int] = {}
    tmp_fcs: List[Tuple[int, int, int, int]] = []

    # Slot-0 sub-pixel dummy triangle buried inside pelvis
    pel_pos = pd("MALE01 pelvis")
    for k, dp in enumerate(((0.0, 0.0, 0.0), (0.001, 0.0, 0.0), (0.0, 0.001, 0.0))):
        pi = len(tmp_pts)
        tmp_pts.append(_vadd(pel_pos, dp))
        tmp_norms.append((0.0, 0.0, 1.0))
        tmp_wts.append(((pelvis_dst_bi, 1.0),))
        tmp_wdgs.append((pi, 0.5, 0.5))
    tmp_fcs.append((0, 1, 2, 0))

    raw_cache: Dict[Tuple[int, bool], Tuple[int, int]] = {}
    for part in used_parts:
        mat_idx = len(mat_names)
        mat_names.append(part.material_name)
        is_skirt = "skirt" in part.material_name.lower()
        for i0, i1, i2 in part.triangles:
            w_tri = []
            # Swap (i1, i2) to preserve CW winding dot((p1-p0)x(p2-p0), n) < 0 after flipY
            for rvi in (i0, i2, i1):
                ckey = (rvi, is_skirt)
                cached = raw_cache.get(ckey)
                if cached is None:
                    sv = ch.vertices[rvi]
                    p_out, n_out = xform_vertex(sv, is_skirt)
                    wts = map_vertex_weights(sv, p_out, is_skirt)
                    pkey = (
                        is_skirt,
                        round(sv.pos[0], 4),
                        round(sv.pos[1], 4),
                        round(sv.pos[2], 4),
                        tuple((db, round(wt, 3)) for db, wt in wts),
                    )
                    pi = pt_map.get(pkey)
                    if pi is None:
                        pi = len(tmp_pts)
                        pt_map[pkey] = pi
                        tmp_pts.append(p_out)
                        tmp_norms.append(n_out)
                        tmp_wts.append(wts)
                    wkey = (pi, round(sv.uv[0], 5), round(sv.uv[1], 5))
                    wi = wdg_map.get(wkey)
                    if wi is None:
                        wi = len(tmp_wdgs)
                        wdg_map[wkey] = wi
                        tmp_wdgs.append((pi, sv.uv[0], sv.uv[1]))
                    raw_cache[ckey] = (pi, wi)
                    w_tri.append(wi)
                else:
                    w_tri.append(cached[1])
            tmp_fcs.append((w_tri[0], w_tri[1], w_tri[2], mat_idx))

    # Reorder points and wedges in strict first-appearance order grouped by material index
    tmp_fcs.sort(key=lambda f: f[3])
    old_w_to_new: Dict[int, int] = {}
    old_p_to_new: Dict[int, int] = {}

    final_pts: List[Vec3] = []
    final_norms: List[Vec3] = []
    final_infs: List[Tuple[float, int, int]] = []
    final_wdgs: List[Tuple[int, float, float]] = []
    final_fcs: List[Tuple[int, int, int, int]] = []

    for w0, w1, w2, mat in tmp_fcs:
        nw = []
        for ow in (w0, w1, w2):
            nwi = old_w_to_new.get(ow)
            if nwi is None:
                op, fu, fv = tmp_wdgs[ow]
                npi = old_p_to_new.get(op)
                if npi is None:
                    npi = len(final_pts)
                    old_p_to_new[op] = npi
                    final_pts.append(tmp_pts[op])
                    final_norms.append(tmp_norms[op])
                    for db, wt in tmp_wts[op]:
                        final_infs.append((wt, npi, db))
                nwi = len(final_wdgs)
                old_w_to_new[ow] = nwi
                final_wdgs.append((npi, fu, fv))
            nw.append(nwi)
        final_fcs.append((nw[0], nw[1], nw[2], mat))

    return final_pts, final_norms, final_wdgs, final_fcs, final_infs, mat_names


def build_null_head_geometry() -> Tuple[
    List[Vec3],
    List[Vec3],
    List[Tuple[int, float, float]],
    List[Tuple[int, int, int, int]],
    List[Tuple[float, int, int]],
]:
    """Build an invisible 1-triangle dummy head mesh (for Doki_NullTex)."""
    pts = [(0.0, 0.0, 0.0), (0.001, 0.0, 0.0), (0.0, 0.001, 0.0)]
    norms = [(0.0, 0.0, 1.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0)]
    wdgs = [(0, 0.5, 0.5), (1, 0.5, 0.5), (2, 0.5, 0.5)]
    fcs = [(0, 1, 2, 0)]
    infs = [(1.0, 0, 0), (1.0, 1, 0), (1.0, 2, 0)]
    return pts, norms, wdgs, fcs, infs


def inject_dokis_into_characters(
    in_ukx_path: str,
    out_ukx_path: str,
    mat_map: Dict[str, Dict[str, str]],
) -> None:
    """Append Doki_* SkeletalMeshes and Doki_YuriAnim to a Characters.ukx package."""
    pkg = ue2_io.UE2Package.load(in_ukx_path)
    tmpl = ue2_io.extract_skel_template(pkg, "Avg_Dude")
    # Add secondary inertia child bones (jiggle_L, jiggle_R) parented to MALE01 spine2 (bone 4)
    # at the end of RefSkeleton so original bone indices 0..55 remain 100% intact for animAvg.
    sp2_name, sp2_flags, sp2_quat, sp2_pos, sp2_misc, sp2_nchild, sp2_parent = tmpl.bones[4]
    tmpl.bones[4] = (sp2_name, sp2_flags, sp2_quat, sp2_pos, sp2_misc, sp2_nchild + 2, sp2_parent)
    ident_q = (0.0, 0.0, 0.0, -1.0)
    tmpl.bones.append(("jiggle_L", 0, ident_q, (14.0, 3.2, 3.8), (0.0, 0.0, 0.0, 0.0), 0, 4))
    tmpl.bones.append(("jiggle_R", 0, ident_q, (14.0, -3.2, 3.8), (0.0, 0.0, 0.0, 0.0), 0, 4))
    avg_anim_data = ue2_io.extract_mesh_anim_data(pkg, "animAvg")

    eng_pkg = pkg.ensure_import("Core", "Package", 0, "Engine")
    cls_sm = pkg.ensure_import("Core", "Class", eng_pkg, "SkeletalMesh")
    cls_ma = pkg.ensure_import("Core", "Class", eng_pkg, "MeshAnimation")
    doki_pkg = pkg.ensure_import("Core", "Package", 0, "DokiSkins")
    null_tex_ref = pkg.ensure_import("Engine", "Texture", doki_pkg, "Doki_NullTex")

    if pkg.find_export_ci("Doki_YuriAnim") is not None:
        raise RuntimeError(f"Doki_YuriAnim already exists in {in_ukx_path}")
    yuri_anim_ref = pkg.add_export_builder(
        cls_ma,
        0,
        0,
        "Doki_YuriAnim",
        0x000F0004,
        lambda _off: ue2_io.build_cloned_mesh_anim_payload(
            pkg, avg_anim_data, YURI_DOG_ANIM_MAP
        ),
    )

    for mesh_name, grp_name, vpk_path, mdl_path, skip_mats in DOKI_SPECS:
        if pkg.find_export_ci(mesh_name) is not None:
            raise RuntimeError(f"{mesh_name} already exists in {in_ukx_path}")
        grp_ref = pkg.ensure_import("Core", "Package", doki_pkg, grp_name)
        pts, norms, wdgs, fcs, infs, mat_names = retarget_source_character(
            tmpl, vpk_path, mdl_path, skip_mats, mesh_name=mesh_name
        )
        tex_refs = [null_tex_ref]
        for mn in mat_names[1:]:
            clean_mn = mat_map[mesh_name][mn]
            tex_refs.append(pkg.ensure_import("Engine", "Shader", grp_ref, clean_mn))
        # All 4 Dokis use human animAvg (`default_anim_ref=None`) so CoverMyAss PartnerPawns
        # and Player pawns get full human animations; Doki_YuriDog uses Doki_YuriAnim for DogLover.
        emit_variants = (
            [(mesh_name, None), ("Doki_YuriDog", yuri_anim_ref)]
            if mesh_name == "Doki_Yuri"
            else [(mesh_name, None)]
        )
        for out_mesh_name, anim_ref in emit_variants:
            if out_mesh_name != mesh_name and pkg.find_export_ci(out_mesh_name) is not None:
                raise RuntimeError(f"{out_mesh_name} already exists in {in_ukx_path}")
            pkg.add_export_builder(
                cls_sm,
                0,
                0,
                out_mesh_name,
                ue2_io.RF_DEFAULT_OBJ,
                lambda off, tr=tex_refs, p=pts, n=norms, w=wdgs, f=fcs, inf=infs, dar=anim_ref: ue2_io.build_skeletal_mesh_payload(
                    pkg,
                    off,
                    tmpl,
                    tr,
                    p,
                    n,
                    w,
                    f,
                    inf,
                    default_anim_ref=dar,
                    origin=(0.0, 0.0, 75.0),
                ),
            )
    pkg.save(out_ukx_path)


def inject_null_head(in_ukx_path: str, out_ukx_path: str, template_head_name: str) -> None:
    """Append Doki_NullHead into a heads/MoreHeads .ukx package."""
    pkg = ue2_io.UE2Package.load(in_ukx_path)
    if pkg.find_export_ci("Doki_NullHead") is not None:
        raise RuntimeError(f"Doki_NullHead already exists in {in_ukx_path}")
    tmpl = ue2_io.extract_skel_template(pkg, template_head_name)
    eng_pkg = pkg.ensure_import("Core", "Package", 0, "Engine")
    cls_sm = pkg.ensure_import("Core", "Class", eng_pkg, "SkeletalMesh")
    doki_pkg = pkg.ensure_import("Core", "Package", 0, "DokiSkins")
    null_tex_ref = pkg.ensure_import("Engine", "Texture", doki_pkg, "Doki_NullTex")

    pts, norms, wdgs, fcs, infs = build_null_head_geometry()
    pkg.add_export_builder(
        cls_sm,
        0,
        0,
        "Doki_NullHead",
        ue2_io.RF_DEFAULT_OBJ,
        lambda off: ue2_io.build_skeletal_mesh_payload(
            pkg, off, tmpl, [null_tex_ref], pts, norms, wdgs, fcs, infs
        ),
    )
    pkg.save(out_ukx_path)


def verify_skeletal_mesh_export(pkg_path: str, mesh_name: str) -> None:
    """Reload pkg_path and verify export binary framing, skinning stream, and geometry sanity."""
    pkg = ue2_io.UE2Package.load(pkg_path)
    ei = pkg.find_export_ci(mesh_name)
    assert ei is not None, (pkg_path, mesh_name)
    ex = pkg.exports[ei - 1]
    buf = pkg.raw[ex.serial_offset : ex.serial_offset + ex.serial_size]

    p = 0
    while True:
        ni, p = ue2_io.read_ci(buf, p)
        if pkg.names[ni][0] == "None":
            break
    p += 49
    nv, p = ue2_io.read_ci(buf, p)
    p += nv * 4
    nt, p = ue2_io.read_ci(buf, p)
    trefs = []
    for _ in range(nt):
        tr, p = ue2_io.read_ci(buf, p)
        trefs.append(tr)
    p += 36
    for sz in (2, 8, 2, 10, 8):
        n, p = ue2_io.read_ci(buf, p)
        p += n * sz
    p += 24
    np2, p = ue2_io.read_ci(buf, p)
    p += np2 * 12
    nb, p = ue2_io.read_ci(buf, p)
    for _ in range(nb):
        _, p = ue2_io.read_ci(buf, p)
        p += 56
    _, p = ue2_io.read_ci(buf, p)
    p += 4
    for _ in range(2):
        n, p = ue2_io.read_ci(buf, p)
        p += n * 4
    for _ in range(2):
        n, p = ue2_io.read_ci(buf, p)
        for _ in range(n):
            _, p = ue2_io.read_ci(buf, p)
    n_ac, p = ue2_io.read_ci(buf, p)
    p += n_ac * 48
    nlods, p = ue2_io.read_ci(buf, p)
    assert nlods == 1
    nsd, p = ue2_io.read_ci(buf, p)
    p += nsd * 4
    nsp, p = ue2_io.read_ci(buf, p)
    sp = [struct.unpack_from("<3fI", buf, p + i * 16) for i in range(nsp)]
    p += nsp * 16 + 4
    nsec, p = ue2_io.read_ci(buf, p)
    p += nsec * 18
    nssec, p = ue2_io.read_ci(buf, p)
    p += nssec * 18
    nib, p = ue2_io.read_ci(buf, p)
    p += nib * 2 + 4
    nsib, p = ue2_io.read_ci(buf, p)
    p += nsib * 2 + 4
    p += 12
    nav, p = ue2_io.read_ci(buf, p)
    p += nav * 16

    def rlazy(fmt: str):
        nonlocal p
        skip = struct.unpack_from("<I", buf, p)[0]
        p += 4
        cnt, p = ue2_io.read_ci(buf, p)
        sz = struct.calcsize(fmt)
        items = [struct.unpack_from(fmt, buf, p + i * sz) for i in range(cnt)]
        p += cnt * sz
        assert ex.serial_offset + p == skip
        return items

    infs = rlazy("<fHH")
    wdgs = rlazy("<Hff")
    fcs = rlazy("<4H")
    pts = rlazy("<3f")
    p += 24
    _, p = ue2_io.read_ci(buf, p)
    for _ in range(6):
        skip = struct.unpack_from("<I", buf, p)[0]
        p += 4
        cnt, p = ue2_io.read_ci(buf, p)
        p = skip - ex.serial_offset
    assert p == len(buf), f"{mesh_name}: END_DIFF={len(buf) - p}"

    ue2_io.create_skinning_stream(len(pts), wdgs, fcs, infs, nb)
    assert pkg.obj_name(trefs[0]) == "Doki_NullTex"
    assert all(0 <= bi < nb and math.isfinite(w) and w > 0.0 for w, _vi, bi in infs)
    assert all(math.isfinite(c) for pt in pts for c in pt)

    xs = [pt[0] for pt in pts]
    ys = [pt[1] for pt in pts]
    zs = [pt[2] for pt in pts]

    neg_dot = pos_dot = 0
    for w0, w1, w2, m in fcs[1:]:
        p0, p1, p2 = pts[wdgs[w0][0]], pts[wdgs[w1][0]], pts[wdgs[w2][0]]
        cx, cy, cz = _vcross(_vsub(p1, p0), _vsub(p2, p0))
        u = sp[wdgs[w0][0]][3]
        nx = (u & 0x3FF) - 511
        ny = ((u >> 10) & 0x3FF) - 511
        nz = ((u >> 20) & 0x3FF) - 511
        if cx * nx + cy * ny + cz * nz < 0:
            neg_dot += 1
        else:
            pos_dot += 1

    print(
        f"VERIFIED {os.path.basename(pkg_path)}::{mesh_name}: "
        f"END_DIFF=0 pts={len(pts)} wdgs={len(wdgs)} fcs={len(fcs)} infs={len(infs)} mats={len(trefs)} "
        f"X=[{min(xs):.1f},{max(xs):.1f}] Y=[{min(ys):.1f},{max(ys):.1f}] Z=[{min(zs):.1f},{max(zs):.1f}] "
        f"winding_neg={neg_dot}/{neg_dot + pos_dot}"
    )


def main() -> None:
    out_dir = os.path.join(_SCRIPT_DIR, "out")
    os.makedirs(out_dir, exist_ok=True)

    utx_path = os.path.join(out_dir, "DokiSkins.utx")
    mat_map = build_doki_textures(utx_path)
    r_utx = ue2_io.UE2Package.load(utx_path)
    print(f"Built DokiSkins.utx: exports={len(r_utx.exports)} size={os.path.getsize(utx_path)}")

    chars_out = os.path.join(out_dir, "Characters.ukx")
    inject_dokis_into_characters(
        os.path.join(P2_ROOT, "Animations/Characters.ukx"), chars_out, mat_map
    )
    for mname, *_ in DOKI_SPECS:
        verify_skeletal_mesh_export(chars_out, mname)
    verify_skeletal_mesh_export(chars_out, "Doki_YuriDog")

    mh_out = os.path.join(out_dir, "MoreHeads.ukx")
    inject_null_head(os.path.join(P2_ROOT, "Animations/MoreHeads.ukx"), mh_out, "AW_Dude")
    verify_skeletal_mesh_export(mh_out, "Doki_NullHead")

    hd_out = os.path.join(out_dir, "heads.ukx")
    inject_null_head(os.path.join(P2_ROOT, "Animations/heads.ukx"), hd_out, "AvgDude")
    verify_skeletal_mesh_export(hd_out, "Doki_NullHead")


if __name__ == "__main__":
    main()

