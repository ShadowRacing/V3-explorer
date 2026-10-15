# Rendering the Shadows File Explorer start-up video

The video is `shadows_explorer/resources/ShadowsExplorerLogo.mp4`, about 6.3 s,
1920x1080 at 60 fps. The app plays it at start-up (`shadows_explorer/ui/splash.py`);
when the video cannot play it shows `ShadowsExplorerLogo.png`, the video's last
frame, instead.

Scene: `Manim/shadows_explorer_logo.py`, class `ShadowsExplorerLogo`. It is
ShadowTracker's "F4 — Sheen" splash with an **SE** in the tile: a pen draws
the SE in a shaded tile, the tile glides left, and light crosses the tile
(the SE turns white where it is lit), then moves on across **Shadows** File
Explorer, "Modern File Manager" and the version badge, uncovering each letter
with a brief glint. `Manim/explorer_brand.py` holds the logo geometry, the
colours, the font chain and the lockup text; it is a self-contained copy of
ShadowTracker's code, so it does not follow later changes made there.

The badge text is `VERSION` in `explorer_brand.py` (3.0).

## Render

Manim 0.21 (`pip install manim`; on Linux it also needs
`libcairo2-dev libpango1.0-dev ffmpeg`). From the repository root:

```
manim -qh --fps 60 -r 1920,1080 --disable_caching --media_dir <scratch folder> Manim/shadows_explorer_logo.py ShadowsExplorerLogo
```

Then re-encode to H.264 / yuv420p (Windows Media Foundation will not play
other pixel formats reliably):

```
ffmpeg -y -i <scratch folder>/videos/shadows_explorer_logo/1080p60/ShadowsExplorerLogo.mp4 -c:v libx264 -pix_fmt yuv420p -profile:v high -crf 18 -preset slow -r 60 -an -movflags +faststart shadows_explorer/resources/ShadowsExplorerLogo.mp4
```

Then refresh the fallback still from the last frame:

```
ffmpeg -y -sseof -0.5 -i shadows_explorer/resources/ShadowsExplorerLogo.mp4 -frames:v 1 -vf scale=960:540 -update 1 shadows_explorer/resources/ShadowsExplorerLogo.png
```

Keep the `media/` output out of the repository. The font is the first
installed of Segoe UI, Ubuntu, Cantarell, Noto Sans; the committed render was
made on Linux, so it uses Ubuntu.
