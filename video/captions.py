#!/usr/bin/python3
"""Render caption / logo overlay PNGs (transparent 1920x1080) for the Space Janitor film.

    /usr/bin/python3 video/captions.py            # -> out/captions/NN.png + captions.json

Edit CAPTIONS below to change text or timing, then re-run this and video/assemble.sh.
"""
import json, math, os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

# ----------------------------------------------------------------------------
# CAPTION DATA  (start seconds, end seconds, spec)
#   "text"    lower-third caption            (use "\n" to force a line break)
#   "kicker"  small uppercase line above the lower-third caption
#   "logo"    big letter-spaced wordmark in the upper third (with gold hexagon)
#   "tagline" thin line under the logo
#   "small"   small letter-spaced line near the bottom (e.g. a URL)
# ----------------------------------------------------------------------------
CAPTIONS = [
    (0.4,  3.3,  {"kicker": "Y COMBINATOR · REQUEST FOR STARTUPS",
                  "text": "Startups in a World of Abundant Space Access"}),
    (3.8,  7.8,  {"text": "Launch is about to get 100x cheaper."}),
    (8.3,  12.0, {"text": "Great news for space. Also great news for space trash."}),
    (12.3, 16.8, {"text": "130,000,000 pieces of junk. Each one faster than a bullet."}),
    (17.3, 23.7, {"text": "Fun fact: in 2009, two satellites collided at 42,000 km/h\nand made 2,000+ new pieces of trash."}),
    (24.4, 29.7, {"logo": "SPACE JANITOR",
                  "text": "Nobody wants to be the janitor. So we will."}),
    (30.3, 36.7, {"text": "A swarm of cheap little mirror satellites."}),
    (37.3, 40.3, {"text": "Together, they focus sunlight on one spot."}),
    (40.6, 42.9, {"text": "...not that one."}),
    (43.1, 44.9, {"text": "Sorry. They're still in training."}),
    (45.2, 46.8, {"text": "That one."}),
    (47.3, 51.0, {"text": "100 mirrors = 100 suns."}),
    (51.3, 55.3, {"text": "No fuel. No lasers. Just sunlight."}),
    (55.7, 59.7, {"text": "It vaporizes, slows down, and burns up. Clean."}),
    (60.3, 63.3, {"text": "Customers: mega-constellations. (Hi, Starlink.)"}),
    (63.7, 68.3, {"text": "LEO needs cleaning on a schedule. So it's a subscription:\npick real debris in our simulator, get a price."}),
    (68.7, 71.7, {"text": "Cheaper launch = more trash to clean + cheaper janitors."}),
    (72.3, 75.7, {"text": "Also. If there's a satellite you really don't like..."}),
    (76.2, 79.0, {"text": "Nice satellite. Shame if someone... focused on it."}),
    (81.9, 83.8, {"text": "(Legal says we're joking.)"}),
    (84.5, 90.0, {"logo": "SPACE JANITOR",
                  "tagline": "We take out the space trash.",
                  "small": "github.com/cloneisyou/compiled-3"}),
]

# ----------------------------------------------------------------------------
# STYLE
# ----------------------------------------------------------------------------
W, H = 1920, 1080
FONT = "/System/Library/Fonts/Avenir Next.ttc"
BOLD, DEMI, MEDIUM, REGULAR, HEAVY = 0, 2, 5, 7, 8   # face indexes in the .ttc

TEXT_SIZE, TEXT_FACE = 46, DEMI
TEXT_BOTTOM = 968          # bottom edge of the lower-third text block
TEXT_MAX_W = 1560          # wrap to two balanced lines beyond this
LINE_GAP = 1.28            # line height multiplier
KICKER_SIZE, KICKER_FACE, KICKER_TRACK = 23, DEMI, 0.26
LOGO_SIZE, LOGO_FACE, LOGO_TRACK = 120, BOLD, 0.20
LOGO_CENTER_Y = 330        # vertical centre of the wordmark
TAGLINE_SIZE, TAGLINE_FACE, TAGLINE_TRACK = 40, REGULAR, 0.04
SMALL_SIZE, SMALL_FACE, SMALL_TRACK = 26, MEDIUM, 0.10
WHITE = (255, 255, 255)
GOLD = (240, 190, 92)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out", "captions")


def font(size, face):
    return ImageFont.truetype(FONT, size, index=face)


def tracked_width(f, s, track_px):
    return sum(f.getlength(c) for c in s) + track_px * (len(s) - 1)


def draw_tracked(d, cx, y, s, f, track_px, fill):
    """Draw string centred on cx with extra letter-spacing; y = top of em box."""
    x = cx - tracked_width(f, s, track_px) / 2
    for c in s:
        d.text((x, y), c, font=f, fill=fill)
        x += f.getlength(c) + track_px


def wrap(text, f, max_w):
    lines = []
    for para in text.split("\n"):
        if f.getlength(para) <= max_w:
            lines.append(para)
            continue
        words = para.split()
        best = None
        for i in range(1, len(words)):     # most balanced two-line split
            a, b = " ".join(words[:i]), " ".join(words[i:])
            score = abs(f.getlength(a) - f.getlength(b))
            if best is None or score < best[0]:
                best = (score, a, b)
        lines += [best[1], best[2]]
    return lines


def hexagon(size, ss=4):
    """Gold hexagonal mirror icon (flat-top, faceted), supersampled."""
    n = size * ss
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = n / 2
    def pts(r, rot=0):
        return [(c + r * math.cos(math.radians(60 * k + rot)),
                 c + r * math.sin(math.radians(60 * k + rot))) for k in range(6)]
    outer = pts(n * 0.48)
    # facets: six triangles in slightly different golds -> reads as a mirror
    shades = [(255, 226, 150), (246, 200, 104), (214, 160, 66),
              (190, 138, 52), (226, 176, 80), (255, 238, 184)]
    for k in range(6):
        d.polygon([(c, c), outer[k], outer[(k + 1) % 6]], fill=shades[k] + (255,))
    d.line(outer + [outer[0]], fill=(255, 244, 210, 255), width=max(2, n // 40), joint="curve")
    return im.resize((size, size), Image.LANCZOS)


def render(spec):
    ink = Image.new("RGBA", (W, H), (0, 0, 0, 0))     # everything visible
    d = ImageDraw.Draw(ink)
    cx = W / 2

    if "logo" in spec:
        f = font(LOGO_SIZE, LOGO_FACE)
        asc, desc = f.getmetrics()
        cap_top = LOGO_CENTER_Y - LOGO_SIZE * 0.36           # approx cap height centre
        y = LOGO_CENTER_Y - (asc + desc) / 2
        icon = hexagon(84)
        ink.alpha_composite(icon, (int(cx - 42), int(cap_top - 84 - 44)))
        draw_tracked(d, cx, y, spec["logo"], f, LOGO_SIZE * LOGO_TRACK, WHITE + (255,))
        if "tagline" in spec:
            tf = font(TAGLINE_SIZE, TAGLINE_FACE)
            draw_tracked(d, cx, LOGO_CENTER_Y + LOGO_SIZE * 0.36 + 46, spec["tagline"], tf,
                         TAGLINE_SIZE * TAGLINE_TRACK, WHITE + (240,))

    if "small" in spec:
        sf = font(SMALL_SIZE, SMALL_FACE)
        draw_tracked(d, cx, TEXT_BOTTOM - SMALL_SIZE * 1.5, spec["small"], sf,
                     SMALL_SIZE * SMALL_TRACK, WHITE + (225,))

    if "text" in spec:
        f = font(TEXT_SIZE, TEXT_FACE)
        lines = wrap(spec["text"], f, TEXT_MAX_W)
        lh = TEXT_SIZE * LINE_GAP
        top = TEXT_BOTTOM - lh * len(lines)
        for i, line in enumerate(lines):
            d.text((cx, top + i * lh + lh / 2), line, font=f, fill=WHITE + (255,), anchor="mm")
        if "kicker" in spec:
            kf = font(KICKER_SIZE, KICKER_FACE)
            ky = top - KICKER_SIZE - 22
            draw_tracked(d, cx, ky, spec["kicker"], kf, KICKER_SIZE * KICKER_TRACK, GOLD + (255,))

    # --- legibility: soft dark halo + tight drop shadow built from the ink alpha
    a = ink.getchannel("A")
    wide = a.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(64))
    wide = wide.point(lambda v: min(255, int(v * 3.6)))          # broad soft glow
    mid = a.filter(ImageFilter.GaussianBlur(10)).point(lambda v: min(255, int(v * 2.0)))
    tight = ImageChops.offset(a, 0, 2).filter(ImageFilter.GaussianBlur(2.5))
    shadow_a = ImageChops.lighter(ImageChops.lighter(wide.point(lambda v: int(v * 0.42)),
                                                     mid.point(lambda v: int(v * 0.62))),
                                  tight.point(lambda v: int(v * 0.80)))
    out = Image.new("RGBA", (W, H), (4, 6, 12, 0))
    out.putalpha(shadow_a)
    out.alpha_composite(ink)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn in os.listdir(OUT):
        if fn.endswith(".png"):
            os.remove(os.path.join(OUT, fn))
    meta = []
    for i, (start, end, spec) in enumerate(CAPTIONS, 1):
        assert end > start, f"caption {i}: end <= start"
        name = f"{i:02d}.png"
        im = render(spec)
        bbox = im.getchannel("A").point(lambda v: 255 if v > 200 else 0).getbbox()
        if bbox and (bbox[0] < 96 or bbox[2] > W - 96 or bbox[1] < 54 or bbox[3] > H - 54):
            print(f"WARNING caption {i} leaves the title-safe area: {bbox}", file=sys.stderr)
        im.save(os.path.join(OUT, name), optimize=False, compress_level=3)
        meta.append({"start": start, "end": end, "file": name,
                     "label": spec.get("text") or spec.get("logo")})
        print(f"{name}  {start:5.1f}-{end:5.1f}  {meta[-1]['label']}")
    with open(os.path.join(OUT, "captions.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    print(f"wrote {len(meta)} captions -> {OUT}")


if __name__ == "__main__":
    main()
