"""
The Shadows File Explorer logo as animatable Manim geometry, plus the
end-frame lockup.

A self-contained copy of ShadowTracker's splash code (repository
ShadowRacing/V3_Project-Tracker, Manim/shadowtracker_brand.py), with the
tile's letters changed from ST to SE. Used by shadows_explorer_logo.py.

* the logo is ShadowTracker's rounded master icon (rx=22) rebuilt from its
  own path data so its parts can move: the tile minus a radius-80 disc is the
  blue "light" corner, the tile inside the disc is the shade, and the letter
  stroke is white where it is lit and blue where it is shaded. Manim's
  SVGMobject ignores clip paths, so skia-pathops (a Manim dependency) does
  the clipping;
* the colours are ShadowTracker's brand and dark-theme colours, written in
  here because their source files live in that repository;
* the font is the first family of the chain that is installed (Segoe UI on
  Windows, Ubuntu on Ubuntu).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import manimpango
import numpy as np
import pathops
from manim import (
    BOLD, DOWN, LEFT, NORMAL, RIGHT, UP, Line, ManimColor, RoundedRectangle,
    Text, ValueTracker, VGroup, VMobject, interpolate_color,
)

# --- colours: ShadowTracker's brand and dark theme ---------------------------
BLUE = "#3B82F6"            # the light tile, the shaded stroke
SHADE = "#141A26"           # the shade tile
WHITE = "#FFFFFF"           # the lit stroke
BG = "#0B0F17"              # the background, and the cut along the arc
TEXT_PRIMARY = "#f3f6fc"
TEXT_SECONDARY = "#9aa4b6"


def mix(a, b, t: float) -> ManimColor:
    return interpolate_color(ManimColor(a), ManimColor(b), t)


# Glows only: the brand blue lifted toward white.
BLUE_LIGHT = mix(BLUE, WHITE, 0.2)
EDGE_LIGHT = mix(BLUE, WHITE, 0.7)

# The UI font chain, in order.
FONT_CHAIN = ("Segoe UI", "Ubuntu", "Cantarell", "Noto Sans")
_INSTALLED = set(manimpango.list_fonts())
FONT = next((f for f in FONT_CHAIN if f in _INSTALLED), "sans-serif")

TAGLINE = "Modern File Manager"
# The product version (V3); the package's __version__ still reads 1.0.0.
VERSION = "3.0"

# --- logo geometry, SVG units (0..100, y down) ------------------------------
TILE_RX = 22.0
SHADE_C = (50 + math.sqrt(700), 50 + math.sqrt(700))  # arc centre: the disc
SHADE_R = 80.0                                         # through both corners
GAP_W = 3.0
ST_W = 12.0
_SKEW = math.tan(math.radians(-12))
# translate(50 50) scale(0.8) translate(-50 -50) translate(5 0) skewX(-12)
ST_AFFINE = dict(
    scaleX=0.8, skewY=0.0, skewX=0.8 * _SKEW, scaleY=0.8,
    translateX=0.8 * (5 - 50) + 50, translateY=0.8 * (-50) + 50,
)
# ShadowTracker's ST, the base of the SE below:
# "M86 26 H36 C27 26 21 31 21 37 C21 45 29 47 36 49 C44 51 51 54 51 62
#  C51 69 45 74 36 74 C29 74 23 71 20 66 M68 26 V74"
ST_SEGMENTS = [
    ("M", (86, 26)), ("L", (36, 26)),
    ("C", (27, 26), (21, 31), (21, 37)),
    ("C", (21, 45), (29, 47), (36, 49)),
    ("C", (44, 51), (51, 54), (51, 62)),
    ("C", (51, 69), (45, 74), (36, 74)),
    ("C", (29, 74), (23, 71), (20, 66)),
    ("M", (68, 26)), ("L", (68, 74)),
]


def _narrow(segments: list, x0: float, k: float) -> list:
    """The segments squeezed horizontally toward x0 by k."""
    return [(seg[0], *((x0 + (x - x0) * k, y) for x, y in seg[1:]))
            for seg in segments]


# The tile's "SE": ShadowTracker's ST's own S, its top cut back to the S and
# narrowed so the E fits, then an E drawn as one pen run (top bar, stem,
# bottom bar) and its middle bar. Same box (x 20..86, y 26..74) as the ST.
SE_SEGMENTS = [
    *_narrow([("M", (51, 26)), *ST_SEGMENTS[1:7]], 20, 0.84),
    ("M", (86, 26)), ("L", (62, 26)), ("L", (62, 74)), ("L", (86, 74)),
    ("M", (62, 50)), ("L", (80, 50)),
]

# End-frame layout (scene units; the frame is 14.22 x 8).
LOCK_LOGO_SIZE = 2.1
LOCK_LOGO_X = -4.85
WORD_SIZE = 58


# ============================================================================
# skia paths
# ============================================================================
_K = 0.5522847498  # cubic circle constant


def _circle(cx: float, cy: float, r: float) -> pathops.Path:
    k = _K * r
    p = pathops.Path()
    p.moveTo(cx + r, cy)
    p.cubicTo(cx + r, cy + k, cx + k, cy + r, cx, cy + r)
    p.cubicTo(cx - k, cy + r, cx - r, cy + k, cx - r, cy)
    p.cubicTo(cx - r, cy - k, cx - k, cy - r, cx, cy - r)
    p.cubicTo(cx + k, cy - r, cx + r, cy - k, cx + r, cy)
    p.close()
    return p


def _tile() -> pathops.Path:
    """The rounded tile, 0..100 with rx=22, as in the master icon."""
    r, k = TILE_RX, _K * TILE_RX
    p = pathops.Path()
    p.moveTo(r, 0)
    p.lineTo(100 - r, 0)
    p.cubicTo(100 - r + k, 0, 100, r - k, 100, r)
    p.lineTo(100, 100 - r)
    p.cubicTo(100, 100 - r + k, 100 - r + k, 100, 100 - r, 100)
    p.lineTo(r, 100)
    p.cubicTo(r - k, 100, 0, 100 - r + k, 0, 100 - r)
    p.lineTo(0, r)
    p.cubicTo(0, r - k, r - k, 0, r, 0)
    p.close()
    return p


_OPS = {"and": pathops.PathOp.INTERSECTION, "sub": pathops.PathOp.DIFFERENCE,
        "or": pathops.PathOp.UNION}


def _op(a: pathops.Path, b: pathops.Path, kind: str) -> pathops.Path:
    return pathops.op(a, b, _OPS[kind])


class Mark:
    """The letters in the tile: a centre line sampled to polylines, one per
    pen run (for the ST: the T bar + S, then the stem)."""

    def __init__(self, segments: list) -> None:
        self.runs = _sample_runs(segments)
        self.lengths = [sum(math.dist(r[i], r[i + 1]) for i in range(len(r) - 1))
                        for r in self.runs]


def _sample_runs(segments: list) -> list[list[tuple[float, float]]]:
    runs: list[list[tuple[float, float]]] = []
    cur = (0.0, 0.0)
    for seg in segments:
        if seg[0] == "M":
            cur = seg[1]
            runs.append([cur])
        elif seg[0] == "L":
            a, b = np.array(cur), np.array(seg[1])
            runs[-1] += [tuple(a + (b - a) * t) for t in np.linspace(0, 1, 24)[1:]]
            cur = seg[1]
        else:
            p0, p1, p2, p3 = (np.array(x) for x in (cur, *seg[1:]))
            for t in np.linspace(0, 1, 24)[1:]:
                q = ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 \
                    + 3 * (1 - t) * t * t * p2 + t ** 3 * p3
                runs[-1].append(tuple(q))
            cur = seg[3]
    return runs


ST_MARK = Mark(ST_SEGMENTS)
SE_MARK = Mark(SE_SEGMENTS)


def _st_centerline(progress: float, mark: Mark = ST_MARK) -> pathops.Path:
    """The centre line drawn up to ``progress`` (0..1) of its total length."""
    budget = max(0.0, min(1.0, progress)) * sum(mark.lengths)
    path = pathops.Path()
    for run in mark.runs:
        if budget <= 1e-6:
            break
        path.moveTo(*run[0])
        for a, b in zip(run[:-1], run[1:]):
            d = math.dist(a, b)
            if budget >= d:
                path.lineTo(*b)
                budget -= d
                continue
            t = budget / d
            path.lineTo(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            budget = 0
            break
    return path


def st_outline(progress: float = 1.0, width: float = ST_W,
               mark: Mark = ST_MARK) -> pathops.Path:
    """The ST as a filled outline: the stroke is expanded first, then the SVG's
    own transform is applied, so the skew bends the stroke as in the logo."""
    centre = _st_centerline(progress, mark)
    if not list(centre.segments):
        return pathops.Path()
    centre.stroke(width, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    centre.convertConicsToQuads()
    return _op(centre.transform(**ST_AFFINE), pathops.Path(), "or")


def st_tip(progress: float, mark: Mark = ST_MARK) -> tuple[float, float] | None:
    """The drawn end of the stroke, in SVG units."""
    pts = list(_st_centerline(progress, mark).points)
    if not pts:
        return None
    x, y = pts[-1]
    a = ST_AFFINE
    return (a["scaleX"] * x + a["skewX"] * y + a["translateX"],
            a["scaleY"] * y + a["translateY"])


def to_vmob(path: pathops.Path, cx: float, cy: float, size: float,
            color, opacity: float = 1.0) -> VMobject:
    """SVG-unit skia path -> filled VMobject, centred at (cx, cy)."""
    k = size / 100.0
    vm = VMobject(fill_color=color, fill_opacity=opacity, stroke_width=0)
    path = pathops.Path(path)
    path.convertConicsToQuads()

    def P(x: float, y: float) -> np.ndarray:
        return np.array([cx + (x - 50) * k, cy - (y - 50) * k, 0.0])

    start = None
    for verb, pts in path:
        if verb == pathops.PathVerb.MOVE:
            start = P(*pts[0])
            vm.start_new_path(start)
        elif verb == pathops.PathVerb.LINE:
            vm.add_line_to(P(*pts[0]))
        elif verb == pathops.PathVerb.QUAD:
            vm.add_quadratic_bezier_curve_to(P(*pts[0]), P(*pts[1]))
        elif verb == pathops.PathVerb.CUBIC:
            vm.add_cubic_bezier_curve_to(P(*pts[0]), P(*pts[1]), P(*pts[2]))
        elif verb == pathops.PathVerb.CLOSE and start is not None:
            vm.add_line_to(start)
    return vm


# ============================================================================
# the animatable logo
# ============================================================================
def _tracker(v: float):
    return field(default_factory=lambda: ValueTracker(v))


@dataclass
class Logo:
    """Every knob the video animates, as ValueTrackers.

    disc_x / disc_y / disc_r : the shade disc in SVG units (rest: SHADE_C, 80).
    st : how much of the letter stroke is drawn (0..1).  tile : tile opacity.
    gap : opacity of the dark cut along the arc.  glow : halo round the stroke.
    tip : the bright pen tip.  edge : the lit edge of the arc while it moves.
    """

    cx: ValueTracker = _tracker(0)
    cy: ValueTracker = _tracker(0)
    size: ValueTracker = _tracker(3.2)
    disc_x: ValueTracker = _tracker(SHADE_C[0])
    disc_y: ValueTracker = _tracker(SHADE_C[1])
    disc_r: ValueTracker = _tracker(SHADE_R)
    st: ValueTracker = _tracker(1)
    tile: ValueTracker = _tracker(1)
    gap: ValueTracker = _tracker(1)
    glow: ValueTracker = _tracker(0)
    tip: ValueTracker = _tracker(0)
    edge: ValueTracker = _tracker(0)
    mark: Mark = SE_MARK

    SLOTS = 24  # more parts than build() ever returns

    def _frame(self) -> tuple[float, float, float]:
        return self.cx.get_value(), self.cy.get_value(), self.size.get_value()

    def _disc(self, extra: float = 0.0) -> pathops.Path:
        return _circle(self.disc_x.get_value(), self.disc_y.get_value(),
                       max(self.disc_r.get_value() + extra, 0.01))

    def _ring(self, width: float) -> pathops.Path:
        return _op(self._disc(width / 2), self._disc(-width / 2), "sub")

    def build(self) -> list[VMobject]:
        """This frame's logo as filled parts, back to front."""
        cx, cy, size = self._frame()
        tile_op, st_p = self.tile.get_value(), self.st.get_value()
        tile, disc = _tile(), self._disc()
        st = st_outline(st_p, mark=self.mark)
        light, shade = _op(tile, disc, "sub"), _op(tile, disc, "and")
        parts: list[VMobject] = []
        if self.glow.get_value() > 0.001 and st_p > 0:
            for w, o in ((ST_W * 3.2, 0.06), (ST_W * 2.2, 0.10), (ST_W * 1.5, 0.16)):
                parts.append(to_vmob(st_outline(st_p, w, self.mark), cx, cy, size, BLUE,
                                     o * self.glow.get_value()))
        if tile_op > 0.001:
            parts += [to_vmob(light, cx, cy, size, BLUE, tile_op),
                      to_vmob(shade, cx, cy, size, SHADE, tile_op),
                      to_vmob(_op(st, light, "and"), cx, cy, size, WHITE),
                      to_vmob(_op(st, shade, "and"), cx, cy, size, BLUE)]
            if tile_op < 0.999:
                parts.append(to_vmob(_op(st, tile, "sub"), cx, cy, size, BLUE))
            if self.gap.get_value() > 0.001:
                parts.append(to_vmob(_op(self._ring(GAP_W), tile, "and"), cx, cy,
                                     size, BG, self.gap.get_value() * tile_op))
        else:
            parts.append(to_vmob(st, cx, cy, size, BLUE))
        return parts + self._decorations(tile)

    def _decorations(self, tile: pathops.Path) -> list[VMobject]:
        cx, cy, size = self._frame()
        parts: list[VMobject] = []
        edge = self.edge.get_value()
        if edge > 0.001 and self.tile.get_value() > 0.001:
            for w, o, col in ((9.0, 0.10, BLUE_LIGHT), (5.0, 0.22, BLUE_LIGHT),
                              (1.6, 0.95, EDGE_LIGHT)):
                parts.append(to_vmob(_op(self._ring(w), tile, "and"), cx, cy, size,
                                     col, o * edge))
        st_p, tip = self.st.get_value(), self.tip.get_value()
        if tip > 0.001 and 0.0 < st_p < 0.999:
            u_v = st_tip(st_p, self.mark)
            if u_v is not None:
                k = size / 100.0
                px, py = cx + (u_v[0] - 50) * k, cy - (u_v[1] - 50) * k
                for rad, o, col in ((5.5, 0.12, BLUE_LIGHT), (3.2, 0.3, BLUE_LIGHT),
                                    (1.7, 1.0, WHITE)):
                    parts.append(to_vmob(_circle(50, 50, rad), px, py, size, col,
                                         o * tip))
        return parts

    def mob(self) -> VGroup:
        """A fixed set of slot shapes, refilled from a fresh build every frame.

        Not ``always_redraw``: its ``become()`` aligns old and new parts one by
        one, and when the part count changes (the pen tip goes as the stroke
        completes) it mis-assigns styles for a frame -- the ST blinked out.
        Nor can the parts be swapped for new objects: the Cairo renderer fixes
        which objects it redraws when a play() begins. Fixed slots keep their
        identity; only their points and fill change.
        """
        slots = VGroup(*[VMobject(stroke_width=0, fill_opacity=0)
                         for _ in range(self.SLOTS)])

        def refresh(g: VGroup) -> None:
            parts = self.build()
            for i, slot in enumerate(g.submobjects):
                if i < len(parts):
                    slot.points = parts[i].points.copy()
                    slot.set_fill(parts[i].get_fill_color(),
                                  opacity=parts[i].get_fill_opacity())
                else:
                    slot.points = np.zeros((0, 3))
                    slot.set_fill(opacity=0)

        slots.add_updater(refresh)
        refresh(slots)
        return slots


# ============================================================================
# the end frame: tile | Shadows File Explorer / tagline + version badge
# ============================================================================
def _baseline(word: Text, text: str) -> float:
    """The lowest bottom among the letters that sit on the baseline (no
    descender), so two words line up even when one has a "p" or a "g"."""
    glyphs = [c for c in text if not c.isspace()]
    flat = [m for m, c in zip(word, glyphs) if c not in "gjpqy,;"] or list(word)
    return min(m.get_bottom()[1] for m in flat)


def lockup_text(bold: str = "Shadows", rest: str = "File Explorer",
                tagline_text: str = TAGLINE, version_text: str = VERSION,
                logo_x: float = LOCK_LOGO_X, word_size: float = WORD_SIZE,
                word_gap: float = 0.3) -> tuple[Line, VGroup, Text, VGroup]:
    logo_right = logo_x + LOCK_LOGO_SIZE / 2
    divider = Line(UP * 0.95, DOWN * 0.95, stroke_color=BLUE, stroke_width=2.4,
                   stroke_opacity=0.5)
    divider.move_to([logo_right + 0.55, 0, 0])
    w1 = Text(bold, font=FONT, weight=BOLD, font_size=word_size,
              color=TEXT_PRIMARY)
    w2 = Text(rest, font=FONT, weight=NORMAL, font_size=word_size,
              color=TEXT_SECONDARY)
    w2.next_to(w1, RIGHT, buff=word_gap)
    w2.shift(UP * (_baseline(w1, bold) - _baseline(w2, rest)))
    words = VGroup(w1, w2).next_to(divider, RIGHT, buff=0.55).shift(UP * 0.32)
    tagline = Text(tagline_text, font=FONT, weight=NORMAL, font_size=31,
                   color=TEXT_SECONDARY)
    tagline.next_to(words, DOWN, buff=0.3, aligned_edge=LEFT)
    label = Text(version_text, font=FONT, weight=BOLD, font_size=26, color=WHITE)
    pill = RoundedRectangle(corner_radius=0.2, width=label.width + 0.46,
                            height=0.42, fill_color=BLUE, fill_opacity=1,
                            stroke_width=0)
    label.move_to(pill)
    version = VGroup(pill, label).next_to(tagline, RIGHT, buff=0.3)
    return divider, words, tagline, version
