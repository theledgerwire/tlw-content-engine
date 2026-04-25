#!/usr/bin/env python3
"""One-line fix: restore branded gold footer in generate_image.py"""
with open("generate_image.py", "r") as f:
    code = f.read()

old = """def draw_footer(draw):
    # v18.1: Thin 6px gold strip — clean, minimal, no text clutter.
    draw.rectangle([(0, H - 6), (W, H)], fill=GOLD)"""

new = """def draw_footer(draw):
    PAD = 56
    draw.rectangle([(0, H-72), (W, H)], fill=GOLD)
    url_f = ImageFont.truetype(FONT_BOLD, 19)
    tag_f = ImageFont.truetype(FONT_REG, 19)
    btb = draw.textbbox((0,0), "THE LEDGER WIRE", font=url_f)
    utb = draw.textbbox((0,0), "theledgerwire.com", font=tag_f)
    uw = utb[2] - utb[0]
    fy = H - 72 + (72 - btb[3]) // 2
    draw.text((PAD, fy), "THE LEDGER WIRE", font=url_f, fill=NAVY)
    draw.text((W - PAD - uw, fy), "theledgerwire.com", font=tag_f, fill=NAVY)"""

if old in code:
    code = code.replace(old, new, 1)
    print("✓ Footer restored — THE LEDGER WIRE + theledgerwire.com")
else:
    print("⚠ Footer draw_footer not found — may already be fixed")

# Fix 2: Restore FTR_H inside card_with_photo
old2 = "FTR_H   = 6"
new2 = "FTR_H   = 72"
if old2 in code:
    code = code.replace(old2, new2, 1)
    print("✓ FTR_H restored to 72 in card_with_photo")

# Fix 3: Restore global FOOTER_H
old3 = "FOOTER_H  = 6"
new3 = "FOOTER_H  = 72"
if old3 in code:
    code = code.replace(old3, new3, 1)
    print("✓ FOOTER_H restored to 72")

with open("generate_image.py", "w") as f:
    f.write(code)
print("Done — all footer fixes applied")
