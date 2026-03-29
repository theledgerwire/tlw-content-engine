# TLW v4
import os
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

BUFFER_API_KEY   = os.environ.get("BUFFER_API_KEY", "")
BUFFER_PROFILE_X = os.environ.get("BUFFER_PROFILE_X", "")
POST_TEXT        = os.environ.get("POST_TEXT", "")
HEADLINE_LINE1   = os.environ.get("HEADLINE_LINE1", "Breaking news.")
HEADLINE_LINE2   = os.environ.get("HEADLINE_LINE2", "Read the full story.")

W, H   = 1080, 1080
GOLD   = (240, 185, 11)
WHITE  = (255, 255, 255)
NAVY   = (4, 8, 20)
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

print("=== TLW Card Generator v4 ===")
print(f"Profile ID: {BUFFER_PROFILE_X[:8] if BUFFER_PROFILE_X else 'MISSING'}...")

img  = Image.new("RGB", (W, H), NAVY)
draw = ImageDraw.Draw(img)
PAD  = 52

logo_f = ImageFont.truetype(FONT_BOLD, 19)
logo_t = "THE LEDGER WIRE"
lb = draw.textbbox((0,0), logo_t, font=logo_f)
draw.text((PAD, 36), logo_t, font=logo_f, fill=WHITE)
draw.rectangle([(PAD, 59),(PAD+(lb[2]-lb[0]), 62)], fill=GOLD)

h1_f = ImageFont.truetype(FONT_BOLD, 88)
h2_f = ImageFont.truetype(FONT_BOLD, 80)
draw.text((PAD, 600), HEADLINE_LINE1, font=h1_f, fill=WHITE)
draw.text((PAD, 700), HEADLINE_LINE2, font=h2_f, fill=GOLD)

draw.rectangle([(0, H-46),(W, H)], fill=NAVY)
draw.rectangle([(0, H-48),(W, H-46)], fill=GOLD)

img.save("card.png", "PNG")
print("Card saved: card.png")

if BUFFER_API_KEY and BUFFER_PROFILE_X:
    r = requests.post(
        "https://api.bufferapp.com/1/updates/create.json",
        headers={"Authorization": f"Bearer {BUFFER_API_KEY}"},
        data={
            "profile_ids[]": BUFFER_PROFILE_X.strip(),
            "text": POST_TEXT,
            "now": "false",
            "shorten": "false",
        },
        timeout=30
    )
    print(f"Buffer status: {r.status_code}")
    print(f"Buffer response: {r.text[:500]}")
else:
    print("Buffer credentials missing")
