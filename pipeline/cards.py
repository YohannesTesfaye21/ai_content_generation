"""Text rendered in code (never inside generated images): subtitles and the AI end card.

This FFmpeg build has no drawtext/libass, so text is drawn with Pillow as PNGs and overlaid.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
MAX_CHARS = 40   # per subtitle line
MAX_LINES = 2


def font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default(size)


def chunk_subtitle(text: str) -> list[str]:
    """Split a line into balanced subtitle cards of at most 2 lines x 40 characters.

    Cards are split by character count so we never leave a one-word orphan card.
    """
    import re
    limit = MAX_CHARS * MAX_LINES
    # 1. break at sentence/clause punctuation, 2. pack clauses into cards, 3. word-split leftovers
    clauses = [c.strip() for c in re.split(r"(?<=[.,:;!?])\s+", text) if c.strip()]
    cards, cur = [], ""
    for c in clauses:
        joined = f"{cur} {c}".strip()
        if len(joined) <= limit:
            cur = joined
        else:
            if cur:
                cards.append(cur)
            cur = c
    if cur:
        cards.append(cur)
    out = []
    for c in cards:
        while len(c) > limit:  # a single clause longer than one card
            cut = c.rfind(" ", 0, limit)
            out.append(c[:cut])
            c = c[cut + 1:]
        out.append(c)

    def balance(card):  # two lines of similar length read better than one long + one short
        if len(card) <= MAX_CHARS:
            return card
        for width in range((len(card) + 1) // 2, MAX_CHARS + 1):
            lines = textwrap.wrap(card, width)
            if len(lines) <= MAX_LINES:
                return "\n".join(lines)
        return "\n".join(textwrap.wrap(card, MAX_CHARS))

    return [balance(c) for c in out]


def subtitle_png(text: str, size: tuple[int, int], out: Path, vertical: bool) -> None:
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(FONT_BOLD, int(w * (0.042 if vertical else 0.028)))
    bbox = d.multiline_textbbox((0, 0), text, font=f, align="center", spacing=8)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # Vertical video: keep text in the safe area, well above platform buttons and captions.
    cy = int(h * (0.70 if vertical else 0.87))
    x, y = (w - tw) // 2, cy - th // 2
    pad = int(f.size * 0.45)
    d.rounded_rectangle((x - pad, y - pad, x + tw + pad, y + th + pad), radius=pad,
                        fill=(0, 0, 0, 150))
    d.multiline_text((x - bbox[0], y - bbox[1]), text, font=f, fill=(255, 255, 255, 255),
                     align="center", spacing=8)
    img.save(out)


def end_card_png(sb: dict, size: tuple[int, int], out: Path, music_credit: str) -> None:
    w, h = size
    vertical = h > w
    img = Image.new("RGB", size, (24, 17, 12))
    d = ImageDraw.Draw(img)
    unit = w * (0.07 if vertical else 0.045)
    title_f, big_f, small_f = font(FONT_BOLD, int(unit)), font(FONT_BOLD, int(unit * 0.8)), font(FONT_REG, int(unit * 0.36))
    model = sb.get("image_model", "").split("/")[-1].replace("flux-2-klein-4b", "FLUX.2 klein 4B")
    credits = (f"Images: {model} (Cloudflare Workers AI)\n"
               f"Narration: Gemini TTS ({sb.get('language_name', sb['language'])})\n"
               f"Music: {music_credit}\nEdit: FFmpeg, assembled in code")
    blocks = [(sb["title"], title_f, (236, 214, 170)),
              ("Made with AI", big_f, (255, 255, 255)),
              (credits, small_f, (200, 190, 175))]
    heights = [d.multiline_textbbox((0, 0), t, font=f, spacing=10, align="center")[3] for t, f, _ in blocks]
    gap = unit * 0.7
    y = (h - sum(heights) - gap * 2) / 2
    for (t, f, c), bh in zip(blocks, heights):
        bw = d.multiline_textbbox((0, 0), t, font=f, spacing=10, align="center")[2]
        d.multiline_text(((w - bw) / 2, y), t, font=f, fill=c, spacing=10, align="center")
        y += bh + gap
    img.save(out)
