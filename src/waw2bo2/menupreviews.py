"""Approximate in-game renders of a converted map's menu art, for the launcher.

Everything is drawn in BO2's 1280 x 720 menu space and scaled at the end. The
stock textures (globe, signpost plank, lobby frame) are read from the user's
own BO2 install (raw/images) when available; nothing from the game ships with
the tool. Layout numbers come from the stock menus:

* Map selection: aligned artwork fills the frame; the start-location box is
  400 x 200 (SelectStartLocZombie) centred at the Blit point, the option list
  (map name, description) at the location's option offset (+180, -50).
* Lobby: CoD.MapInfoImage frame 294 x 182 (MapImageWidth x MapImageHeight +
  the 46-unit name strip); converted maps fill all of it (menupreview).
* Globe: mapstable longitude/latitude in BO2's own convention, which is
  geographic longitude with the sign flipped (zm_prison 122 = San Francisco,
  zm_tomb -11 = northern France).
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .menuart import START_BOX, blit_window, composite_art, fit_aspect

SCREEN = (1280, 720)
LOBBY_FRAME = (294, 182)
ORANGE = (236, 114, 27)
OFF_WHITE = (226, 226, 220)

_FONT_CACHE: dict = {}
_TEXTURE_CACHE: dict = {}


def font(size: int, bold: bool = True) -> ImageFont.ImageFont:
    """A condensed display face close to BO2's menu font (Bahnschrift on Windows)."""
    key = (size, bold)
    if key not in _FONT_CACHE:
        face = None
        for name, variation in (('bahnschrift.ttf', 'Bold SemiCondensed' if bold else 'SemiCondensed'),
                                ('impact.ttf', None), ('arialbd.ttf' if bold else 'arial.ttf', None)):
            try:
                face = ImageFont.truetype(name, size)
                if variation:
                    try:
                        face.set_variation_by_name(variation)
                    except (OSError, ValueError, AttributeError):
                        pass
                break
            except OSError:
                continue
        _FONT_CACHE[key] = face or ImageFont.load_default()
    return _FONT_CACHE[key]


def stock_texture(bo2: str | Path | None, name: str) -> Image.Image | None:
    """A BO2 raw image (e.g. globe_map_zm), or None when the install lacks it."""
    if not bo2:
        return None
    path = Path(bo2) / 'raw' / 'images' / f'{name}.dds'
    key = str(path)
    if key not in _TEXTURE_CACHE:
        try:
            _TEXTURE_CACHE[key] = Image.open(path).convert('RGBA')
        except (OSError, ValueError):
            _TEXTURE_CACHE[key] = None
    return _TEXTURE_CACHE[key]


def _parse_point(text: str) -> tuple[float, float] | None:
    try:
        x, y = (float(v) for v in text.split(','))
        return x, y
    except (ValueError, AttributeError):
        return None


def _wrap(draw: ImageDraw.ImageDraw, text: str, face, width: int) -> list[str]:
    lines, line = [], ''
    for word in text.split():
        trial = (line + ' ' + word).strip()
        if line and draw.textlength(trial, font=face) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + ([line] if line else [])


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return fit_aspect(image.convert('RGBA'), size[0] / size[1]).resize(size, Image.Resampling.LANCZOS)


def _placeholder(size: tuple[int, int], text: str) -> Image.Image:
    image = Image.new('RGBA', size, (21, 26, 32, 255))
    draw = ImageDraw.Draw(image)
    face = font(28, False)
    lines = _wrap(draw, text, face, size[0] - 120)
    y = size[1] // 2 - 20 * len(lines)
    for line in lines:
        draw.text((size[0] // 2, y), line, fill=(171, 184, 195), font=face, anchor='mt')
        y += 40
    return image


# ---------------------------------------------------------------- map selection

def map_selection(images: dict[str, Image.Image], title: str, description: str, *,
                  focused: bool = False, point: str = '') -> Image.Image:
    """The Change Map screen after the globe zooms in on the map."""
    if not all(role in images for role in ('blit', 'large', 'blur')):
        return _placeholder(SCREEN, 'Upload Blit, Large and Blur to preview the map selection screen.')
    screen = _cover(composite_art(images, blurred=focused), SCREEN)
    draw = ImageDraw.Draw(screen)
    blit = images['blit'].convert('RGBA')
    aligned = len({image.size for image in images.values()}) == 1
    if aligned:
        center, _crop = blit_window(blit, _parse_point(point))
    else:
        center = [0, 0]
    x, y = SCREEN[0] // 2 + center[0], SCREEN[1] // 2 + center[1]
    box = (x - START_BOX[0] // 2, y - START_BOX[1] // 2, x + START_BOX[0] // 2, y + START_BOX[1] // 2)
    if not focused:
        # The selected location's image pulses over the art; outline it.
        glow = Image.new('RGBA', SCREEN, (0, 0, 0, 0))
        ImageDraw.Draw(glow).rectangle(box, outline=(255, 170, 60, 200), width=6)
        screen.alpha_composite(glow.filter(ImageFilter.GaussianBlur(6)))
        draw.rectangle(box, outline=(255, 190, 90, 230), width=2)
    # Option list at the row's option position (gametypestable columns 10/11:
    # the location point + (180, -50), centre-anchored): "[TITLE]" in orange
    # brackets, then the description.
    left = min(max(SCREEN[0] // 2 + center[0] + 180, 20), SCREEN[0] - 360)
    top = min(max(SCREEN[1] // 2 + center[1] - 50, 20), SCREEN[1] - 160)
    name = font(30)
    label = title.upper()
    width = draw.textlength(label, font=name)
    draw.rectangle((left - 6, top - 4, left + width + 6, top + 38), outline=ORANGE, width=2)
    draw.text((left, top), label, fill=ORANGE, font=name)
    text = font(24, False)
    for index, line in enumerate(_wrap(draw, description, text, 320)[:4]):
        if index == 0:
            draw.polygon(((left + 2, top + 58), (left + 2, top + 72), (left + 10, top + 65)), fill=OFF_WHITE)
        draw.text((left + 18, top + 50 + index * 28), line, fill=OFF_WHITE, font=text)
    draw.text((210, 672), 'ESC', fill=(232, 178, 64), font=font(26))
    draw.text((262, 672), 'Back', fill=OFF_WHITE, font=font(26, False))
    return screen.convert('RGB')


def screen_to_canvas(images: dict[str, Image.Image], point: tuple[float, float]) -> tuple[int, int] | None:
    """A map-selection screen point (1280 x 720) -> aligned Blit canvas pixels,
    the inverse of map_selection's cover crop. None for stock-layout art."""
    if not all(role in images for role in ('blit', 'large', 'blur')) or len({i.size for i in images.values()}) != 1:
        return None
    width, height = images['large'].size
    aspect = SCREEN[0] / SCREEN[1]
    if width / height > aspect:
        keep = round(height * aspect)
        left, top, crop_w, crop_h = (width - keep) // 2, 0, keep, height
    else:
        keep = round(width / aspect)
        left, top, crop_w, crop_h = 0, (height - keep) // 2, width, keep
    x = left + point[0] / SCREEN[0] * crop_w
    y = top + point[1] / SCREEN[1] * crop_h
    return round(min(max(x, 0), width - 1)), round(min(max(y, 0), height - 1))


# ------------------------------------------------------------------- lobby card

def lobby(images: dict[str, Image.Image], preview: Image.Image | None, title: str, mode: str,
          bo2: str | Path | None = None) -> Image.Image:
    """The Custom Games lobby map preview, enlarged, over the blurred map art."""
    if 'large' in images:
        backdrop = _cover(composite_art(images, blurred=True) if all(r in images for r in ('blit', 'large', 'blur'))
                          else images['large'], SCREEN)
    else:
        backdrop = Image.new('RGBA', SCREEN, (28, 32, 36, 255))
    screen = backdrop.copy()
    screen.alpha_composite(Image.new('RGBA', SCREEN, (0, 0, 0, 110)))
    draw = ImageDraw.Draw(screen)
    draw.text((205, 40), 'CUSTOM GAMES', fill=(240, 240, 236), font=font(54))
    for index, line in enumerate(('START MATCH', 'MAP', '', 'DIFFICULTY', 'STARTING ROUND')):
        draw.text((205, 100 + index * 32), line, fill=(240, 240, 236), font=font(26))
    scale = 1.45
    frame = (round(LOBBY_FRAME[0] * scale), round(LOBBY_FRAME[1] * scale))
    origin = (212, SCREEN[1] - 60 - frame[1])
    picture = preview if preview is not None else (composite_art(images) if all(r in images for r in ('blit', 'large', 'blur')) else None)
    card = _cover(picture, frame) if picture is not None else _placeholder(frame, 'Upload a lobby preview')
    border = stock_texture(bo2, 'menu_zm_map_frame')
    if border is not None:
        card.alpha_composite(border.resize(frame, Image.Resampling.LANCZOS))
    else:
        shade = Image.new('RGBA', frame, (0, 0, 0, 0))
        ImageDraw.Draw(shade).rectangle((0, frame[1] - round(46 * scale), frame[0], frame[1]), fill=(0, 0, 0, 120))
        card.alpha_composite(shade)
        ImageDraw.Draw(card).rectangle((0, 0, frame[0] - 1, frame[1] - 1), outline=(150, 150, 150), width=3)
    face = font(27)
    card_draw = ImageDraw.Draw(card)
    for index, line in enumerate((title.upper(), (mode or title).upper())):
        card_draw.text((frame[0] - 16, frame[1] - 64 + index * 28), line, fill=(245, 245, 240), font=face, anchor='ra')
    screen.alpha_composite(card, origin)
    return screen.convert('RGB')


# --------------------------------------------------------------- loading screen

def loading(images: dict[str, Image.Image], art: Image.Image | None, title: str, location: str) -> Image.Image:
    picture = art if art is not None else (composite_art(images) if all(r in images for r in ('blit', 'large', 'blur')) else None)
    if picture is None:
        return _placeholder(SCREEN, 'Upload a loading screen image (or Blit, Large and Blur).')
    screen = _cover(picture, SCREEN)
    shade = Image.new('RGBA', SCREEN, (0, 0, 0, 0))
    ImageDraw.Draw(shade).rectangle((0, SCREEN[1] - 150, SCREEN[0], SCREEN[1]), fill=(0, 0, 0, 130))
    screen.alpha_composite(shade.filter(ImageFilter.GaussianBlur(30)))
    draw = ImageDraw.Draw(screen)
    draw.text((60, SCREEN[1] - 132), title.upper(), fill=(245, 245, 240), font=font(52))
    draw.text((62, SCREEN[1] - 74), location or 'World at War', fill=OFF_WHITE, font=font(26, False))
    draw.text((SCREEN[0] - 60, SCREEN[1] - 60), 'LOADING...', fill=OFF_WHITE, font=font(24), anchor='ra')
    return screen.convert('RGB')


# ------------------------------------------------------------------------ globe

class Globe:
    """An orthographic globe from BO2's globe_map_zm texture, rotatable."""

    def __init__(self, texture: Image.Image | None, size: int = 520, tilt: float = 18.0):
        self.size, self.tilt = size, math.radians(tilt)
        if texture is None:
            texture = Image.new('RGBA', (1024, 512), (24, 30, 38, 255))
            draw = ImageDraw.Draw(texture)
            for lon in range(0, 1024, 64):
                draw.line((lon, 0, lon, 512), fill=(60, 72, 84, 255))
            for lat in range(0, 512, 64):
                draw.line((0, lat, 1024, lat), fill=(60, 72, 84, 255))
        self.texture = texture.convert('RGB').resize((1024, 512), Image.Resampling.BOX)
        # Lift the dark game texture so continents read at launcher size.
        self.texture = self.texture.point(lambda v: min(255, int(v * 1.9 + 8)))
        self.pixels = self.texture.tobytes()   # RGB triples, row-major
        self.origin = (0, 0)
        radius = size / 2 - 2
        self.samples = []
        c, s = math.cos(self.tilt), math.sin(self.tilt)
        for py in range(size):
            for px in range(size):
                nx, ny = (px - size / 2 + 0.5) / radius, (size / 2 - py - 0.5) / radius
                d = nx * nx + ny * ny
                if d >= 1:
                    continue
                nz = math.sqrt(1 - d)
                lat = math.asin(max(-1.0, min(1.0, ny * c + nz * s)))
                dlon = math.degrees(math.atan2(nx, nz * c - ny * s))
                row = min(511, int((90 - math.degrees(lat)) / 180 * 512)) * 1024
                light = 0.35 + 0.65 * nz
                self.samples.append((py * size + px, row, dlon, light))

    def render(self, center_lon: float, markers=()) -> Image.Image:
        """The sphere alone (transparent outside). center_lon is geographic,
        east positive."""
        size = self.size
        out = [(0, 0, 0, 0)] * (size * size)
        pixels = self.pixels
        for index, row, dlon, light in self.samples:
            u = int(((center_lon + dlon + 180) % 360) / 360 * 1024) % 1024
            at = (row + u) * 3
            r, g, b = pixels[at], pixels[at + 1], pixels[at + 2]
            out[index] = (int(r * light), int(g * light), int(b * light), 255)
        image = Image.new('RGBA', (size, size))
        image.putdata(out)
        rim = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        ImageDraw.Draw(rim).ellipse((2, 2, size - 3, size - 3), outline=(255, 140, 60, 120), width=3)
        image.alpha_composite(rim.filter(ImageFilter.GaussianBlur(3)))
        return image

    def scene(self, center_lon: float, markers=(), background: Image.Image | None = None) -> Image.Image:
        """The Change Map globe on a 1280 x 720 screen. markers: (bo2_lon,
        bo2_lat, icon or None, name, highlighted)."""
        screen = (_cover(background, SCREEN) if background is not None
                  else Image.new('RGBA', SCREEN, (12, 14, 18, 255)))
        screen.alpha_composite(Image.new('RGBA', SCREEN, (0, 0, 0, 90)))
        self.origin = ((SCREEN[0] - self.size) // 2, (SCREEN[1] - self.size) // 2 + 10)
        screen.alpha_composite(self.render(center_lon), self.origin)
        for marker in sorted(markers, key=lambda m: m[4]):
            self._marker(screen, center_lon, *marker)
        draw = ImageDraw.Draw(screen)
        draw.text((210, 672), 'ESC', fill=(232, 178, 64), font=font(26))
        draw.text((262, 672), 'Back', fill=OFF_WHITE, font=font(26, False))
        return screen.convert('RGB')

    def project(self, center_lon: float, bo2_lon: float, lat: float) -> tuple[float, float] | None:
        geo, phi = math.radians(-bo2_lon - center_lon), math.radians(lat)
        x, y, z = math.cos(phi) * math.sin(geo), math.sin(phi), math.cos(phi) * math.cos(geo)
        c, s = math.cos(self.tilt), math.sin(self.tilt)
        y2, z2 = y * c - z * s, y * s + z * c
        if z2 <= 0.05:
            return None
        radius = self.size / 2 - 2
        return self.size / 2 + x * radius, self.size / 2 - y2 * radius

    def pick(self, center_lon: float, px: float, py: float) -> tuple[int, int] | None:
        """BO2 (longitude, latitude) under a click on the globe, or None."""
        radius = self.size / 2 - 2
        nx, ny = (px - self.size / 2) / radius, (self.size / 2 - py) / radius
        d = nx * nx + ny * ny
        if d >= 1:
            return None
        nz = math.sqrt(1 - d)
        c, s = math.cos(self.tilt), math.sin(self.tilt)
        lat = math.degrees(math.asin(max(-1.0, min(1.0, ny * c + nz * s))))
        geo = center_lon + math.degrees(math.atan2(nx, nz * c - ny * s))
        bo2 = -((geo + 180) % 360 - 180)
        return round(bo2), round(lat)

    def _marker(self, image, center_lon, bo2_lon, lat, icon, name, highlighted):
        spot = self.project(center_lon, bo2_lon, lat)
        if spot is None:
            return
        x, y = spot[0] + self.origin[0], spot[1] + self.origin[1]
        draw = ImageDraw.Draw(image)
        size = 54 if highlighted else 34
        if icon is not None:
            mark = icon.convert('RGBA').copy()
            mark.thumbnail((size, size), Image.Resampling.LANCZOS)
            image.alpha_composite(mark, (int(x - mark.width / 2), int(y - mark.height / 2)))
        else:
            draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=ORANGE if highlighted else OFF_WHITE)
        if name:
            face = font(18 if highlighted else 13)
            width = draw.textlength(name, font=face)
            left = x + size / 2 + 4
            draw.rounded_rectangle((left - 4, y - 12, left + width + 6, y + 12), radius=4,
                                   fill=(32, 22, 14, 220), outline=(150, 105, 50, 255) if highlighted else (90, 70, 50, 255))
            draw.text((left + 1, y), name, fill=ORANGE if highlighted else OFF_WHITE, font=face, anchor='lm')


def stock_maps(bo2: str | Path | None) -> list[tuple[float, float, str, str]]:
    """(bo2_lon, bo2_lat, signpost image, name) for the stock zombie maps."""
    import csv
    if not bo2:
        return []
    path = Path(bo2) / 'raw' / 'zm' / 'mapstable.csv'
    names = {'zm_transit': 'TranZit', 'zm_nuked': 'Nuketown', 'zm_highrise': 'Die Rise',
             'zm_prison': 'Mob of the Dead', 'zm_buried': 'Buried', 'zm_tomb': 'Origins'}
    try:
        rows = list(csv.reader(path.read_text(encoding='utf-8-sig').splitlines()))
    except OSError:
        return []
    out = []
    for row in rows:
        if len(row) > 17 and row[0] in names:
            try:
                out.append((float(row[16]), float(row[17]), row[4], names[row[0]]))
            except ValueError:
                continue
    return out
