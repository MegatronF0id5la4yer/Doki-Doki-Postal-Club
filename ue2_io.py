"""UE2 (Postal 2 ver=118, lic=2) binary package reader/appender/builder."""
from __future__ import annotations
import struct
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


PKG_SIGNATURE = 0x9E2A83C1
PKG_VERSION = 118
PKG_LICENSEE = 2

RF_PUBLIC = 0x00000004
RF_STANDALONE = 0x00080000
RF_LOAD_CLIENT = 0x00010000
RF_LOAD_SERVER = 0x00020000
RF_LOAD_EDIT = 0x00040000
RF_DEFAULT_OBJ = RF_PUBLIC | RF_LOAD_CLIENT | RF_LOAD_SERVER | RF_LOAD_EDIT
RF_DEFAULT_TEX = RF_DEFAULT_OBJ | RF_STANDALONE


def read_ci(buf: bytes | bytearray, pos: int) -> Tuple[int, int]:
    b0 = buf[pos]
    pos += 1
    neg = b0 & 0x80
    val = b0 & 0x3F
    if b0 & 0x40:
        b1 = buf[pos]
        pos += 1
        val |= (b1 & 0x7F) << 6
        if b1 & 0x80:
            b2 = buf[pos]
            pos += 1
            val |= (b2 & 0x7F) << 13
            if b2 & 0x80:
                b3 = buf[pos]
                pos += 1
                val |= (b3 & 0x7F) << 20
                if b3 & 0x80:
                    b4 = buf[pos]
                    pos += 1
                    val |= b4 << 27
    return (-val if neg else val), pos


def write_ci(val: int) -> bytes:
    neg = val < 0
    v = -val if neg else val
    b0 = (v & 0x3F) | (0x80 if neg else 0)
    v >>= 6
    if not v:
        return bytes([b0])
    out = bytearray([b0 | 0x40])
    for _ in range(4):
        chunk = v & 0x7F
        v >>= 7
        if v:
            out.append(chunk | 0x80)
        else:
            out.append(chunk)
            break
    return bytes(out)


def read_fstring(buf: bytes | bytearray, pos: int) -> Tuple[str, int]:
    length, pos = read_ci(buf, pos)
    if length < 0:
        raw = buf[pos : pos + (-length) * 2]
        pos += (-length) * 2
        return raw.decode("utf-16-le", "replace").rstrip("\x00"), pos
    raw = buf[pos : pos + length]
    pos += length
    return raw.decode("latin-1", "replace").rstrip("\x00"), pos


def write_fstring(s: str) -> bytes:
    b = s.encode("latin-1") + b"\x00"
    return write_ci(len(b)) + b


@dataclass
class UE2Import:
    class_package: int  # NameIndex
    class_name: int     # NameIndex
    package_idx: int    # ObjectReference (outer)
    object_name: int    # NameIndex


@dataclass
class UE2Export:
    class_idx: int      # ObjectReference
    super_idx: int      # ObjectReference
    outer_idx: int      # ObjectReference
    object_name: int    # NameIndex
    object_flags: int
    serial_size: int
    serial_offset: int


@dataclass
class UE2Package:
    raw: bytearray
    version: int = PKG_VERSION
    licensee: int = PKG_LICENSEE
    pkg_flags: int = 1
    guid: bytes = b"\x00" * 16
    generations: List[Tuple[int, int]] = field(default_factory=list)
    names: List[Tuple[str, int]] = field(default_factory=list)
    imports: List[UE2Import] = field(default_factory=list)
    exports: List[UE2Export] = field(default_factory=list)
    name_offset: int = 64
    import_offset: int = 0
    export_offset: int = 0
    _name_map: Dict[str, int] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str) -> "UE2Package":
        with open(path, "rb") as f:
            raw = bytearray(f.read())
        sig, ver, lic, pkg_flags, nc, no, ec, eo, ic, io = struct.unpack_from(
            "<IHHIIIIIII", raw, 0
        )
        assert sig == PKG_SIGNATURE, f"Bad UE2 sig in {path}: {sig:#x}"
        guid = bytes(raw[36:52])
        gcnt, = struct.unpack_from("<I", raw, 52)
        gens = []
        pos = 56
        for _ in range(gcnt):
            ec_g, nc_g = struct.unpack_from("<II", raw, pos)
            pos += 8
            gens.append((ec_g, nc_g))

        names: List[Tuple[str, int]] = []
        name_map: Dict[str, int] = {}
        pos = no
        for i in range(nc):
            s, pos = read_fstring(raw, pos)
            nflags, = struct.unpack_from("<I", raw, pos)
            pos += 4
            names.append((s, nflags))
            name_map.setdefault(s, i)

        imports: List[UE2Import] = []
        pos = io
        for _ in range(ic):
            cp, pos = read_ci(raw, pos)
            cl, pos = read_ci(raw, pos)
            pkg, = struct.unpack_from("<i", raw, pos)
            pos += 4
            on, pos = read_ci(raw, pos)
            imports.append(UE2Import(cp, cl, pkg, on))

        exports: List[UE2Export] = []
        pos = eo
        for _ in range(ec):
            cl, pos = read_ci(raw, pos)
            sup, pos = read_ci(raw, pos)
            outer, = struct.unpack_from("<i", raw, pos)
            pos += 4
            on, pos = read_ci(raw, pos)
            oflags, = struct.unpack_from("<I", raw, pos)
            pos += 4
            ssz, pos = read_ci(raw, pos)
            soff = 0
            if ssz > 0:
                soff, pos = read_ci(raw, pos)
            exports.append(UE2Export(cl, sup, outer, on, oflags, ssz, soff))

        return cls(
            raw=raw,
            version=ver,
            licensee=lic,
            pkg_flags=pkg_flags,
            guid=guid,
            generations=gens,
            names=names,
            imports=imports,
            exports=exports,
            name_offset=no,
            import_offset=io,
            export_offset=eo,
            _name_map=name_map,
        )

    @classmethod
    def new_empty(cls) -> "UE2Package":
        hdr = bytearray(64)
        pkg = cls(
            raw=hdr,
            version=PKG_VERSION,
            licensee=PKG_LICENSEE,
            pkg_flags=1,
            guid=uuid.uuid4().bytes,
            generations=[(0, 1)],
            names=[("None", 0x00070410)],
            imports=[],
            exports=[],
            name_offset=64,
            import_offset=64,
            export_offset=64,
            _name_map={"None": 0},
        )
        return pkg

    def obj_name(self, idx: int) -> str:
        if idx == 0:
            return "None"
        if idx < 0:
            return self.names[self.imports[-idx - 1].object_name][0]
        return self.names[self.exports[idx - 1].object_name][0]

    def ensure_name(self, s: str, flags: int = 0x00070410) -> int:
        if s in self._name_map:
            return self._name_map[s]
        idx = len(self.names)
        self.names.append((s, flags))
        self._name_map[s] = idx
        return idx

    def find_import(self, pkg_name: str, cls_name: str, outer: int, obj_name: str) -> Optional[int]:
        for i, imp in enumerate(self.imports):
            if (
                self.names[imp.class_package][0] == pkg_name
                and self.names[imp.class_name][0] == cls_name
                and imp.package_idx == outer
                and self.names[imp.object_name][0] == obj_name
            ):
                return -(i + 1)
        return None

    def ensure_import(self, pkg_name: str, cls_name: str, outer: int, obj_name: str) -> int:
        found = self.find_import(pkg_name, cls_name, outer, obj_name)
        if found is not None:
            return found
        cp = self.ensure_name(pkg_name)
        cl = self.ensure_name(cls_name)
        on = self.ensure_name(obj_name)
        self.imports.append(UE2Import(cp, cl, outer, on))
        return -len(self.imports)

    def find_export(self, obj_name: str, outer_idx: Optional[int] = None) -> Optional[int]:
        for i, exp in enumerate(self.exports):
            if self.names[exp.object_name][0] == obj_name:
                if outer_idx is None or exp.outer_idx == outer_idx:
                    return i + 1
        return None

    def find_export_ci(self, obj_name: str) -> Optional[int]:
        low = obj_name.lower()
        for i, exp in enumerate(self.exports):
            if self.names[exp.object_name][0].lower() == low:
                return i + 1
        return None

    def append_space_offset(self) -> int:
        """Start appending new export payloads safely without shifting any existing export offset."""
        if not hasattr(self, "_append_cursor"):
            # Safe insertion point: right after the highest existing export data (or old import_offset),
            # never touching bytes before import_offset so existing TLazyArray::skip_off remain 100% valid!
            max_end = max(
                [self.import_offset]
                + [e.serial_offset + e.serial_size for e in self.exports if e.serial_size > 0]
            )
            self._append_cursor = max(64, max_end)
            if len(self.raw) < self._append_cursor:
                self.raw.extend(b"\x00" * (self._append_cursor - len(self.raw)))
        return self._append_cursor

    def add_export_builder(
        self,
        class_idx: int,
        super_idx: int,
        outer_idx: int,
        name: str,
        flags: int,
        build_fn,  # Callable[[int], bytes] receives exact file offset where payload will live!
    ) -> int:
        ni = self.ensure_name(name)
        off = self.append_space_offset()
        payload = build_fn(off)
        self.raw[off : off + len(payload)] = payload
        self._append_cursor = off + len(payload)
        self.exports.append(
            UE2Export(
                class_idx=class_idx,
                super_idx=super_idx,
                outer_idx=outer_idx,
                object_name=ni,
                object_flags=flags,
                serial_size=len(payload),
                serial_offset=off,
            )
        )
        return len(self.exports)

    def add_group_export(self, pkg_class_idx: int, name: str, outer_idx: int = 0) -> int:
        # UPackage::Serialize reads UStruct::SerializeTaggedProperties ("None" terminator)
        return self.add_export_builder(
            pkg_class_idx,
            0,
            outer_idx,
            name,
            RF_DEFAULT_OBJ,
            lambda _off: write_ci(self.ensure_name("None")),
        )

    def replace_export_payload(self, export_1based: int, new_payload: bytes) -> None:
        """Replace a non-lazy export payload safely at append cursor (never shifts other exports)."""
        off = self.append_space_offset()
        self.raw[off : off + len(new_payload)] = new_payload
        self._append_cursor = off + len(new_payload)
        e = self.exports[export_1based - 1]
        e.serial_offset = off
        e.serial_size = len(new_payload)

    def save(self, path: str) -> None:
        # Preserve original prefix (0 .. append_cursor), discarding trailing old tables
        end_data = self.append_space_offset()
        out = bytearray(self.raw[:end_data])

        # Write NameTable at end_data! (All existing offsets < end_data stay intact; NameOffset moves cleanly to end_data)
        name_offset = len(out)
        for s, nflags in self.names:
            out.extend(write_fstring(s))
            out.extend(struct.pack("<I", nflags))

        import_offset = len(out)
        for imp in self.imports:
            out.extend(write_ci(imp.class_package))
            out.extend(write_ci(imp.class_name))
            out.extend(struct.pack("<i", imp.package_idx))
            out.extend(write_ci(imp.object_name))

        export_offset = len(out)
        for exp in self.exports:
            out.extend(write_ci(exp.class_idx))
            out.extend(write_ci(exp.super_idx))
            out.extend(struct.pack("<i", exp.outer_idx))
            out.extend(write_ci(exp.object_name))
            out.extend(struct.pack("<I", exp.object_flags))
            out.extend(write_ci(exp.serial_size))
            if exp.serial_size > 0:
                out.extend(write_ci(exp.serial_offset))

        # Update Generations (last generation gets current counts)
        if not self.generations:
            self.generations = [(len(self.exports), len(self.names))]
        else:
            self.generations[-1] = (len(self.exports), len(self.names))

        # Rebuild 64-byte header (note len(generations) may be >= 1; only 1 fits cleanly in 64b header if empty pkg)
        hdr = bytearray()
        hdr.extend(
            struct.pack(
                "<IHHIIIIIII",
                PKG_SIGNATURE,
                self.version,
                self.licensee,
                self.pkg_flags,
                len(self.names),
                name_offset,
                len(self.exports),
                export_offset,
                len(self.imports),
                import_offset,
            )
        )
        hdr.extend(self.guid[:16])
        hdr.extend(struct.pack("<I", len(self.generations)))
        for ec_g, nc_g in self.generations:
            hdr.extend(struct.pack("<II", ec_g, nc_g))

        if len(hdr) > 64 and self.name_offset == 64 and len(self.exports) > 0:
            # Verify multi-gen original packages had HeaderEnd <= old name_offset
            hdr_orig_len = 56 + 8 * len(self.generations)
            assert hdr_orig_len <= self.name_offset or self.name_offset == 64
        out[0 : len(hdr)] = hdr

        with open(path, "wb") as f:
            f.write(out)


def encode_prop_obj(prop_name_idx: int, obj_ref: int, array_idx: int = 0) -> bytes:
    """Encode an ObjectProperty (type=5) FPropertyTag (ver=118)."""
    val = write_ci(obj_ref)
    if len(val) == 1:
        st = 0  # 1 byte
        sz_hdr = b""
    elif len(val) == 2:
        st = 1  # 2 bytes
        sz_hdr = b""
    elif len(val) == 4:
        st = 2  # 4 bytes
        sz_hdr = b""
    else:
        st = 5
        sz_hdr = bytes([len(val)])
    info = 5 | (st << 4) | (0x80 if array_idx > 0 else 0)
    arr = write_ci(array_idx) if array_idx > 0 else b""
    return write_ci(prop_name_idx) + bytes([info]) + sz_hdr + arr + val


def encode_prop_byte(prop_name_idx: int, byte_val: int) -> bytes:
    info = 1 | (0 << 4)
    return write_ci(prop_name_idx) + bytes([info, byte_val & 0xFF])


def encode_prop_int(prop_name_idx: int, int_val: int, array_idx: int = 0) -> bytes:
    info = 2 | (2 << 4) | (0x80 if array_idx > 0 else 0)
    arr = write_ci(array_idx) if array_idx > 0 else b""
    return write_ci(prop_name_idx) + bytes([info]) + arr + struct.pack("<i", int_val)


def encode_prop_float(prop_name_idx: int, float_val: float, array_idx: int = 0) -> bytes:
    """Encode a FloatProperty (type=4, stype=2) FPropertyTag."""
    info = 4 | (2 << 4) | (0x80 if array_idx > 0 else 0)
    arr = write_ci(array_idx) if array_idx > 0 else b""
    return write_ci(prop_name_idx) + bytes([info]) + arr + struct.pack("<f", float_val)


def _encode_array_prop_body(prop_name_idx: int, inner: bytearray | bytes) -> bytes:
    sz = len(inner)
    if sz < 256:
        info = 9 | (5 << 4)
        sz_hdr = bytes([sz])
    elif sz < 65536:
        info = 9 | (6 << 4)
        sz_hdr = struct.pack("<H", sz)
    else:
        info = 9 | (7 << 4)
        sz_hdr = struct.pack("<I", sz)
    return write_ci(prop_name_idx) + bytes([info]) + sz_hdr + bytes(inner)


def encode_prop_obj_array(prop_name_idx: int, obj_refs: List[int]) -> bytes:
    """Encode an ArrayProperty (type=9) of ObjectProperty compact-index references."""
    inner = bytearray(write_ci(len(obj_refs)))
    for ref in obj_refs:
        inner.extend(write_ci(ref))
    return _encode_array_prop_body(prop_name_idx, inner)


def encode_prop_struct_array(prop_name_idx: int, struct_items: List[bytes]) -> bytes:
    """Encode an ArrayProperty (type=9) of serialized StructProperty element streams."""
    inner = bytearray(write_ci(len(struct_items)))
    for item in struct_items:
        inner.extend(item)
    return _encode_array_prop_body(prop_name_idx, inner)


def encode_prop_bool(prop_name_idx: int, val: bool) -> bytes:
    # Postal 2 Shader style: SizeType=5 (0x53/0xd3) + 1 byte Size=0 (or SizeType=0 0x83/0x03)
    info = 3 | (5 << 4) | (0x80 if val else 0)
    return write_ci(prop_name_idx) + bytes([info, 0x00])


def encode_prop_struct_color(prop_name_idx: int, color_name_idx: int, r: int, g: int, b: int, a: int) -> bytes:
    info = 10 | (2 << 4)  # StructProperty size=4
    return (
        write_ci(prop_name_idx)
        + bytes([info])
        + write_ci(color_name_idx)
        + struct.pack("<BBBB", b, g, r, a)
    )


def build_utexture_payload(
    pkg: UE2Package,
    width: int,
    height: int,
    ue2_format: int,  # 5=BGRA8, 8=DXT5
    mips_largest_first: List[bytes],
    export_offset: int,
) -> bytes:
    import math

    ubits = int(math.log2(width))
    vbits = int(math.log2(height))
    out = bytearray()
    out.extend(encode_prop_byte(pkg.ensure_name("LODSet"), 2))  # LODSET_World
    out.extend(encode_prop_byte(pkg.ensure_name("Format"), ue2_format))
    out.extend(encode_prop_byte(pkg.ensure_name("UBits"), ubits))
    out.extend(encode_prop_byte(pkg.ensure_name("VBits"), vbits))
    out.extend(encode_prop_int(pkg.ensure_name("USize"), width))
    out.extend(encode_prop_int(pkg.ensure_name("VSize"), height))
    out.extend(encode_prop_int(pkg.ensure_name("UClamp"), width))
    out.extend(encode_prop_int(pkg.ensure_name("VClamp"), height))
    out.extend(write_ci(pkg.ensure_name("None")))

    # TArray<FMipmap>
    out.extend(write_ci(len(mips_largest_first)))
    mw, mh = width, height
    mub, mvb = ubits, vbits
    for mbytes in mips_largest_first:
        # FMipmap: DataArray TLazyArray<BYTE>(u32 skip_off + ci size + data) + USize(u32) + VSize(u32) + UBits(u8) + VBits(u8)
        dsz_ci = write_ci(len(mbytes))
        skip_off = export_offset + len(out) + 4 + len(dsz_ci) + len(mbytes)
        out.extend(struct.pack("<I", skip_off))
        out.extend(dsz_ci)
        out.extend(mbytes)
        out.extend(struct.pack("<IIBB", mw, mh, mub, mvb))
        mw = max(1, mw >> 1)
        mh = max(1, mh >> 1)
        mub = max(0, mub - 1)
        mvb = max(0, mvb - 1)
    return bytes(out)


def build_shader_payload(
    pkg: UE2Package,
    diffuse_ref: int,
    two_sided: bool = True,
) -> bytes:
    out = bytearray()
    out.extend(encode_prop_obj(pkg.ensure_name("Diffuse"), diffuse_ref))
    if two_sided:
        out.extend(encode_prop_bool(pkg.ensure_name("TwoSided"), True))
    out.extend(write_ci(pkg.ensure_name("None")))
    return bytes(out)


def pack_normal_10_10_10(nx: float, ny: float, nz: float) -> int:
    """Pack a unit normal into UE2 FMeshNorm 10-10-10 signed-offset-511 u32."""
    ix = max(-511, min(511, int(round(nx * 511.0)))) + 511
    iy = max(-511, min(511, int(round(ny * 511.0)))) + 511
    iz = max(-511, min(511, int(round(nz * 511.0)))) + 511
    return (ix & 0x3FF) | ((iy & 0x3FF) << 10) | ((iz & 0x3FF) << 20)


def create_skinning_stream(
    n_pts: int,
    wdgs: List[Tuple[int, float, float]],
    fcs: List[Tuple[int, int, int, int]],  # w0, w1, w2, mat_idx
    infs: List[Tuple[float, int, int]],     # weight, vert_idx, bone_idx
    n_bones: int,
) -> Tuple[List[int], List[int], List[Tuple[int, ...]], int, int]:
    """Replicate postal2-bin CreateSkinningStream(FStaticLODModel*, USkeletalMesh*) bit-for-bit."""
    pt_refs = [0] * n_pts
    w_dup = [-1] * len(wdgs)
    pt_dup = [0] * n_pts
    for vi, _, _ in wdgs:
        pt_refs[vi] += 1

    dup_cnt = 0
    for wi, (vi, _, _) in enumerate(wdgs):
        if pt_refs[vi] > 1:
            if w_dup[wi] == -1:
                if pt_dup[vi] == 0:
                    w_dup[wi] = 0
                    dup_cnt += 1
                    pt_dup[vi] = dup_cnt
                else:
                    w_dup[wi] = pt_dup[vi]

    stream: List[int] = []
    inf_cur = 0
    max_inf = 1
    for wi, (vi, fu, fv) in enumerate(wdgs):
        u_u32 = struct.unpack("<I", struct.pack("<f", fu))[0]
        v_u32 = struct.unpack("<I", struct.pack("<f", fv))[0]
        if w_dup[wi] > 0:
            d = w_dup[wi]
            stream.append(0xF0000000 | (((d - 1) * 6) & 0x0FFFFFFF))
            stream.append(u_u32)
            stream.append(v_u32)
            continue

        assert inf_cur < len(infs) and infs[inf_cur][1] == vi, (
            f"RawInfluences out of sync at wedge {wi} vert {vi}: inf_cur={inf_cur} "
            f"got {infs[inf_cur] if inf_cur < len(infs) else None}"
        )
        j = inf_cur + 1
        while j < len(infs) and infs[j][1] == vi:
            j += 1
        cnt = min(8, j - inf_cur)
        max_inf = max(max_inf, cnt)

        hdr = (cnt - 1) << 28
        if w_dup[wi] == 0:
            hdr |= 0x80000000

        for k in range(cnt):
            wt, _, bi = infs[inf_cur + k]
            b6 = (bi * 6) if bi < n_bones else 0
            wi_int = max(0, min(65535, int(wt * 65535.0)))
            word = (hdr if k == 0 else 0) | ((wi_int & 0xFFFF) << 12) | b6
            stream.append(word & 0xFFFFFFFF)

        inf_cur = j
        stream.append(u_u32)
        stream.append(v_u32)

    stream.append(0xFFFFFFFF)

    index_buf: List[int] = []
    for w0, w1, w2, _mat in fcs:
        index_buf.extend((w0, w1, w2))

    # Group contiguous faces by MaterialIndex into FSkelMeshSection tuples
    sections: List[Tuple[int, ...]] = []
    cur_sec: Optional[List[int]] = None
    for fi, (w0, w1, w2, mat) in enumerate(fcs):
        mn = min(w0, w1, w2)
        mx = max(w0, w1, w2)
        if cur_sec is None or cur_sec[0] != mat:
            if cur_sec is not None:
                cur_sec[4] = (1 - cur_sec[2]) & 0xFFFF
                sections.append(tuple(cur_sec))
            cur_sec = [mat, 0, mn, mx, 0, 1, 4, fi, 1]
        else:
            cur_sec[2] = min(cur_sec[2], mn)
            cur_sec[3] = max(cur_sec[3], mx)
            cur_sec[8] += 1
    if cur_sec is not None:
        cur_sec[4] = (1 - cur_sec[2]) & 0xFFFF
        sections.append(tuple(cur_sec))

    return stream, index_buf, sections, dup_cnt, max_inf


@dataclass
class SkelMeshTemplate:
    """Extracted skeleton/attachment/orientation metadata from a stock USkeletalMesh."""
    bones: List[Tuple[str, int, Tuple[float, ...], Tuple[float, ...], Tuple[float, ...], int, int]]
    default_anim_ref: int
    skeletal_depth: int
    scale: Tuple[float, float, float]
    origin: Tuple[float, float, float]
    rot_origin: Tuple[int, int, int]
    attach_aliases: List[str]
    attach_bones: List[str]
    attach_coords: List[Tuple[float, ...]]
    lod_floats: Tuple[float, ...]


def extract_skel_template(pkg: UE2Package, mesh_name: str) -> SkelMeshTemplate:
    ex = pkg.exports[pkg.find_export_ci(mesh_name) - 1]
    buf = pkg.raw[ex.serial_offset : ex.serial_offset + ex.serial_size]
    pos = 0
    while True:
        ni, pos = read_ci(buf, pos)
        if pkg.names[ni][0] == "None":
            break
        raise ValueError(f"Unexpected prop in {mesh_name}: {pkg.names[ni][0]}")
    pos += 41 + 8
    nv, pos = read_ci(buf, pos); pos += nv * 4
    nt, pos = read_ci(buf, pos)
    for _ in range(nt):
        _, pos = read_ci(buf, pos)
    scale = struct.unpack_from("<3f", buf, pos); pos += 12
    origin = struct.unpack_from("<3f", buf, pos); pos += 12
    rot = struct.unpack_from("<3i", buf, pos); pos += 12
    for sz in (2, 8, 2, 10, 8):
        n, pos = read_ci(buf, pos)
        pos += n * sz
    lod_floats = struct.unpack_from("<6f", buf, pos); pos += 24
    np2, pos = read_ci(buf, pos); pos += np2 * 12
    nb, pos = read_ci(buf, pos)
    bones = []
    for _ in range(nb):
        bni, pos = read_ci(buf, pos)
        bflags = struct.unpack_from("<I", buf, pos)[0]; pos += 4
        q = struct.unpack_from("<4f", buf, pos); pos += 16
        p = struct.unpack_from("<3f", buf, pos); pos += 12
        dims = struct.unpack_from("<4f", buf, pos); pos += 16
        nchild, parent = struct.unpack_from("<ii", buf, pos); pos += 8
        bones.append((pkg.names[bni][0], bflags, q, p, dims, nchild, parent))
    def_anim, pos = read_ci(buf, pos)
    skel_depth = struct.unpack_from("<i", buf, pos)[0]; pos += 4
    for _ in range(2):
        n, pos = read_ci(buf, pos)
        pos += n * 4
    n_aa, pos = read_ci(buf, pos)
    aa = []
    for _ in range(n_aa):
        ni, pos = read_ci(buf, pos)
        aa.append(pkg.names[ni][0])
    n_ab, pos = read_ci(buf, pos)
    ab = []
    for _ in range(n_ab):
        ni, pos = read_ci(buf, pos)
        ab.append(pkg.names[ni][0])
    n_ac, pos = read_ci(buf, pos)
    ac = []
    for _ in range(n_ac):
        ac.append(struct.unpack_from("<12f", buf, pos))
        pos += 48
    return SkelMeshTemplate(
        bones=bones,
        default_anim_ref=def_anim,
        skeletal_depth=skel_depth,
        scale=scale,
        origin=origin,
        rot_origin=rot,
        attach_aliases=aa,
        attach_bones=ab,
        attach_coords=ac,
        lod_floats=lod_floats,
    )


def _write_tlazy_array(out: bytearray, export_offset: int, cnt: int, body_bytes: bytes) -> None:
    cnt_ci = write_ci(cnt)
    skip_off = export_offset + len(out) + 4 + len(cnt_ci) + len(body_bytes)
    out.extend(struct.pack("<I", skip_off))
    out.extend(cnt_ci)
    out.extend(body_bytes)


def build_skeletal_mesh_payload(
    pkg: UE2Package,
    export_offset: int,
    template: SkelMeshTemplate,
    texture_refs: List[int],
    pts: List[Tuple[float, float, float]],
    normals: List[Tuple[float, float, float]],
    wdgs: List[Tuple[int, float, float]],
    fcs: List[Tuple[int, int, int, int]],
    infs: List[Tuple[float, int, int]],
    default_anim_ref: Optional[int] = None,
    origin: Optional[Tuple[float, float, float]] = None,
    rot_origin: Optional[Tuple[int, int, int]] = None,
    scale: Optional[Tuple[float, float, float]] = None,
) -> bytes:
    """Serialize a complete UE2 USkeletalMesh with 1 crisp LOD0 matching postal2-bin."""
    n_pts = len(pts)
    n_wdg = len(wdgs)
    n_fcs = len(fcs)
    n_bones = len(template.bones)
    assert n_pts <= 65535 and n_wdg <= 65535, (n_pts, n_wdg)
    assert len(normals) == n_pts

    skin_data, index_buf, sections, dup_cnt, max_inf = create_skinning_stream(
        n_pts, wdgs, fcs, infs, n_bones
    )

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    zs = [p[2] for p in pts]
    mn = (min(xs), min(ys), min(zs))
    mx = (max(xs), max(ys), max(zs))
    cx = 0.5 * (mn[0] + mx[0])
    cy = 0.5 * (mn[1] + mx[1])
    cz = 0.5 * (mn[2] + mx[2])
    r = max(((p[0] - cx) ** 2 + (p[1] - cy) ** 2 + (p[2] - cz) ** 2) ** 0.5 for p in pts)

    out = bytearray()
    # 1. UObject props (None)
    out.extend(write_ci(pkg.ensure_name("None")))
    # 2. UPrimitive BBox (25b) + BSphere (16b)
    out.extend(struct.pack("<6fB", mn[0], mn[1], mn[2], mx[0], mx[1], mx[2], 1))
    out.extend(struct.pack("<4f", cx, cy, cz, r))
    # 3. ULodMesh: InternalVersion=2, FrameSize=n_pts, Verts=[], Textures=[...]
    out.extend(struct.pack("<II", 2, n_pts))
    out.extend(write_ci(0))
    out.extend(write_ci(len(texture_refs)))
    for tref in texture_refs:
        out.extend(write_ci(tref))

    sc = scale if scale is not None else template.scale
    og = origin if origin is not None else template.origin
    ro = rot_origin if rot_origin is not None else template.rot_origin
    out.extend(struct.pack("<3f3f3i", *sc, *og, *ro))

    # CollapsePointThus (FaceLevel u16[]), Faces=[], CollapseWedgeThus=[], Wedges=[], Materials
    out.extend(write_ci(n_fcs))
    out.extend(b"\x00\x00" * n_fcs)
    out.extend(write_ci(0))  # Faces
    out.extend(write_ci(0))  # CollapseWedgeThus
    out.extend(write_ci(0))  # Wedges
    out.extend(write_ci(len(texture_refs)))
    for ti in range(len(texture_refs)):
        out.extend(struct.pack("<II", 0, ti))  # PolyFlags=0, TextureIndex=ti
    out.extend(struct.pack("<6f", *template.lod_floats))

    # 4. USkeletalMesh: Points=[], RefSkeleton, DefaultAnim, SkeletalDepth
    out.extend(write_ci(0))
    out.extend(write_ci(n_bones))
    for bname, bflags, q, p, dims, nchild, parent in template.bones:
        out.extend(write_ci(pkg.ensure_name(bname)))
        out.extend(struct.pack("<I", bflags))
        out.extend(struct.pack("<4f3f4fii", *q, *p, *dims, nchild, parent))

    anim_ref = template.default_anim_ref if default_anim_ref is None else default_anim_ref
    out.extend(write_ci(anim_ref))
    out.extend(struct.pack("<i", template.skeletal_depth))

    # WeightIndices=[], BoneWeightIdx=[]
    out.extend(write_ci(0))
    out.extend(write_ci(0))

    # AttachAliases, AttachBoneNames, AttachCoords
    out.extend(write_ci(len(template.attach_aliases)))
    for a in template.attach_aliases:
        out.extend(write_ci(pkg.ensure_name(a)))
    out.extend(write_ci(len(template.attach_bones)))
    for a in template.attach_bones:
        out.extend(write_ci(pkg.ensure_name(a)))
    out.extend(write_ci(len(template.attach_coords)))
    for c in template.attach_coords:
        out.extend(struct.pack("<12f", *c))

    # 5. LODModels: 1 crisp LODModel at DisplayFactor=1.0
    out.extend(write_ci(1))
    # SkinningData
    out.extend(write_ci(len(skin_data)))
    out.extend(struct.pack(f"<{len(skin_data)}I", *skin_data))
    # SkinPoints (FVector + packed 10-10-10 normal) — exact match to pts[0..n_pts-1]
    out.extend(write_ci(n_pts))
    for p, n in zip(pts, normals):
        out.extend(struct.pack("<3fI", p[0], p[1], p[2], pack_normal_10_10_10(*n)))
    # LODFlags = n_wdg (matches Avg_Dude)
    out.extend(struct.pack("<I", n_wdg))
    # Sections & SmoothSections=[]
    out.extend(write_ci(len(sections)))
    for sec in sections:
        out.extend(struct.pack("<9H", *sec))
    out.extend(write_ci(0))
    # IndexBuffer + Revision=0, SmoothIndexBuffer=[] + Revision=0
    out.extend(write_ci(len(index_buf)))
    out.extend(struct.pack(f"<{len(index_buf)}H", *index_buf))
    out.extend(struct.pack("<i", 0))
    out.extend(write_ci(0))
    out.extend(struct.pack("<i", 0))
    # f3 (3 x u32 = 0), AnimVerts=[]
    out.extend(struct.pack("<III", 0, 0, 0))
    out.extend(write_ci(0))
    # LOD0 4 TLazyArrays: RawInfluences, RawWedges, RawFaces, RawPoints
    inf_bytes = b"".join(struct.pack("<fHH", w, vi, bi) for w, vi, bi in infs)
    wdg_bytes = b"".join(struct.pack("<Hff", vi, u, v) for vi, u, v in wdgs)
    fcs_bytes = b"".join(struct.pack("<4H", w0, w1, w2, m) for w0, w1, w2, m in fcs)
    pts_bytes = b"".join(struct.pack("<3f", *p) for p in pts)
    _write_tlazy_array(out, export_offset, len(infs), inf_bytes)
    _write_tlazy_array(out, export_offset, n_wdg, wdg_bytes)
    _write_tlazy_array(out, export_offset, n_fcs, fcs_bytes)
    _write_tlazy_array(out, export_offset, n_pts, pts_bytes)
    # tail6: DisplayFactor=1.0, Hysteresis=0.02, DupCount, MaxInf, 0, 0.0
    out.extend(struct.pack("<IfIIIf", 0x3F800000, 0.02, dup_cnt, 4, 0, 0.0))

    # 6. Tail of USkeletalMesh: RefAnim=0 + 6 TLazyArrays (Points, Wedges, Tris, Infs, CollapseWedgeThus, FaceLevel)
    out.extend(write_ci(0))
    # Build VTriangle (12b: 3*u16 iWedge + u8 MatIndex + u8 AuxMat + u32 SmoothingGroups)
    tri12_bytes = b"".join(struct.pack("<3HBBi", w0, w1, w2, m & 0xFF, 0, 1) for w0, w1, w2, m in fcs)
    cw_bytes = b"".join(struct.pack("<H", i) for i in range(n_wdg))
    fl_bytes = b"\x00\x00" * n_fcs
    _write_tlazy_array(out, export_offset, n_pts, pts_bytes)
    _write_tlazy_array(out, export_offset, n_wdg, wdg_bytes)
    _write_tlazy_array(out, export_offset, n_fcs, tri12_bytes)
    _write_tlazy_array(out, export_offset, len(infs), inf_bytes)
    _write_tlazy_array(out, export_offset, n_wdg, cw_bytes)
    _write_tlazy_array(out, export_offset, n_fcs, fl_bytes)
    return bytes(out)


def parse_prop_stream(pkg: UE2Package, buf: bytes | bytearray, start_off: int):
    """Parse FPropertyTag chain starting at start_off; raises if invalid."""
    pos = start_off
    out = []
    while pos < len(buf):
        ni, pos2 = read_ci(buf, pos)
        if ni < 0 or ni >= len(pkg.names):
            raise ValueError(f"Bad name index {ni} at {pos}")
        name = pkg.names[ni][0]
        if name == "None":
            return out, pos2
        info = buf[pos2]
        pos2 += 1
        ptype = info & 0x0F
        stype = (info >> 4) & 0x07
        arr_flag = (info >> 7) & 1
        struct_name = None
        if ptype == 10:
            sni, pos2 = read_ci(buf, pos2)
            struct_name = pkg.names[sni][0]
        sz_map = {0: 1, 1: 2, 2: 4, 3: 12, 4: 16}
        if stype in sz_map:
            val_sz = 0 if ptype == 3 else sz_map[stype]
        elif stype == 5:
            val_sz = buf[pos2]
            pos2 += 1
        elif stype == 6:
            val_sz = struct.unpack_from("<H", buf, pos2)[0]
            pos2 += 2
        elif stype == 7:
            val_sz = struct.unpack_from("<I", buf, pos2)[0]
            pos2 += 4
        else:
            raise ValueError(f"Bad stype {stype}")
        arr_idx = 0
        if arr_flag and ptype != 3:
            arr_idx, pos2 = read_ci(buf, pos2)
        val_raw = bytes(buf[pos2 : pos2 + val_sz])
        pos2 += val_sz
        out.append((pos, pos2, name, info, struct_name, arr_idx, val_raw))
        pos = pos2
    raise ValueError("Reached EOF without None terminator")


def find_defprop_span(pkg: UE2Package, export_1based: int, anchor_prop: str, target_prop: str) -> Tuple[int, int, int, str, int]:
    """Find [start, end] of target_prop in a UClass DefaultProperties block anchored by anchor_prop."""
    ex = pkg.exports[export_1based - 1]
    buf = pkg.raw[ex.serial_offset : ex.serial_offset + ex.serial_size]
    pat = write_ci(pkg.ensure_name(anchor_prop))
    idx = 0
    while True:
        idx = buf.find(pat, idx)
        if idx < 0:
            break
        try:
            props, end = parse_prop_stream(pkg, buf, idx)
            if end == len(buf):
                for st, en, name, info, sn, ai, _vr in props:
                    if name == target_prop:
                        return st, en, info, sn or "", ai
        except Exception:
            pass
        idx += 1
    raise KeyError(f"Property {target_prop} (anchor={anchor_prop}) not found in {pkg.obj_name(export_1based)}")


def patch_class_defprop_obj(
    pkg: UE2Package,
    cls_name: str,
    anchor_prop: str,
    target_prop: str,
    new_obj_ref: int,
) -> None:
    ei = pkg.find_export_ci(cls_name)
    assert ei is not None, f"Class {cls_name} not found"
    st, en, info, _sn, ai = find_defprop_span(pkg, ei, anchor_prop, target_prop)
    assert (info & 0x0F) == 5, f"{target_prop} not ObjectProperty (info={info:#x})"
    ex = pkg.exports[ei - 1]
    buf = bytearray(pkg.raw[ex.serial_offset : ex.serial_offset + ex.serial_size])
    repl = encode_prop_obj(pkg.ensure_name(target_prop), new_obj_ref, array_idx=ai)
    new_buf = bytes(buf[:st] + repl + buf[en:])
    # Verify stream integrity after patch
    parse_prop_stream(pkg, new_buf, st)
    pkg.replace_export_payload(ei, new_buf)


def clear_class_defprop_array(
    pkg: UE2Package,
    cls_name: str,
    anchor_prop: str,
    array_prop: str,
) -> None:
    """Replace an ArrayProperty's value with empty dynamic array (cnt=0)."""
    ei = pkg.find_export_ci(cls_name)
    assert ei is not None, f"Class {cls_name} not found"
    st, en, info, _sn, ai = find_defprop_span(pkg, ei, anchor_prop, array_prop)
    assert (info & 0x0F) == 9, f"{array_prop} not ArrayProperty (info={info:#x})"
    assert ai == 0
    ex = pkg.exports[ei - 1]
    buf = bytearray(pkg.raw[ex.serial_offset : ex.serial_offset + ex.serial_size])
    ni = pkg.ensure_name(array_prop)
    repl = write_ci(ni) + bytes([9 | (5 << 4), 1, 0])  # ArrayProperty, stype=5, size=1, count=0
    new_buf = bytes(buf[:st] + repl + buf[en:])
    parse_prop_stream(pkg, new_buf, st)
    pkg.replace_export_payload(ei, new_buf)


def null_class_struct_inner_obj(
    pkg: UE2Package,
    cls_name: str,
    anchor_prop: str,
    struct_prop: str,
    inner_prop: str,
) -> None:
    """Set an inner ObjectProperty inside every matching StructProperty (e.g. Bolton[k].StaticMesh = None)."""
    ei = pkg.find_export_ci(cls_name)
    assert ei is not None, f"Class {cls_name} not found"
    ex = pkg.exports[ei - 1]
    buf = bytearray(pkg.raw[ex.serial_offset : ex.serial_offset + ex.serial_size])
    pat = write_ci(pkg.ensure_name(anchor_prop))
    stream_start = -1
    idx = 0
    while True:
        idx = buf.find(pat, idx)
        if idx < 0:
            break
        try:
            _props, end = parse_prop_stream(pkg, buf, idx)
            if end == len(buf):
                stream_start = idx
                break
        except Exception:
            pass
        idx += 1
    assert stream_start >= 0, f"Anchor {anchor_prop} not found in {cls_name}"

    props, _end = parse_prop_stream(pkg, buf, stream_start)
    # Process in reverse offset order so earlier indices stay valid while splicing
    for st, en, name, info, _sn, _ai, _vr in reversed(props):
        if name != struct_prop:
            continue
        assert (info & 0x0F) == 10
        stype = (info >> 4) & 0x07
        assert stype == 5, f"Expected stype=5 on {struct_prop}"
        prop_bytes = bytes(buf[st:en])
        p = 0
        _, p = read_ci(prop_bytes, p)
        p += 1  # info
        _, p = read_ci(prop_bytes, p)  # struct_name
        sz_pos = p
        p += 1  # val_sz byte
        if (info & 0x80) != 0:
            _, p = read_ci(prop_bytes, p)  # arr_idx
        hdr_before_inner = prop_bytes[:p]
        inner_bytes = prop_bytes[p:]
        inner_props, inner_end = parse_prop_stream(pkg, inner_bytes, 0)
        assert inner_end == len(inner_bytes)
        patched_inner = None
        for ist, ien, iname, iinfo, _isn, iai, _ivr in inner_props:
            if iname == inner_prop:
                assert (iinfo & 0x0F) == 5
                irepl = encode_prop_obj(pkg.ensure_name(inner_prop), 0, array_idx=iai)
                patched_inner = inner_bytes[:ist] + irepl + inner_bytes[ien:]
                break
        if patched_inner is None:
            continue
        new_val_len = len(patched_inner)
        new_struct = (
            hdr_before_inner[:sz_pos]
            + bytes([new_val_len])
            + hdr_before_inner[sz_pos + 1 :]
            + patched_inner
        )
        buf = bytearray(buf[:st] + new_struct + buf[en:])
        parse_prop_stream(pkg, buf, stream_start)
    pkg.replace_export_payload(ei, bytes(buf))


def upsert_class_defprops(
    pkg: UE2Package,
    cls_name: str,
    anchor_prop: str,
    prop_bytes_list: List[Tuple[str, bytes]],
) -> None:
    """Replace existing DefaultProperties entries or insert new ones before the trailing None."""
    ei = pkg.find_export_ci(cls_name)
    assert ei is not None, f"Class {cls_name} not found"
    ex = pkg.exports[ei - 1]
    buf = bytearray(pkg.raw[ex.serial_offset : ex.serial_offset + ex.serial_size])
    pat = write_ci(pkg.ensure_name(anchor_prop))
    stream_start = -1
    idx = 0
    while True:
        idx = buf.find(pat, idx)
        if idx < 0:
            break
        try:
            _props, end = parse_prop_stream(pkg, buf, idx)
            if end == len(buf):
                stream_start = idx
                break
        except Exception:
            pass
        idx += 1
    assert stream_start >= 0, f"Anchor {anchor_prop} not found in {cls_name}"

    none_len = len(write_ci(pkg.ensure_name("None")))
    for pname, pbytes in prop_bytes_list:
        props, end = parse_prop_stream(pkg, buf, stream_start)
        assert end == len(buf)
        hit = next(((st, en) for st, en, n, *_rest in props if n == pname), None)
        if hit is not None:
            st, en = hit
            buf = bytearray(buf[:st] + pbytes + buf[en:])
        else:
            ins = len(buf) - none_len
            buf = bytearray(buf[:ins] + pbytes + buf[ins:])

    _props, end = parse_prop_stream(pkg, bytes(buf), stream_start)
    assert end == len(buf), (cls_name, end, len(buf))
    pkg.replace_export_payload(ei, bytes(buf))


def extract_mesh_anim_data(pkg: UE2Package, anim_name: str):
    """Parse a UE2 UMeshAnimation export into (iver, ref_bones, move_chunks, seqs)."""
    ei = pkg.find_export_ci(anim_name)
    assert ei is not None, f"MeshAnimation {anim_name} not found"
    ex = pkg.exports[ei - 1]
    buf = pkg.raw[ex.serial_offset : ex.serial_offset + ex.serial_size]
    pos = 0
    while True:
        ni, pos = read_ci(buf, pos)
        if pkg.names[ni][0] == "None":
            break
    iver = struct.unpack_from("<I", buf, pos)[0]
    pos += 4
    nb, pos = read_ci(buf, pos)
    ref_bones: List[Tuple[str, int, int]] = []
    for _ in range(nb):
        bni, pos = read_ci(buf, pos)
        flags, par = struct.unpack_from("<Ii", buf, pos)
        pos += 8
        ref_bones.append((pkg.names[bni][0], flags, par))

    nmoves, pos = read_ci(buf, pos)
    move_chunks: List[bytes] = []
    for _ in range(nmoves):
        mstart = pos
        pos += 24
        nbi, pos = read_ci(buf, pos)
        pos += nbi * 4
        nat, pos = read_ci(buf, pos)
        for _ in range(nat + 1):
            pos += 4
            nq, pos = read_ci(buf, pos)
            pos += nq * 16
            np_, pos = read_ci(buf, pos)
            pos += np_ * 12
            nt, pos = read_ci(buf, pos)
            pos += nt * 4
        move_chunks.append(bytes(buf[mstart:pos]))

    nseqs, pos = read_ci(buf, pos)
    seqs = []
    for idx in range(nseqs):
        f0 = struct.unpack_from("<f", buf, pos)[0]
        pos += 4
        sni, pos = read_ci(buf, pos)
        ng, pos = read_ci(buf, pos)
        grps = []
        for _ in range(ng):
            gi, pos = read_ci(buf, pos)
            grps.append(pkg.names[gi][0])
        sf, nf = struct.unpack_from("<ii", buf, pos)
        pos += 8
        nn, pos = read_ci(buf, pos)
        for _ in range(nn):
            pos += 4
            _, pos = read_ci(buf, pos)
            _, pos = read_ci(buf, pos)
        rate = struct.unpack_from("<f", buf, pos)[0]
        pos += 4
        seqs.append((idx, pkg.names[sni][0], f0, grps, sf, nf, rate))

    assert pos == len(buf), f"MeshAnimation {anim_name} trailing mismatch: {pos} != {len(buf)}"
    return iver, ref_bones, move_chunks, seqs


def build_cloned_mesh_anim_payload(
    pkg: UE2Package,
    src_anim_data,
    seq_mapping: List[Tuple[str, str]],
) -> bytes:
    """Serialize a custom UMeshAnimation containing remapped sequences cloned from src_anim_data."""
    iver, ref_bones, move_chunks, seqs = src_anim_data
    by_name = {s[1].lower(): s for s in seqs}

    out = bytearray()
    out.extend(write_ci(pkg.ensure_name("None")))
    out.extend(struct.pack("<I", iver))
    out.extend(write_ci(len(ref_bones)))
    for bname, flags, par in ref_bones:
        out.extend(write_ci(pkg.ensure_name(bname)))
        out.extend(struct.pack("<Ii", flags, par))

    out.extend(write_ci(len(seq_mapping)))
    for _dst_name, src_name in seq_mapping:
        idx = by_name[src_name.lower()][0]
        out.extend(move_chunks[idx])

    out.extend(write_ci(len(seq_mapping)))
    for dst_name, src_name in seq_mapping:
        _idx, _sn, f0, _grps, sf, nf, rate = by_name[src_name.lower()]
        assert sf == 0, f"Expected StartFrame=0 on {src_name}, got {sf}"
        out.extend(struct.pack("<f", f0))
        out.extend(write_ci(pkg.ensure_name(dst_name)))
        out.extend(write_ci(0))  # Groups=[]
        out.extend(struct.pack("<ii", sf, nf))
        out.extend(write_ci(0))  # Notifys=[]
        out.extend(struct.pack("<f", rate))
    return bytes(out)
