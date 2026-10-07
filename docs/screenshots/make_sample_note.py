"""Generate a handwritten-style sample note on lined paper for the hero screenshot."""
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

random.seed(7)

W, H = 1240, 1550
img = Image.new("RGB", (W, H), (246, 244, 239))
d = ImageDraw.Draw(img)

# lined paper
for y in range(140, H, 56):
    d.line([(30, y), (W - 20, y)], fill=(199, 205, 214), width=2)
# margin line + binder holes
d.line([(110, 0), (110, H)], fill=(228, 180, 180), width=2)
for hy in (260, 760, 1260):
    d.ellipse([52, hy - 16, 84, hy + 16], fill=(252, 251, 249), outline=(190, 190, 190), width=2)

FONTS = [
    "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
    "/System/Library/Fonts/Supplemental/Noteworthy.ttc",
    "/System/Library/Fonts/Supplemental/MarkerFelt.ttc",
]
font_path = None
for p in FONTS:
    try:
        ImageFont.truetype(p, 40)
        font_path = p
        break
    except OSError:
        continue
assert font_path, "no handwriting font found"
f = lambda s: ImageFont.truetype(font_path, s)

INK = (52, 56, 66)
lines = [
    ("# Sample Notes", 46, 0),
    ("", 20, 0),
    ("## Key Concepts", 42, 0),
    ("", 14, 0),
    ("This is **bold** and this is *italic*.", 38, 20),
    ("", 20, 0),
    ("### Math Example", 40, 0),
    ("The quadratic formula:  x = (-b ± √(b²-4ac)) / 2a", 36, 10),
    ("", 10, 0),
    ("Display math:", 36, 10),
    ("    ∫ e^(-x²) dx from 0 to ∞  =  √π / 2", 38, 60),
    ("", 16, 0),
    ("### List Example", 40, 0),
    ("- First item", 36, 20),
    ("- Second item", 36, 20),
    ("- Third item", 36, 20),
    ("", 20, 0),
    ("### Code", 40, 0),
    ("```python", 34, 20),
    ("def hello():", 34, 30),
    ('    print("Hello, world!")', 34, 30),
    ("```", 34, 20),
]

y = 120
for text, size, extra_x in lines:
    if not text:
        y += size
        continue
    x = 140 + extra_x + random.randint(-4, 6)
    jitter = random.randint(-3, 3)
    d.text((x, y + jitter), text, font=f(size), fill=INK)
    y += int(size * 1.45)

# subtle paper texture: slight rotation + soft shadowing
img = img.rotate(-0.6, resample=Image.BICUBIC, expand=False, fillcolor=(236, 234, 229))
img = img.filter(ImageFilter.GaussianBlur(0.4))

out = "/private/tmp/claude-502/-Users-jbutt-Developer-ocr-handwritten-notes/be115aa7-5d89-46a1-870e-622881a3361b/scratchpad/sample_note.jpg"
img.save(out, quality=88)
print("saved", out, "font:", font_path)
