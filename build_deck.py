import sys
import pandas as pd
from pathlib import Path
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN

from segments import SEGMENTS

CHARTS_DIR = Path(__file__).parent / "charts"
DECKS_DIR = Path(__file__).parent / "decks"

SLIDE_W, SLIDE_H = 13.333, 7.5
PAD = 0.4                                   # padding from the slide edges
BOX_L, BOX_T = 8.9, 5.0                     # r-bar chart box, bottom right of the results slide
BOX_W, BOX_H = SLIDE_W - PAD - BOX_L, SLIDE_H - PAD - BOX_T


def add_text(slide, text, left, top, width, height, size=18, bold=False, align=None):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.font.size = Pt(size)
        p.font.bold = bold
        if align is not None:
            p.alignment = align


def add_fit(slide, path, left, top, box_w, box_h, anchor="center"):
    """Place an image inside a box, keeping its aspect ratio.
    Returns the picture's (x, y, width, height) in inches."""
    with Image.open(path) as im:
        w, h = im.size
    scale = min(box_w / w, box_h / h)
    pw, ph = w * scale, h * scale
    if anchor == "bottom-right":
        x, y = left + box_w - pw, top + box_h - ph
    else:
        x, y = left + (box_w - pw) / 2, top + (box_h - ph) / 2
    slide.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(pw), height=Inches(ph))
    return x, y, pw, ph


def image_slide(prs, title, paths):
    paths = [p for p in paths if p.exists()]
    if not paths:
        return
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_text(s, title, 0.5, 0.3, 12.3, 0.8, 28, bold=True)
    col_w = 12.3 / len(paths)
    for i, p in enumerate(paths):
        add_fit(s, p, 0.5 + i * col_w, 1.3, col_w - 0.2, 5.8)


def stats_text(row):
    if row is None or pd.isna(row.get("r_rb")):
        return "Not enough human- and natural-caused fires to run the test."
    return (f"{row['n_fires']:,.0f} fires\n\n"
            f"Human: {row['n_human']:,.0f} fires\n"
            f"  median {row['median_human']:,.1f} acres\n"
            f"Natural: {row['n_natural']:,.0f} fires\n"
            f"  median {row['median_natural']:,.1f} acres\n\n"
            f"Rank-biserial r = {row['r_rb']:+.2f}\n"
            f"p = {row['p_value']:.2g}")


def build_deck(region):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(SLIDE_W), Inches(SLIDE_H)

    # --- Title slide: text top left, map in the right two thirds ---------------------------
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(3.8), Inches(5))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = region
    p.font.size, p.font.bold = Pt(44), True
    sub = tf.add_paragraph()
    sub.text = "Human vs. natural ignition: fire size"
    sub.font.size = Pt(24)
    sub.space_before = Pt(12)

    title_map = CHARTS_DIR / "all" / region / "gacc_highlight.png"
    if title_map.exists():
        add_fit(s, title_map, SLIDE_W / 3, 0.25, SLIDE_W * 2 / 3 - 0.25, SLIDE_H - 0.5)

    # --- One block of slides per segment ---------------------------------------------------
    for key, (label, _) in SEGMENTS.items():
        csv = CHARTS_DIR / key / "results.csv"
        if not csv.exists():
            continue
        table = pd.read_csv(csv).set_index("region")
        row = table.loc[region] if region in table.index else None
        folder = CHARTS_DIR / key / region
        title = f"{region}: {label}"

        # Results slide: map left, stats top right, conclusion + r-bar chart bottom right
        map_path = folder / "region_map.png"
        if map_path.exists():
            s = prs.slides.add_slide(prs.slide_layouts[6])
            add_text(s, title, 0.5, 0.3, 12.3, 0.8, 28, bold=True)
            add_fit(s, map_path, 0.4, 1.2, 8.3, 5.9)
            add_text(s, stats_text(row), 9.0, 1.4, 3.9, 3.3, 16)

            conclusion = str(row["conclusion"]) if row is not None else "Insufficient data"
            bars = folder / "r_bars.png"
            if bars.exists():
                _, y, _, _ = add_fit(s, bars, BOX_L, BOX_T, BOX_W, BOX_H, anchor="bottom-right")
                concl_top = y - 0.6
            else:
                concl_top = SLIDE_H - PAD - 0.5
            add_text(s, conclusion, BOX_L, concl_top, BOX_W, 0.5, 20, bold=True, align=PP_ALIGN.RIGHT)

        image_slide(prs, title, [folder / "monthly_fires.png", folder / "human_causes.png"])
        image_slide(prs, title, [folder / "fires_map.png"])

    DECKS_DIR.mkdir(exist_ok=True)
    out = DECKS_DIR / f"{region}.pptx"
    prs.save(out)
    print(f"Saved {out} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    regions = sys.argv[1:] or sorted(p.name for p in (CHARTS_DIR / "all").iterdir() if p.is_dir())
    for r in regions:
        build_deck(r)