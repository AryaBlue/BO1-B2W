"""WaW lightmap pages for the T6 world.

A WaW lightmap page is two textures (measured on the dumped world programs):
  * secondary, W x 2H RGBA8: top half colour A + direction x in alpha, bottom
    half colour B + direction y in alpha. ``lm_*`` pixel programs sample it at
    (u, v/2) and (u, v/2 + 1/2).
  * primary, 2W x 2H L8: sun visibility, sampled at (u, v) by sun programs.

A T6 page is one W x 3H RGBA8 texture of three stacked pages, bound as
``lightmapSamplerSecondary`` (measured on stock world lit programs):
  1. ambient, decoded rgb / (a + 1e-6), linear
  2. directional colour, decoded the same way
  3. direction * 0.5 + 0.5 in rgb, sun visibility in alpha
Final T6 colour = sqrt(hdr * (albedo^2 * lighting + ...)); WaW writes
albedo * lighting in gamma space.

Two encodings of each page are produced:
  * WaW-encoded: [secondary top, secondary bottom, primary] stacked in T6's
    shape; translated WaW programs sample it through an exact UV remap
    (``WAW_PAGE_UV``). The primary is box-filtered to the W x H layer size
    (reported: sun shadow detail at half resolution).

BO1 (T5) pages differ (measured on ps_pimp_shader_layer_lmap_* of zombie_theater):
  * secondary, W x 2H R5G6B5 (D3D format 23): top half A, bottom half B; per texel
    .x / .z = red / blue share, .y = one direction component (A: x, B: y, decoded * 4 - 2).
  * secondaryB, W x H G16R16 (format 34): .x / .y = brightness of A / B (* 31.875).
    Colour = brightness * (4 red, 2 (1 - red - blue), 4 blue): equal shares of 0.25 are grey.
  * primary, 2W x H L8: sun visibility (.y).
  Lighting = A + B * (0.6 exp(-|d|^2) + 0.4) at a flat normal, already linear (BO1 multiplies
  albedo^2 like T6), so the T6 page takes it without squaring. OAT has no loader for formats
  23 / 34: the dumper writes their raw pixels as <image>.loaddef.bin (int32 format, size,
  width, height, depth, flags, then the pixels).
  * T6-encoded, for surfaces still drawn by T6 donor programs: ambient =
    WaW's own lighting at a flat normal, squared into T6's linear units
    (hdrControl0.x assumed 1), directional colour 0, sun visibility from the
    primary. Bump-dependent WaW lighting is not representable there
    (reported as an approximation).
"""
from __future__ import annotations

import json
import os
import math
import struct
from pathlib import Path

from . import iwi

# WaW sampler -> (scale, offset) applied to v inside the WaW-encoded page.
WAW_PAGE_UV = {
    'lightmapSamplerSecondary': (2.0 / 3.0, 0.0),
    'lightmapSamplerPrimary': (1.0 / 3.0, 2.0 / 3.0),
}
# BO1 secondaryB (G16R16 brightness) in the WaW-layout page of build_page_t5:
# high bytes in the alpha of thirds A / B, low bytes in .z / .w of the third.
# Filtering is linear, so hi * 256 + lo of filtered bytes is the filtered word.
T5_BRIGHTNESS_TAPS = ((1.0 / 3.0, 0.0), (1.0 / 3.0, 1.0 / 3.0), (1.0 / 3.0, 2.0 / 3.0))
T5_BRIGHTNESS_TEXEL = ('float4((T0.w * 65280.0 + T2.z * 255.0) / 65535.0, '
                       '(T1.w * 65280.0 + T2.w * 255.0) / 65535.0, 1.0, 1.0)')
PAGE_SAMPLERS = {*WAW_PAGE_UV, 'lightmapSamplerSecondaryB'}
# WaW lm_* direction decode, per alpha pair (measured literal c1 of the programs)
_DIR_SCALE = (4.07999992, 4.06451607)
_DIR_BIAS = (-2.07999992, -2.06451607)


class LightmapError(ValueError):
    pass


def _rgba(path: Path) -> tuple[int, int, bytes]:
    img = iwi.read_dds(path.read_bytes())
    level = iwi._convert_pixels(img, iwi._split_levels(img)[0])
    if img.iwi_format == iwi.FMT_RGBA:
        return img.width, img.height, level
    if img.iwi_format == iwi.FMT_LUMINANCE:
        out = bytearray(len(level) * 4)
        for c in range(3):
            out[c::4] = level
        out[3::4] = level
        return img.width, img.height, bytes(out)
    if img.iwi_format in (iwi.FMT_DXT1, iwi.FMT_DXT3, iwi.FMT_DXT5):
        # BO1 sun visibility pages are DXT1
        from PIL import Image
        with Image.open(path) as dds:
            return dds.width, dds.height, dds.convert('RGBA').tobytes()
    raise LightmapError(f'{path.name}: unsupported lightmap pixel format {img.iwi_format}')


def _box_luminance(width: int, height: int, rgba: bytes, out_w: int, out_h: int, channel: int = 0) -> bytes:
    """Average one channel (default red) down to out_w x out_h (integer factor)."""
    fx, fy = width // out_w, height // out_h
    if fx * out_w != width or fy * out_h != height:
        raise LightmapError('primary lightmap is not an integer multiple of the page size')
    red = rgba[channel::4]
    out = bytearray(out_w * out_h)
    n = fx * fy
    for y in range(out_h):
        rows = [red[(y * fy + j) * width:(y * fy + j + 1) * width] for j in range(fy)]
        for x in range(out_w):
            s = 0
            for row in rows:
                s += sum(row[x * fx:(x + 1) * fx])
            out[y * out_w + x] = (s + n // 2) // n
    return bytes(out)


def _iwi_rgba(width: int, height: int, data: bytes) -> bytes:
    out = bytearray(b'IWi' + bytes([27]))
    out += struct.pack('<bbHHHf', iwi.FMT_RGBA, iwi.FLAG_NOMIPMAPS, width, height, 1, 0.0)
    out += bytes(16)
    out += struct.pack('<8I', 64 + len(data), *([0] * 7))
    return bytes(out + data)


def _flat_weight_table() -> list[float]:
    """0.6 * exp(-|d|^2) + 0.4 for every (top alpha, bottom alpha) byte pair."""
    table = [0.0] * 65536
    for a in range(256):
        dx = a / 255.0 * _DIR_SCALE[0] + _DIR_BIAS[0]
        for b in range(256):
            dy = b / 255.0 * _DIR_SCALE[1] + _DIR_BIAS[1]
            table[a * 256 + b] = 0.6 * math.exp(-(dx * dx + dy * dy)) + 0.4
    return table


def build_page(secondary: Path, primary: Path | None) -> tuple[int, int, bytes, bytes]:
    """(layer width, layer height, WaW RGBA, T6 RGBA) for one WaW page."""
    sw, sh, sec = _rgba(secondary)
    if sw <= 0 or sh <= 0 or sh % 2:
        raise LightmapError(f'{secondary.name}: expected two equal stacked secondary lightmap layers, got {sw}x{sh}')
    height = sh // 2
    pixels = sw * height
    half = pixels * 4
    top, bottom = sec[:half], sec[half:]
    if primary is not None:
        pw, ph, pri = _rgba(primary)
        vis = _box_luminance(pw, ph, pri, sw, height)
    else:
        vis = bytes([255]) * pixels
    third = bytearray(pixels * 4)
    for c in range(3):
        third[c::4] = vis
    third[3::4] = vis
    waw = top + bottom + bytes(third)

    weights = _flat_weight_table()
    ambient = bytearray(pixels * 4)
    ta, ba = top[3::4], bottom[3::4]
    for i in range(pixels):
        w = weights[ta[i] * 256 + ba[i]]
        p = i * 4
        light = [(top[p + c] + bottom[p + c] * w) / 255.0 for c in range(3)]
        linear = [v * v for v in light]  # T6 squares; WaW lighting is gamma
        peak = max(1.0, max(linear))
        for c in range(3):
            ambient[p + c] = min(255, int(round(linear[c] / peak * 255.0)))
        ambient[p + 3] = min(255, max(1, int(round(255.0 / peak))))
    directional = bytes([0, 0, 0, 255]) * pixels
    direction = bytearray(pixels * 4)
    direction[0::4] = bytes([128]) * pixels
    direction[1::4] = bytes([128]) * pixels
    direction[2::4] = bytes([255]) * pixels
    direction[3::4] = vis
    t6 = bytes(ambient) + directional + bytes(direction)
    return sw, height, waw, t6


T5_SECONDARY_FORMAT, T5_SECONDARY_B_FORMAT = 23, 34      # D3DFMT_R5G6B5, D3DFMT_G16R16
T5_BRIGHTNESS = 31.875


def _loaddef(path: Path, expected_format: int) -> tuple[int, int, bytes]:
    fmt, size, width, height, _depth, _flags = struct.unpack_from('<6i', path.read_bytes())
    if fmt != expected_format:
        raise LightmapError(f'{path.name}: D3D format {fmt}, expected {expected_format}')
    data = path.read_bytes()[24:24 + size]
    bpp = 2 if fmt == T5_SECONDARY_FORMAT else 4
    if len(data) != size or size < width * height * bpp:
        raise LightmapError(f'{path.name}: {len(data)} bytes for {width}x{height}')
    return width, height, data[:width * height * bpp]


def build_page_t5(secondary: Path, secondary_b: Path, primary: Path | None) -> tuple[int, int, bytes, bytes]:
    """(layer width, layer height, WaW-layout RGBA, T6 RGBA) for one BO1 page (see the module docstring).
    WaW layout here: thirds A / B as (red share, direction, blue share, brightness high byte) and a third
    (visibility, visibility, brightness A low byte, brightness B low byte)."""
    sw, sh, sec = _loaddef(secondary, T5_SECONDARY_FORMAT)
    bw, bh, sec_b = _loaddef(secondary_b, T5_SECONDARY_B_FORMAT)
    if sh % 2 or (bw, bh) != (sw, sh // 2):
        raise LightmapError(f'{secondary.name}: {sw}x{sh} secondary does not match {bw}x{bh} secondaryB')
    width, height = sw, sh // 2
    pixels = width * height
    words = struct.unpack(f'<{pixels * 2}H', sec)
    scales = struct.unpack(f'<{pixels * 2}H', sec_b)        # per texel: A (.x, low word), B (.y, high word)
    if primary is not None:
        pw, ph, pri = _rgba(primary)
        vis = _box_luminance(pw, ph, pri, width, height, channel=1)   # BO1 reads .y (DXT1 green)
    else:
        vis = bytes([255]) * pixels
    waw = bytearray(pixels * 12)
    ambient = bytearray(pixels * 4)
    for i in range(pixels):
        dirs = []
        for half in (0, 1):
            v = words[half * pixels + i]
            red, d, blue = (v >> 11) / 31.0, ((v >> 5) & 63) / 63.0, (v & 31) / 31.0
            raw = scales[2 * i + half]
            o = half * pixels * 4 + i * 4
            waw[o:o + 4] = bytes(((v >> 11) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31, raw >> 8))
            dirs.append(d * 4.0 - 2.0)
            bright = raw / 65535.0 * T5_BRIGHTNESS
            colour = (4.0 * red * bright, 2.0 * max(0.0, 1.0 - red - blue) * bright, 4.0 * blue * bright)
            if half == 0:
                top = colour
            else:
                bottom = colour
        weight = 0.6 * math.exp(-(dirs[0] * dirs[0] + dirs[1] * dirs[1])) + 0.4
        light = [top[c] + bottom[c] * weight for c in range(3)]
        o = pixels * 8 + i * 4
        waw[o:o + 4] = bytes((vis[i], vis[i], scales[2 * i] & 255, scales[2 * i + 1] & 255))
        peak = max(1.0, max(light))
        p = i * 4
        for c in range(3):
            ambient[p + c] = min(255, int(round(light[c] / peak * 255.0)))
        ambient[p + 3] = min(255, max(1, int(round(255.0 / peak))))
    directional = bytes([0, 0, 0, 255]) * pixels
    direction = bytearray(pixels * 4)
    direction[0::4] = bytes([128]) * pixels
    direction[1::4] = bytes([128]) * pixels
    direction[2::4] = bytes([255]) * pixels
    direction[3::4] = vis
    return width, height, bytes(waw), bytes(ambient) + directional + bytes(direction)


def _stage_page(task):
    index, secondary, primary, project_root, secondary_b = task
    if secondary_b is not None:
        width, height, waw, t6 = build_page_t5(secondary, secondary_b, primary)
    else:
        width, height, waw, t6 = build_page(secondary, primary)
    names = {'waw': f'lightmap{index}_waw_secondary', 't6': f'lightmap{index}_t6_secondary'}
    for key, data in (('waw', waw), ('t6', t6)):
        if os.environ.get('WAW2BO2_DIAG_PAGEID'):
            # Diagnostic build: a 4x4 code in the page's last texels
            # (red = page index, blue = WaW-encoded, green = T6-encoded).
            palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 255, 255)]
            code = bytes([*(palette[index % 5] if key == 'waw' else (255, 0, 255)), 255])
            data = bytearray(data)
            for y in range(max(0, height * 3 - 4), height * 3):
                for x in range(max(0, width - 4), width):
                    o = (y * width + x) * 4
                    data[o:o + 4] = code
            data = bytes(data)
        dst = project_root / 'images' / f'{names[key]}.iwi'
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(_iwi_rgba(width, height * 3, data))
    return {'index': index, 'width': width, 'height': height, **names}


def stage(world, image_roots: list[Path], project_root: Path, waw_materials: set[str]) -> dict:
    """Write both encodings of every lightmap page the world uses.

    ``waw_materials``: materials whose lit passes are translated WaW programs
    reading WaW-encoded pages. Writes images/<name>.iwi and BSP/lightmaps.json:
    {"pages": [{"waw": img, "t6": img}], "wawMaterials": [...]} - the linker
    gives a surface page i for WaW materials and page count + i otherwise.
    """
    report = {'pages': [], 'warnings': [], 'errors': []}
    pages = []

    def find(index, kind, suffix='.dds'):
        name = f'_lightmap{index}_{kind}{suffix}'
        return next((r / name for r in image_roots if (r / name).exists()), None)

    # BO1 pages: secondary + secondaryB raw dumps (formats OAT cannot load, see the module docstring)
    t5 = find(0, 'secondary') is None and find(0, 'secondary', '.loaddef.bin') is not None
    if t5:
        base_find = find
        find = lambda index, kind: base_find(index, kind, '.dds' if kind == 'primary' else '.loaddef.bin')

    # WaW lightmap pages are *lightmap0.. up to the world's lightmap count; a
    # surface index past them (31 on the measured map) means "no lightmap".
    count = 0
    while find(count, 'secondary') is not None:
        count += 1
    used = {s.lightmap_index for s in world.surfaces}
    unlit = sum(1 for s in world.surfaces if s.lightmap_index >= count)
    if unlit:
        report['warnings'].append(f'{unlit} surfaces have no lightmap page (WaW index >= {count}: '
                                  f'{sorted(i for i in used if i >= count)})')
    tasks = []
    for index in range(count):
        secondary, primary = find(index, 'secondary'), find(index, 'primary')
        if primary is None:
            report['warnings'].append(f'lightmap page {index}: primary (sun visibility) absent; fully visible')
        secondary_b = find(index, 'secondaryb') if t5 else None
        if t5 and secondary_b is None:
            report['errors'].append(f'lightmap page {index}: BO1 secondaryB (brightness) absent')
            continue
        tasks.append((index, secondary, primary, project_root, secondary_b))
    from .parallel import ordered_map
    for result in ordered_map(_stage_page, tasks, label='Lightmaps', processes=True):
        pages.append({key: result[key] for key in ('waw', 't6')})
        report['pages'].append(result)
    bsp = project_root / 'BSP'
    bsp.mkdir(parents=True, exist_ok=True)
    (bsp / 'lightmaps.json').write_text(json.dumps({'pages': pages, 'wawMaterials': sorted(waw_materials)}, indent=1) + '\n',
                                        encoding='utf-8')
    if pages:
        report['warnings'].append('lightmap sun visibility (WaW primary) box-filtered to the secondary page resolution')
        if t5:
            report['warnings'].append('BO1 lightmaps decoded (R5G6B5 + G16R16 brightness) for T6 programs; translated '
                                      'BO1 programs reading lightmapSamplerSecondaryB are not adapted yet')
        if len(waw_materials) < len({s.material for s in world.surfaces if s.lightmap_index < count}):
            report['warnings'].append('APPROXIMATED lightmaps for T6 donor materials: WaW flat-normal lighting, no '
                                      'directional term, hdrControl0.x assumed 1')
    return report
