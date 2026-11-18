"""Source Engine VPK + MDL/VVD/DX90.VTX + VMT/VTF loader for L4D2 Workshop models."""
from __future__ import annotations
import os
import posixpath
import re
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


class VPKArchive:
    """Read-only Source VPK (v1 and v2) archive reader."""

    def __init__(self, vpk_path: str):
        self.vpk_path = vpk_path
        with open(vpk_path, "rb") as f:
            self._data = f.read()
        sig, ver, tree_sz = struct.unpack_from("<III", self._data, 0)
        assert sig == 0x55AA1234, f"Bad VPK sig in {vpk_path}: {sig:#x}"
        if ver == 1:
            hdr_sz = 12
        elif ver == 2:
            hdr_sz = 28
        else:
            raise ValueError(f"Unsupported VPK version {ver} in {vpk_path}")
        self.data_offset = hdr_sz + tree_sz
        self.entries: Dict[str, Tuple[int, int, int, bytes]] = {}
        pos = hdr_sz
        end = hdr_sz + tree_sz
        while pos < end:
            ext, pos = self._read_cstr(pos)
            if ext == "":
                break
            while True:
                path, pos = self._read_cstr(pos)
                if path == "":
                    break
                while True:
                    fname, pos = self._read_cstr(pos)
                    if fname == "":
                        break
                    crc, preload_sz, arch_idx, entry_off, entry_len, term = struct.unpack_from(
                        "<IHHIIH", self._data, pos
                    )
                    pos += 18
                    assert term == 0xFFFF, f"Bad VPK terminator {term:#x}"
                    preload = self._data[pos : pos + preload_sz]
                    pos += preload_sz
                    rel = (f"{path}/" if path != " " else "") + f"{fname}.{ext}"
                    self.entries[rel.lower()] = (arch_idx, entry_off, entry_len, preload)

    def _read_cstr(self, pos: int) -> Tuple[str, int]:
        z = self._data.index(0, pos)
        return self._data[pos:z].decode("latin-1"), z + 1

    def read_file(self, rel_path: str) -> bytes:
        key = rel_path.replace("\\", "/").lstrip("/").lower()
        if key not in self.entries:
            raise KeyError(f"{rel_path} not found in {self.vpk_path}")
        arch_idx, off, length, preload = self.entries[key]
        if arch_idx == 0x7FFF:
            body = self._data[self.data_offset + off : self.data_offset + off + length]
        else:
            # Multi-part VPK (_000.vpk) if ever needed
            base = self.vpk_path[:-7] if self.vpk_path.endswith("_dir.vpk") else self.vpk_path[:-4]
            part = f"{base}_{arch_idx:03d}.vpk"
            with open(part, "rb") as pf:
                pf.seek(off)
                body = pf.read(length)
        return preload + body

    def find_files(self, suffix: str = "", prefix: str = "") -> List[str]:
        s = suffix.lower()
        p = prefix.lower()
        return sorted(k for k in self.entries if k.startswith(p) and k.endswith(s))


@dataclass
class SourceBone:
    name: str
    parent: int
    pos: Tuple[float, float, float]
    quat: Tuple[float, float, float, float]  # x, y, z, w
    rot: Tuple[float, float, float]
    pose_to_bone: Tuple[float, ...]  # 3x4 row-major floats


@dataclass
class SourceMeshPart:
    material_name: str
    # Each tuple inside triangles holds 3 vertex indices into `vertices`
    triangles: List[Tuple[int, int, int]]


@dataclass
class SourceVertex:
    pos: Tuple[float, float, float]
    normal: Tuple[float, float, float]
    uv: Tuple[float, float]
    # Up to 3 (bone_idx, weight) pairs
    weights: List[Tuple[int, float]]


@dataclass
class SourceTexture:
    name: str
    width: int
    height: int
    vtf_format: int  # 15=DXT5, 13=DXT1, 0=RGBA8, 1=ABGR8, 2=RGB8, 12=BGRA8
    # Mipmaps ordered largest -> smallest (UE2 order!)
    mips_largest_first: List[bytes]
    has_meaningful_alpha: bool


@dataclass
class SourceCharacter:
    mdl_path: str
    bones: List[SourceBone]
    bone_world_mats: List[List[float]]  # 3x4 row-major per bone in bind pose
    vertices: List[SourceVertex]
    parts: List[SourceMeshPart]
    materials: List[str]  # indexed by material_id
    textures: Dict[str, SourceTexture]  # clean name -> SourceTexture


def _mat3x4_mul(a: List[float], b: List[float]) -> List[float]:
    """Multiply two 3x4 row-major affine transforms."""
    return [
        a[0]*b[0] + a[1]*b[4] + a[2]*b[8],
        a[0]*b[1] + a[1]*b[5] + a[2]*b[9],
        a[0]*b[2] + a[1]*b[6] + a[2]*b[10],
        a[0]*b[3] + a[1]*b[7] + a[2]*b[11] + a[3],
        a[4]*b[0] + a[5]*b[4] + a[6]*b[8],
        a[4]*b[1] + a[5]*b[5] + a[6]*b[9],
        a[4]*b[2] + a[5]*b[6] + a[6]*b[10],
        a[4]*b[3] + a[5]*b[7] + a[6]*b[11] + a[7],
        a[8]*b[0] + a[9]*b[4] + a[10]*b[8],
        a[8]*b[1] + a[9]*b[5] + a[10]*b[9],
        a[8]*b[2] + a[9]*b[6] + a[10]*b[10],
        a[8]*b[3] + a[9]*b[7] + a[10]*b[11] + a[11],
    ]


def _quat_pos_to_mat3x4(q: Tuple[float, float, float, float], p: Tuple[float, float, float]) -> List[float]:
    x, y, z, w = q
    xx, yy, zz = x*x, y*y, z*z
    xy, xz, yz = x*y, x*z, y*z
    wx, wy, wz = w*x, w*y, w*z
    return [
        1.0 - 2.0*(yy + zz), 2.0*(xy - wz),       2.0*(xz + wy),       p[0],
        2.0*(xy + wz),       1.0 - 2.0*(xx + zz), 2.0*(yz - wx),       p[1],
        2.0*(xz - wy),       2.0*(yz + wx),       1.0 - 2.0*(xx + yy), p[2],
    ]


def _read_cstr_at(buf: bytes, off: int) -> str:
    z = buf.index(0, off)
    return buf[off:z].decode("latin-1", "replace")


def parse_mdl(mdl: bytes) -> Tuple[List[SourceBone], List[str], List[dict]]:
    sig, ver = struct.unpack_from("<4si", mdl, 0)
    assert sig == b"IDST", f"Bad MDL sig {sig!r}"
    # L4D2 uses MDL ver 48 or 49
    # Header offsets in studiohdr_t:
    # 0x04: version(4)
    # 0x08: checksum(4)
    # 0x0c: name[64]
    # 0x4c: length(4)
    # 0x50..0x98: eyeposition, illum, hull_min/max, view_bbmin/max (6 * 12 = 72 -> ends 0x98)
    # 0x98: flags(4)
    # 0x9c: numbones(4), boneindex(4)
    # 0xa4: numbonecontrollers(4), bonecontrollerindex(4)
    # 0xac: numhitboxsets(4), hitboxsetindex(4)
    # 0xb4: numlocalanim(4), localanimindex(4)
    # 0xbc: numlocalseq(4), localseqindex(4)
    # 0xc4: activitylistversion(4), eventsindexed(4)
    # 0xcc: numtextures(4), textureindex(4)
    # 0xd4: numcdtextures(4), cdtextureindex(4)
    # 0xdc: numskinref(4), numskinfamilies(4), skinindex(4)
    # 0xe8: numbodyparts(4), bodypartindex(4)
    numbones, boneindex = struct.unpack_from("<ii", mdl, 0x9C)
    numtextures, textureindex = struct.unpack_from("<ii", mdl, 0xCC)
    numcdtextures, cdtextureindex = struct.unpack_from("<ii", mdl, 0xD4)
    numskinref, numskinfamilies, skinindex = struct.unpack_from("<iii", mdl, 0xDC)
    numbodyparts, bodypartindex = struct.unpack_from("<ii", mdl, 0xE8)

    bones: List[SourceBone] = []
    # mstudiobone_t stride = 216 bytes
    for bi in range(numbones):
        bo = boneindex + bi * 216
        sznameindex, parent = struct.unpack_from("<ii", mdl, bo)
        bname = _read_cstr_at(mdl, bo + sznameindex)
        # pos at +0x20 (3f), quat at +0x2c (4f), rot at +0x3c (3f),
        # posscale at +0x48 (3f), rotscale at +0x54 (3f), poseToBone at +0x60 (12f)
        pos = struct.unpack_from("<3f", mdl, bo + 0x20)
        quat = struct.unpack_from("<4f", mdl, bo + 0x2C)
        rot = struct.unpack_from("<3f", mdl, bo + 0x3C)
        p2b = struct.unpack_from("<12f", mdl, bo + 0x60)
        bones.append(SourceBone(bname, parent, pos, quat, rot, p2b))

    # Materials + cdtextures
    cd_dirs = []
    for ci in range(numcdtextures):
        str_off = struct.unpack_from("<i", mdl, cdtextureindex + ci * 4)[0]
        cd_dirs.append(_read_cstr_at(mdl, str_off).replace("\\", "/").strip("/"))

    tex_names = []
    # mstudiotexture_t stride = 64 bytes: sznameindex(4) + flags(4) + used(4) + unused(4) + ...
    for ti in range(numtextures):
        to = textureindex + ti * 64
        sz_off = struct.unpack_from("<i", mdl, to)[0]
        tex_names.append(_read_cstr_at(mdl, to + sz_off))

    # Build skin0 table mapping raw material id -> resolved vmt relative path
    skin_ids = struct.unpack_from(f"<{numskinref}h", mdl, skinindex) if numskinref else ()

    # Bodyparts / models / meshes (only first model of each bodypart or active models)
    bodyparts = []
    for bpi in range(numbodyparts):
        bpo = bodypartindex + bpi * 16
        szname, nummodels, base, modelindex = struct.unpack_from("<iiii", mdl, bpo)
        bp_name = _read_cstr_at(mdl, bpo + szname)
        models = []
        for mi in range(nummodels):
            # mstudiomodel_t stride = 148 bytes in L4D2 (ver 48/49)
            mo = bpo + modelindex + mi * 148
            mname = mdl[mo : mo + 64].split(b"\x00", 1)[0].decode("latin-1", "replace")
            mtype, bradius, nummeshes, meshindex, numvertices, vertexindex, tangentsindex = struct.unpack_from(
                "<ifiiiii", mdl, mo + 64
            )
            meshes = []
            # mstudiomesh_t stride = 116 bytes
            for msi in range(nummeshes):
                mso = mo + meshindex + msi * 116
                mat_id, model_off, m_numverts, m_vertoff, m_numlods, m_numflexes = struct.unpack_from(
                    "<iiiiii", mdl, mso
                )
                meshes.append({
                    "material": skin_ids[mat_id] if mat_id < len(skin_ids) else mat_id,
                    "numvertices": m_numverts,
                    "vertexoffset": m_vertoff,
                })
            models.append({
                "name": mname,
                "numvertices": numvertices,
                "vertexindex": vertexindex,  # byte offset in VVD OR vertex index (/48)
                "meshes": meshes,
            })
        bodyparts.append({"name": bp_name, "models": models, "cd_dirs": cd_dirs, "tex_names": tex_names})

    return bones, tex_names, cd_dirs, bodyparts


def parse_vvd(vvd: bytes) -> List[SourceVertex]:
    sig, ver, checksum, num_lods = struct.unpack_from("<4siii", vvd, 0)
    assert sig == b"IDSV", f"Bad VVD sig {sig!r}"
    lod_vert_counts = struct.unpack_from("<8i", vvd, 16)
    num_fixups, fixup_off, vert_off, tang_off = struct.unpack_from("<iiii", vvd, 48)
    lod0_count = lod_vert_counts[0]

    # Check if fixups are needed (LOD0 can pull subsets via fixups)
    def read_raw_vert(idx: int) -> SourceVertex:
        off = vert_off + idx * 48
        # mstudiovertex_t (48 bytes):
        # 0x00: weight[3] (3f)
        # 0x0c: bone[3] (3B)
        # 0x0f: numbones (1B)
        # 0x10: pos (3f)
        # 0x1c: normal (3f)
        # 0x28: texcoord (2f)
        w0, w1, w2, b0, b1, b2, nb = struct.unpack_from("<3f4B", vvd, off)
        pos = struct.unpack_from("<3f", vvd, off + 16)
        norm = struct.unpack_from("<3f", vvd, off + 28)
        uv = struct.unpack_from("<2f", vvd, off + 40)
        ws = []
        raw_bs = (b0, b1, b2)
        raw_ws = (w0, w1, w2)
        for k in range(min(3, nb)):
            if raw_ws[k] > 0.0:
                ws.append((raw_bs[k], raw_ws[k]))
        if not ws:
            ws = [(b0, 1.0)]
        return SourceVertex(pos, norm, uv, ws)

    if num_fixups == 0:
        return [read_raw_vert(i) for i in range(lod0_count)]

    verts: List[SourceVertex] = []
    # vertexFileFixup_t (12b): lod(i32), sourceVertexID(i32), numVertices(i32)
    for fi in range(num_fixups):
        flod, src_id, cnt = struct.unpack_from("<iii", vvd, fixup_off + fi * 12)
        if flod >= 0:  # fixups with lod >= 0 contribute to LOD0
            for k in range(cnt):
                verts.append(read_raw_vert(src_id + k))
    assert len(verts) >= lod0_count, f"VVD fixups gave {len(verts)} < {lod0_count}"
    return verts[:lod0_count]


def parse_vtx_and_build_parts(
    vtx: bytes,
    mdl_bodyparts: List[dict],
    tex_names: List[str],
) -> List[SourceMeshPart]:
    """Parse dx90.vtx LOD0 indices for bodyparts[..].models[0]."""
    ver = struct.unpack_from("<i", vtx, 0)[0]
    assert ver == 7, f"Bad VTX version {ver}"
    num_bp, bp_off = struct.unpack_from("<ii", vtx, 28)
    assert num_bp == len(mdl_bodyparts), (num_bp, len(mdl_bodyparts))

    parts_by_mat: Dict[int, List[Tuple[int, int, int]]] = {}
    # BodyPartHeader_t (8b): numModels(i32), modelOffset(i32)
    for bpi in range(num_bp):
        vbp_off = bp_off + bpi * 8
        n_mod, mod_off = struct.unpack_from("<ii", vtx, vbp_off)
        assert n_mod >= 1
        # Select model 0 of each bodypart (or pick non-empty? Look up LOD0)
        mdl_bp = mdl_bodyparts[bpi]
        # Wait: check all submodels in case bodypart selects model 0 (or non-blank)
        # In L4D2 survivors, bodypart 0 = main body (model 0), extra bodyparts have model 0 = primary
        mi = 0
        m_mdl = mdl_bp["models"][mi]
        # ModelHeader_t (8b): numLODs(i32), lodOffset(i32)
        vm_off = vbp_off + mod_off + mi * 8
        n_lods, lod_off = struct.unpack_from("<ii", vtx, vm_off)
        assert n_lods >= 1
        # ModelLODHeader_t (12b): numMeshes(i32), meshOffset(i32), switchPoint(f32)
        vlod_off = vm_off + lod_off  # LOD 0
        n_meshes, mesh_off, _ = struct.unpack_from("<iif", vtx, vlod_off)
        assert n_meshes == len(m_mdl["meshes"]), (bpi, n_meshes, len(m_mdl["meshes"]))
        m_base_v = m_mdl["vertexindex"] // 48

        for msi in range(n_meshes):
            m_mesh = m_mdl["meshes"][msi]
            mesh_v_base = m_base_v + m_mesh["vertexoffset"]
            mat_id = m_mesh["material"]
            # MeshHeader_t (9b): numStripGroups(i32), stripGroupHeaderOffset(i32), flags(u8)
            vmesh_off = vlod_off + mesh_off + msi * 9
            n_sg, sg_off, _mflags = struct.unpack_from("<iiB", vtx, vmesh_off)
            tris_out = parts_by_mat.setdefault(mat_id, [])

            for sgi in range(n_sg):
                # StripGroupHeader_t (25b packed in OptimizedModel.h):
                # numVerts(i32), vertOffset(i32), numIndices(i32), indexOffset(i32),
                # numStrips(i32), stripOffset(i32), flags(u8)
                vsg_off = vmesh_off + sg_off + sgi * 25
                nv, vo, ni, io, nst, so, _sflags = struct.unpack_from("<iiiiiiB", vtx, vsg_off)
                sg_verts = []
                # Vertex_t (9b): boneWeightIndex[3](3B), numBones(1B), origMeshVertID(u16), boneID[3](3B)
                for vi in range(nv):
                    orig_id = struct.unpack_from("<H", vtx, vsg_off + vo + vi * 9 + 4)[0]
                    sg_verts.append(mesh_v_base + orig_id)
                sg_indices = struct.unpack_from(f"<{ni}H", vtx, vsg_off + io)

                for sti in range(nst):
                    # StripHeader_t (27b packed): numIndices(4), indexOffset(4), numVerts(4), vertOffset(4),
                    # numBones(2), flags(1), numBoneStateChanges(4), boneStateChangeOffset(4)
                    vst_off = vsg_off + so + sti * 27
                    s_ni, s_io, _s_nv, _s_vo, _s_nb, st_flags = struct.unpack_from(
                        "<iiiiHB", vtx, vst_off
                    )
                    is_list = bool(st_flags & 0x01)
                    is_strip = bool(st_flags & 0x02)
                    assert is_list or is_strip, f"Unknown strip flags {st_flags:#x}"
                    if is_list:
                        for k in range(0, s_ni, 3):
                            i0 = sg_verts[sg_indices[s_io + k]]
                            i1 = sg_verts[sg_indices[s_io + k + 1]]
                            i2 = sg_verts[sg_indices[s_io + k + 2]]
                            tris_out.append((i0, i1, i2))
                    else:
                        for k in range(s_ni - 2):
                            a = sg_verts[sg_indices[s_io + k]]
                            b = sg_verts[sg_indices[s_io + k + 1]]
                            c = sg_verts[sg_indices[s_io + k + 2]]
                            if k & 1:
                                tris_out.append((b, a, c))
                            else:
                                tris_out.append((a, b, c))

    parts: List[SourceMeshPart] = []
    for mat_id in sorted(parts_by_mat):
        mname = tex_names[mat_id] if mat_id < len(tex_names) else f"mat_{mat_id}"
        parts.append(SourceMeshPart(mname, parts_by_mat[mat_id]))
    return parts


def parse_vtf(vtf: bytes, name: str) -> SourceTexture:
    sig, v_maj, v_min, hdr_sz, w, h, flags, frames, first_frame = struct.unpack_from(
        "<4sIIIHHIHH", vtf, 0
    )
    assert sig == b"VTF\x00", f"Bad VTF sig {sig!r}"
    # 0x34: highResImageFormat(i32), mipmapCount(u8), lowResImageFormat(i32), lowResWidth(u8), lowResHeight(u8)
    fmt, mip_cnt, low_fmt, lw, lh = struct.unpack_from("<iBiBB", vtf, 0x34)
    depth = struct.unpack_from("<H", vtf, 0x3F)[0] if (v_maj, v_min) >= (7, 2) else 1
    depth = max(1, depth)

    def fmt_size(f: int, bw: int, bh: int) -> int:
        if f == 13:  # DXT1
            return ((bw + 3) // 4) * ((bh + 3) // 4) * 8
        if f in (14, 15):  # DXT3, DXT5
            return ((bw + 3) // 4) * ((bh + 3) // 4) * 16
        if f in (0, 1, 12, 16):  # RGBA8888, ABGR8888, BGRA8888, BGRX8888
            return bw * bh * 4
        if f in (2, 3):  # RGB888, BGR888
            return bw * bh * 3
        raise ValueError(f"Unsupported VTF format {f} in {name}")

    pos = hdr_sz
    if low_fmt >= 0 and lw > 0 and lh > 0:
        pos += fmt_size(low_fmt, lw, lh)

    # VTF stores smallest mip first (mip_cnt-1 down to 0) across all frames (usually 1)
    mip_dims = []
    mw, mh = w, h
    for _ in range(mip_cnt):
        mip_dims.append((mw, mh))
        mw = max(1, mw >> 1)
        mh = max(1, mh >> 1)

    # Compute byte layout smallest -> largest across `frames` frames (we take frame 0)
    mips_smallest_first: List[bytes] = []
    for mw, mh in reversed(mip_dims):
        sz = fmt_size(fmt, mw, mh) * depth
        # Note: if frames > 1, frame 0 is stored at first slice of each mip
        mips_smallest_first.append(vtf[pos : pos + sz])
        pos += sz * max(1, frames)

    mips_largest_first = list(reversed(mips_smallest_first))

    # Convert format=1 (ABGR8888) or 0 (RGBA8888) -> BGRA8 for UE2 (fmt=5),
    # while leaving DXT1(13)/DXT3(14)/DXT5(15)/BGRA8888(12) native!
    has_alpha = False
    if fmt == 1:  # ABGR8888 -> [A,B,G,R] -> BGRA [B,G,R,A]
        converted = []
        for mb in mips_largest_first:
            out = bytearray(len(mb))
            out[0::4] = mb[1::4]
            out[1::4] = mb[2::4]
            out[2::4] = mb[3::4]
            out[3::4] = mb[0::4]
            if any(a < 128 for a in out[3::4]):
                has_alpha = True
            converted.append(bytes(out))
        mips_largest_first = converted
        fmt = 12  # converted to BGRA8888
    elif fmt == 0:  # RGBA8888 -> BGRA8888
        converted = []
        for mb in mips_largest_first:
            out = bytearray(len(mb))
            out[0::4] = mb[2::4]
            out[1::4] = mb[1::4]
            out[2::4] = mb[0::4]
            out[3::4] = mb[3::4]
            if any(a < 128 for a in out[3::4]):
                has_alpha = True
            converted.append(bytes(out))
        mips_largest_first = converted
        fmt = 12

    return SourceTexture(
        name=name,
        width=w,
        height=h,
        vtf_format=fmt,
        mips_largest_first=mips_largest_first,
        has_meaningful_alpha=has_alpha,
    )


def _resolve_vmt_basetexture(vpk: VPKArchive, cd_dirs: List[str], mat_name: str) -> Optional[str]:
    candidates = []
    clean = mat_name.replace("\\", "/").lstrip("/")
    for d in cd_dirs:
        if d:
            candidates.append(f"materials/{d}/{clean}.vmt")
    candidates.append(f"materials/{clean}.vmt")
    vmt_bytes = None
    for c in candidates:
        if c.lower() in vpk.entries:
            vmt_bytes = vpk.read_file(c)
            break
    if vmt_bytes is None:
        # fallback substring search
        low = f"/{clean.lower()}.vmt"
        hits = [k for k in vpk.entries if k.endswith(low)]
        if hits:
            vmt_bytes = vpk.read_file(hits[0])
    if vmt_bytes is None:
        return None
    text = vmt_bytes.decode("latin-1", "replace")
    m = re.search(r'"?\$basetexture"?\s+"?([^"\r\n}]+)"?', text, re.IGNORECASE)
    if not m:
        return None
    btex = m.group(1).strip().replace("\\", "/").lstrip("/")
    if not btex.lower().startswith("materials/"):
        btex = f"materials/{btex}"
    if not btex.lower().endswith(".vtf"):
        btex = f"{btex}.vtf"
    return btex


def load_source_character(vpk_path: str, mdl_rel_path: str) -> SourceCharacter:
    vpk = VPKArchive(vpk_path)
    base = mdl_rel_path[:-4] if mdl_rel_path.lower().endswith(".mdl") else mdl_rel_path
    mdl_bytes = vpk.read_file(base + ".mdl")
    vvd_bytes = vpk.read_file(base + ".vvd")
    vtx_bytes = vpk.read_file(base + ".dx90.vtx")

    bones, tex_names, cd_dirs, bodyparts = parse_mdl(mdl_bytes)
    verts = parse_vvd(vvd_bytes)
    parts = parse_vtx_and_build_parts(vtx_bytes, bodyparts, tex_names)

    # Compute world bone matrices in Source bind pose (from local pos + quat)
    world_mats: List[List[float]] = []
    for bi, b in enumerate(bones):
        local = _quat_pos_to_mat3x4(b.quat, b.pos)
        if b.parent < 0:
            world_mats.append(local)
        else:
            world_mats.append(_mat3x4_mul(world_mats[b.parent], local))

    # Load textures for used parts
    textures: Dict[str, SourceTexture] = {}
    used_mats = []
    for p in parts:
        used_mats.append(p.material_name)
        if p.material_name not in textures:
            vtf_path = _resolve_vmt_basetexture(vpk, cd_dirs, p.material_name)
            if vtf_path and vtf_path.lower() in vpk.entries:
                vtf_data = vpk.read_file(vtf_path)
                textures[p.material_name] = parse_vtf(vtf_data, p.material_name)

    return SourceCharacter(
        mdl_path=mdl_rel_path,
        bones=bones,
        bone_world_mats=world_mats,
        vertices=verts,
        parts=parts,
        materials=used_mats,
        textures=textures,
    )
