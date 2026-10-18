"""Desktop-authored menu artwork, using the measured T6 menu canvases."""
from __future__ import annotations

import io
import json
import warnings
from functools import lru_cache
from pathlib import Path
from PIL import Image
from .iwi import dds_to_iwi

SIZES = {'blit': (512, 256), 'large': (2048, 2048), 'blur': (2048, 2048)}
# Uncompressed RGBA made each 2048 backdrop 16 MB and failed allocation in T6.
MAX_TEXTURE_BYTES = 16 * 1024 * 1024


def read_art(path: str, role: str, *, check_size: bool = True) -> Image.Image:
    with Image.open(path) as source:
        if check_size and source.size != SIZES[role]:
            w, h = SIZES[role]
            warnings.warn(f'{role.title()} differs from the stock {w} × {h} canvas; it will be resized for export.', UserWarning, stacklevel=2)
        image = source.convert('RGBA')
    if role == 'blit' and image.getextrema()[3][0] == 255:
        raise ValueError('Blit needs a transparent background. Choose a PNG or TGA with alpha transparency.')
    return image


def artwork_layout(images: dict[str, Image.Image]) -> str:
    if len({image.size for image in images.values()}) == 1:
        return 'aligned'
    if all(images[role].size == size for role, size in SIZES.items()):
        return 'stock'
    return 'aligned'


def artwork_warning(images: dict[str, Image.Image]) -> str | None:
    if len({image.size for image in images.values()}) == 1 or artwork_layout(images) == 'stock':
        return None
    return ('Layer canvas sizes differ. They will be resized to the same canvas, but objects may not line up '
            'and the result may look distorted. You can still preview and build.')


def load_artwork(settings) -> dict[str, Image.Image]:
    images = {role: read_art(getattr(settings, 'menu_' + role), role, check_size=False) for role in SIZES}
    artwork_layout(images)
    return images


def composite_art(images: dict[str, Image.Image], *, blurred: bool = False) -> Image.Image:
    background = images['blur' if blurred else 'large'].copy()
    if artwork_layout(images) == 'aligned':
        # Use Large as the preview canvas, matching the normalized full-frame export.
        background = background.resize(images['large'].size, Image.Resampling.LANCZOS)
        background.alpha_composite(images['blit'].resize(background.size, Image.Resampling.LANCZOS))
    else:
        background.alpha_composite(images['blit'].resize((320, 284), Image.Resampling.LANCZOS), (864, 882))
    return background


def validate_art(settings) -> None:
    paths = [getattr(settings, 'menu_' + role) for role in SIZES]
    if any(paths):
        if not all(paths):
            raise ValueError('Choose all three images: Blit, Large, and Blur.')
        warning = _validate_files(tuple((path, Path(path).stat().st_mtime_ns, Path(path).stat().st_size) for path in paths))
        if warning:
            warnings.warn(warning, UserWarning, stacklevel=2)


@lru_cache(maxsize=24)
def _validate_files(files):
    return artwork_warning({role: read_art(path, role, check_size=False) for role, (path, _, _) in zip(SIZES, files)})


def material(image: str) -> dict:
    # Native T6 2D material: straight alpha, clamped linear sampling, no mips.
    return {'_game': 't6', '_type': 'material', '_version': 1,
            'cameraRegion': 'none', 'constants': [], 'contents': 1, 'gameFlags': [],
            'layeredSurfaceTypes': 536870912, 'sortKey': 40,
            'stateBits': [{'alphaTest': 'gt0', 'blendOpAlpha': 'add', 'blendOpRgb': 'add',
                           'colorWriteAlpha': True, 'colorWriteRgb': True, 'cullFace': 'back',
                           'depthTest': 'disabled', 'depthWrite': False, 'dstBlendAlpha': 'one',
                           'dstBlendRgb': 'invsrcalpha', 'polygonOffset': 'offset0',
                           'polymodeLine': False, 'srcBlendAlpha': 'invdestalpha', 'srcBlendRgb': 'srcalpha'}],
            'stateBitsEntry': [-1, -1, 0] + [-1] * 33,
            'stateFlags': 0, 'surfaceFlags': 0, 'surfaceTypeBits': 0,
            'techniqueSet': 'trivial_9z33feqw', 'textureAtlas': {'columns': 1, 'rows': 1},
            'textures': [{'image': image, 'isMatureContent': False, 'name': 'colorMap',
                          'samplerState': {'clampU': True, 'clampV': True, 'clampW': True,
                                           'filter': 'linear', 'mipMap': 'disabled'}, 'semantic': '2D'}]}


def compressed_iwi(image: Image.Image, pixel_format: str) -> bytes:
    """Single-level block-compressed IWI27 (menus draw at a fixed size)."""
    if pixel_format not in ('DXT1', 'DXT5'):
        raise ValueError('Menu textures must use DXT1 or DXT5.')
    if pixel_format == 'DXT1' and image.convert('RGBA').getextrema()[3][0] < 255:
        raise ValueError('Transparent menu textures require DXT5.')
    expected = ((image.width + 3) // 4) * ((image.height + 3) // 4) * (8 if pixel_format == 'DXT1' else 16) + 64
    if expected >= MAX_TEXTURE_BYTES:
        raise ValueError('Each menu texture must be smaller than 16 MiB.')
    dds = io.BytesIO()
    image.convert('RGB' if pixel_format == 'DXT1' else 'RGBA').save(dds, 'DDS', pixel_format=pixel_format)
    pixels = dds_to_iwi(dds.getvalue())
    from .iwi import read_iwi_header, FMT_DXT1, FMT_DXT5
    header = read_iwi_header(pixels)
    if header['format'] != (FMT_DXT1 if pixel_format == 'DXT1' else FMT_DXT5) or len(pixels) != expected:
        raise ValueError('Unexpected menu texture encoding or size.')
    return pixels


def stage_art(settings, root: Path) -> None:
    validate_art(settings)
    from .mapmenu import validate_settings, stage_song
    coordinates = validate_settings(settings)
    metadata = root / 'menu.json'
    previous = json.loads(metadata.read_text(encoding='utf-8')) if metadata.is_file() else {}
    if previous.get('desktop_authored'):
        for name in previous.get('desktop_files', []):
            # Only direct generated image/material children may be removed.
            relative = Path(name)
            if len(relative.parts) == 2 and relative.parts[0] in ('images', 'materials') and relative.suffix in ('.iwi', '.json'):
                (root / relative).unlink(missing_ok=True)
        from .menulayers import clear_runtime
        clear_runtime(root, previous)
    if not any((settings.menu_title, settings.menu_description, getattr(settings, 'menu_mode', ''),
                getattr(settings, 'menu_location', ''), settings.menu_blit, settings.loading_song, any(coordinates))):
        # Remove only metadata previously created by this launcher.
        stage_song(settings, root)
        if previous.get('desktop_authored'):
            metadata.unlink()
        return
    root.mkdir(parents=True, exist_ok=True)
    # Always emit branding, including text-only/default builds. The stock UI
    # synthesizes location/mode keys even when no artwork was uploaded.
    data = {**{k: v for k, v in previous.items() if k not in
               ('icon', 'blit', 'desktop_files', 'loading_song', 'layer_layout', 'layer_rawfiles', 'layer_materials', 'texture_report')},
            'title': settings.menu_title.strip() or settings.project,
            'description': settings.menu_description.strip() or f'{settings.project}: World at War custom map',
            'longitude': coordinates[0], 'latitude': coordinates[1],
            'desktop_authored': True}
    for key in ('mode', 'location'):
        if getattr(settings, 'menu_' + key, ''):
            data[key] = getattr(settings, 'menu_' + key)
    generated = []
    if settings.menu_blit:
        images = load_artwork(settings)
        aligned = artwork_layout(images) == 'aligned'
        complete = composite_art(images)
        if aligned:
            # Bake both menu states. Stock maps stream one full-screen map image
            # at a time; a separately streamed full-canvas Blit showed unfocused
            # but vanished on focus, leaving Blur's cutout black. Map is
            # Large + Blit; Map Blur is the focused view, sharp Blit over Blur.
            images = {'large': complete, 'blur': composite_art(images, blurred=True), 'blit': images['blit']}
            images = {role: image.resize((2048, 2048), Image.Resampling.LANCZOS) for role, image in images.items()}
            images['location'] = Image.new('RGBA', (512, 256))
        images['complete'] = complete.resize((2048, 2048), Image.Resampling.LANCZOS)
        images['icon'] = complete.resize((256, 256), Image.Resampling.LANCZOS)
        bindings = {'map': 'large', 'map_blur': 'blur', 'blit': 'blit', 'icon': 'icon',
                    'zclassic_default': 'complete'}
        bindings.update({'loadscreen:' + suffix: 'complete' for suffix in ('zclassic_default', 'zclassic_')})
        if aligned:
            # Names read back through gametypestable lookups must fit a 32-byte
            # buffer: menu_<project>_location (32 here) was cut short and drew
            # the default checkerboard material.
            bindings['loc'] = 'location'
        for folder in ('materials', 'images'):
            (root / folder).mkdir(parents=True, exist_ok=True)
        report = {}
        for role, image in images.items():
            fmt = 'DXT5' if image.getextrema()[3][0] < 255 or role in ('blit', 'icon') else 'DXT1'
            pixels = compressed_iwi(image, fmt)
            (root / 'images' / f'menu_{settings.project}_{role}.iwi').write_bytes(pixels)
            report[role] = {'format': fmt, 'bytes': len(pixels), 'width': image.width, 'height': image.height}
            generated.append(f'images/menu_{settings.project}_{role}.iwi')
        for suffix, role in bindings.items():
            name = (f'loadscreen_{settings.project}_' + suffix.split(':')[1] if ':' in suffix
                    else f'menu_{settings.project}_{suffix}')
            (root / 'materials' / (name + '.json')).write_text(json.dumps(material(f'menu_{settings.project}_{role}'), indent=2), encoding='utf-8')
            generated.append(f'materials/{name}.json')
        data.update(icon=f'menu_{settings.project}_icon', blit=f'menu_{settings.project}_blit')
        data['texture_report'] = report
        if aligned:
            from .menulayers import stage_runtime
            data.update(stage_runtime(Path(settings.bo2), root, settings.project))
    data['desktop_files'] = generated
    song = stage_song(settings, root)
    if song:
        data['loading_song'] = song
    metadata.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
