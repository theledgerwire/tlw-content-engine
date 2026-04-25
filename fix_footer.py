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

# Fix 4: Fix ig_posted NameError — the v18.1 patch broke Instagram posting
# The patch renamed ig_posted to ig_posted_skip but left "if not ig_posted:" reference
# IG should ALWAYS post single image, so replace with "if True:"
old4 = "if not ig_posted:"
new4 = "if True:  # v18.1 fix: always single image for IG"
if old4 in code:
    code = code.replace(old4, new4, 1)
    print("✓ Fixed ig_posted NameError → always post single image")

# Clean up the broken ig_posted_skip variable if present
old4b = "ig_posted_skip = True  # v18.1: skip PDF carousel for IG"
if old4b in code:
    code = code.replace(old4b, "# v18.1: IG always single image (no PDF carousel)", 1)
    print("✓ Cleaned up ig_posted_skip flag")

# If original ig_posted pattern still exists (un-patched), fix it too
if "ig_posted = False" in code and "ig_posted" in code:
    code = code.replace("ig_posted = False\n", "", 1)
    if "ig_posted = True" in code:
        code = code.replace("ig_posted = True\n", "", 1)
    if "if not ig_posted:" in code:
        code = code.replace("if not ig_posted:", "if True:  # always single image for IG", 1)
    print("✓ Removed all ig_posted references")

# Fix 5: thumb not defined in post_to_buffer_document
# The patch changed doc_url to thumb in the format string but never created the variable
# Target specifically post_to_buffer_document using unique print statement
old5 = '    print(f"Posting LinkedIn PDF document...")\n    time.sleep(3)'
new5 = '    print(f"Posting LinkedIn PDF document...")\n    thumb = thumbnail_url or doc_url  # v18.1b fix\n    time.sleep(3)'
if old5 in code and "thumb = thumbnail_url" not in code:
    code = code.replace(old5, new5, 1)
    print("✓ Fixed thumb variable in post_to_buffer_document")
elif "thumb = thumbnail_url" in code:
    print("✓ thumb variable already exists — skipping")

# Fix 6: H1 stat hook too large for word hooks — add better auto-sizing
# The 180pt works for "$104" but overflows for "18 DAYS" or "LAZARUS"
# Replace the auto-size cascade to also check total text height
old6 = """    h1_f    = ImageFont.truetype(FONT_BOLD, 180)"""
new6 = """    h1_f    = ImageFont.truetype(FONT_BOLD, 160)   # v18.1b: 180→160 for better fit"""
if old6 in code:
    code = code.replace(old6, new6, 1)
    print("✓ H1 stat hook 180→160pt for better fit")

with open("generate_image.py", "w") as f:
    f.write(code)
print("Done — all fixes applied (footer + ig_posted + thumb + H1 sizing)")
