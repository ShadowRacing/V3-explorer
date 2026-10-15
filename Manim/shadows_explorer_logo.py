"""
Shadows File Explorer start-up video: ShadowTracker's "F4 -- Sheen" splash
(repository ShadowRacing/V3_Project-Tracker) with the explorer's own words and
an SE in the tile. See Manim/README.md.

A pen draws the SE in a shaded tile; the tile glides to its slot; light
crosses the tile (the SE turns white where it is lit) and moves on across
the name, which it uncovers letter by letter with a brief glint; behind it
the shadow settles back onto the logo's own arc; the version badge flashes.
The light itself is never drawn as a band -- it shows only where it lands.

1920x1080 @ 60 fps, about 6.3 s; H.264 yuv420p after the ffmpeg re-encode.
"""

import sys
from pathlib import Path

import numpy as np
from manim import UP, Flash, Scene, ValueTracker, VGroup, linear, smooth
from manim.utils.rate_functions import ease_in_out_sine, there_and_back

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explorer_brand import (  # noqa: E402  (sibling module, path set above)
    BG, BLUE_LIGHT, LOCK_LOGO_SIZE, LOCK_LOGO_X, SHADE_C, SHADE_R, SE_MARK,
    Logo, lockup_text, mix,
)

SLANT = np.tan(np.radians(12))  # the letters' own skew: the light travels slanted
GLINT_W = 0.38                  # glint width around the light's centre
REVEAL_RAMP = 0.45              # how far a letter takes to fade fully in
LIGHT_LEAD = 0.6                # the light's leading edge, ahead of its centre
GLINT = mix(BLUE_LIGHT, "white", 0.75)
GLINT_AMT = 0.9                 # how far toward GLINT at the peak
BLOOM_COLOUR = mix(BLUE_LIGHT, "white", 0.35)
BLOOM, BLOOM_OP = 8.0, 0.7      # halo at the glint peak (shows on white text)
HOLD = 1.8                      # final frame: ~0.3 s a word, at least 1.5 s


class ShadowsExplorerLogo(Scene):
    """The F4 splash: stroke, glide, sheen, settle, badge."""

    MARK = SE_MARK
    LOGO_X = LOCK_LOGO_X
    LOCKUP: dict = {}  # lockup_text() keyword arguments

    def construct(self) -> None:
        self.camera.background_color = BG
        logo = self._draw_logo()
        self._sheen(logo)
        self.wait(HOLD)

    def _draw_logo(self) -> Logo:
        """Shaded tile, then the SE drawn with a pen tip, then the glide."""
        logo = Logo(mark=self.MARK)
        logo.disc_x.set_value(50)        # the disc covers the whole tile:
        logo.disc_y.set_value(50)        # everything starts in shadow
        logo.disc_r.set_value(150)
        for knob, v in ((logo.st, 0), (logo.gap, 0), (logo.tile, 0),
                        (logo.glow, 1), (logo.tip, 1)):
            knob.set_value(v)
        self.add(logo.mob())
        self.play(logo.tile.animate.set_value(1), run_time=0.35)
        self.play(logo.st.animate.set_value(1), run_time=1.3,
                  rate_func=ease_in_out_sine)
        self.play(logo.cx.animate.set_value(self.LOGO_X),
                  logo.size.animate.set_value(LOCK_LOGO_SIZE),
                  logo.glow.animate.set_value(0), logo.tip.animate.set_value(0),
                  run_time=0.6, rate_func=smooth)
        return logo

    def _sheen(self, logo: Logo) -> None:
        """The light crosses the tile, then the name; the shadow settles."""
        divider, words, tagline, version = lockup_text(logo_x=self.LOGO_X,
                                                       **self.LOCKUP)
        letters = [*words[0], *words[1], *tagline, *version]
        x = ValueTracker(self.LOGO_X - LOCK_LOGO_SIZE)
        self._light_letters(letters, x)
        divider.set_opacity(0)
        self.add(divider, *letters)
        self.play(
            x.animate.set_value(self.LOGO_X + LOCK_LOGO_SIZE * 0.5),
            logo.disc_x.animate.set_value(142), logo.disc_y.animate.set_value(142),
            logo.disc_r.animate.set_value(62), logo.gap.animate.set_value(1),
            logo.edge.animate.set_value(1),
            run_time=0.55, rate_func=smooth,
        )
        self.play(
            x.animate.set_value(8.6),
            logo.disc_x.animate.set_value(SHADE_C[0]),
            logo.disc_y.animate.set_value(SHADE_C[1]),
            logo.disc_r.animate.set_value(SHADE_R), logo.edge.animate.set_value(0),
            divider.animate.set_opacity(0.5),
            run_time=1.25, rate_func=linear,
        )
        for m in letters:
            m.clear_updaters()
            m.restore()
        badge = VGroup(*version)
        self.play(
            Flash(badge, color=BLUE_LIGHT, line_length=0.16, num_lines=10,
                  flash_radius=badge.width * 0.75, time_width=0.4),
            badge.animate(rate_func=there_and_back).scale(1.15),
            run_time=0.45,
        )

    @staticmethod
    def _light_letters(letters: list, x: ValueTracker) -> None:
        """Each letter is uncovered as the light's leading edge reaches it and
        glints (colour + bloom) as its centre passes."""
        for m in letters:
            m.save_state()
            op, col = m.get_fill_opacity(), m.get_fill_color().to_hex()
            home = m.get_center().copy()

            def light(mob, op=op, col=col, home=home):
                centre = x.get_value() + SLANT * home[1]
                t = float(np.clip((centre + LIGHT_LEAD - mob.get_left()[0])
                                  / REVEAL_RAMP, 0, 1))
                g = float(np.exp(-0.5 * ((centre - home[0]) / GLINT_W) ** 2)) * t
                mob.set_fill(mix(col, GLINT, GLINT_AMT * g), opacity=op * t)
                mob.set_stroke(BLOOM_COLOUR, width=BLOOM * g, opacity=BLOOM_OP * g * op)

            m.add_updater(light)
            light(m)
