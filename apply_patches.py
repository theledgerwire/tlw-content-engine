#!/usr/bin/env python3
"""
TLW v18 → v18.1 Patch Applier
Run this in your repo directory:
  python apply_patches.py
It reads generate_image.py, applies all v18.1 patches, and writes the result.
"""
import re

with open("generate_image.py", "r") as f:
    code = f.read()

patches_applied = 0

# ── PATCH 1: FOOTER_H constant ──
old = "FOOTER_H  = 60"
new = "FOOTER_H  = 6  # v18.1: thin gold strip"
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 1: FOOTER_H 60→6")

# ── PATCH 2: process_photo — remove brightness ──
old = """    photo  = ImageEnhance.Color(photo).enhance(style["saturation"])
    photo  = ImageEnhance.Brightness(photo).enhance(style["brightness"])
    return photo"""
new = """    # v18.1: Slight saturation boost only — NO brightness reduction.
    # The gradient handles all darkening. Pre-darkening kills image quality.
    photo  = ImageEnhance.Color(photo).enhance(min(style["saturation"], 1.05))
    return photo"""
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 2: process_photo — removed brightness pre-darkening")

# ── PATCH 3: apply_gradient — eased curve, no top overlay ──
old = """    # Bottom gradient — starts at 40%, ramps to text area
    for y in range(int(H*start),H):
        t = float(y-H*start)/float(H*(1-start))
        t = max(0.0,min(1.0,t))
        a = int(min(235, 250*t) * op)
        gd.line([(0,y),(W,y)],fill=(*overlay_rgb,a))
    # Top brand bar overlay — lighter so image shows through
    for y in range(0,100):
        t = 1-(y/100)
        a = int(140*t**0.5 * op)
        gd.line([(0,y),(W,y)],fill=(*top_rgb,a))
    return Image.alpha_composite(img.convert("RGBA"),grad).convert("RGB")"""
new = """    # v18.1: Eased gradient — t^0.7 keeps image vivid in the middle,
    # only going opaque in the bottom 25% where text lives.
    for y in range(int(H * start), H):
        t = float(y - H * start) / float(H * (1 - start))
        t = max(0.0, min(1.0, t))
        a = int(255 * min(1.0, t ** 0.7) * op)
        gd.line([(0, y), (W, y)], fill=(*overlay_rgb, a))
    # v18.1: NO top overlay — let the hero image breathe at the top.
    return Image.alpha_composite(img.convert("RGBA"), grad).convert("RGB")"""
if "250*t) * op)" in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 3: apply_gradient — eased curve, removed top overlay")
else:
    # Try looser match
    code = re.sub(
        r'# Bottom gradient.*?return Image\.alpha_composite\(img\.convert\("RGBA"\),grad\)\.convert\("RGB"\)',
        new.lstrip(),
        code,
        flags=re.DOTALL,
        count=1
    )
    patches_applied += 1
    print("✓ Patch 3: apply_gradient (regex match)")

# ── PATCH 4: apply_gradient — remove top_rgb variable ──
old = """    overlay_rgb = (10, 22, 40)  # always navy — brand consistency
    top_rgb     = (10, 22, 40)"""
new = """    overlay_rgb = (10, 22, 40)  # always navy — brand consistency"""
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 4: removed top_rgb variable")

# ── PATCH 5: draw_footer — thin 6px strip ──
old = """def draw_footer(draw):
    PAD=56
    draw.rectangle([(0,H-72),(W,H)],fill=GOLD)
    url_f=ImageFont.truetype(FONT_BOLD,19)
    tag_f=ImageFont.truetype(FONT_REG,19)
    btb=draw.textbbox((0,0),"THE LEDGER WIRE",font=url_f)
    utb=draw.textbbox((0,0),"theledgerwire.com",font=tag_f)
    uw=utb[2]-utb[0]
    fy=H-72+(72-btb[3])//2
    draw.text((PAD,fy),"THE LEDGER WIRE",font=url_f,fill=NAVY)
    draw.text((W-PAD-uw,fy),"theledgerwire.com",font=tag_f,fill=NAVY)"""
new = """def draw_footer(draw):
    # v18.1: Thin 6px gold strip — clean, minimal, no text clutter.
    draw.rectangle([(0, H - 6), (W, H)], fill=GOLD)"""
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 5: draw_footer — thin 6px strip")

# ── PATCH 6: card_with_photo — bigger stat, full bar, rounded badge ──
old = '    FTR_H   = 72  # footer height'
new = '    FTR_H   = 6  # v18.1: thin footer strip'
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 6a: card_with_photo FTR_H 72→6")

old = '    h1_f    = ImageFont.truetype(FONT_BOLD, 150)  # gold stat — hero size'
new = '    h1_f    = ImageFont.truetype(FONT_BOLD, 180)   # v18.1: 150→180 (hero stat)'
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 6b: H1 stat 150→180pt")

old = '    badge_f = ImageFont.truetype(FONT_BOLD, 16)'
new = '    badge_f = ImageFont.truetype(FONT_BOLD, 18)   # v18.1: 16→18'
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 6c: badge font 16→18pt")

old = '    body_f  = ImageFont.truetype(FONT_MED,  26)   # grey body lines'
new = '    body_f  = ImageFont.truetype(FONT_MED,  28)    # v18.1: 26→28'
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 6d: body font 26→28pt")

old = '    draw.rectangle([(0, 0), (10, H - FTR_H)], fill=GOLD)'
new = '    draw.rectangle([(0, 0), (10, H)], fill=GOLD)  # v18.1: full height'
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 6e: gold bar full height")

old = '    draw.rectangle([(40, mb[3] + 4), (40 + 130, mb[3] + 7)], fill=GOLD)'
new = """    mark_w = mb[2] - mb[0]
    draw.rectangle([(40, mb[3] + 4), (40 + mark_w, mb[3] + 7)], fill=GOLD)  # v18.1: match text width"""
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 6f: underline matches text width")

# Replace source badge with rounded rectangle
old = """        draw.rectangle(
            [(box_x, box_y), (box_x + box_w, box_y + box_h)],
            outline=GOLD, width=2
        )
        draw.text((box_x + pad_x, box_y + pad_y - 2), source, font=badge_f, fill=GOLD)"""
new = """        draw.rounded_rectangle(
            [(box_x, box_y), (box_x + box_w, box_y + box_h)],
            radius=4, outline=GOLD, width=2
        )
        draw.text((box_x + pad_x, box_y + pad_y + 1), source, font=badge_f, fill=GOLD)"""
if "draw.rectangle(\n            [(box_x, box_y)" in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 6g: rounded source badge")

# Auto-size cascade 180→150→120
old = """    h1_test = draw.textbbox((0, 0), h1, font=h1_f)
    if (h1_test[2] - h1_test[0]) > MTW:
        h1_f = ImageFont.truetype(FONT_BOLD, 120)"""
new = """    h1_test = draw.textbbox((0, 0), h1, font=h1_f)
    if (h1_test[2] - h1_test[0]) > MTW:
        h1_f = ImageFont.truetype(FONT_BOLD, 150)
        h1_test2 = draw.textbbox((0, 0), h1, font=h1_f)
        if (h1_test2[2] - h1_test2[0]) > MTW:
            h1_f = ImageFont.truetype(FONT_BOLD, 120)"""
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 6h: auto-size cascade 180→150→120")

# Bottom spacing
old = "    body_y = footer_top - 28 - body_block_h"
new = "    body_y = footer_top - 40 - body_block_h  # v18.1: more breathing room"
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 6i: bottom spacing increased")

old = '    print("Card saved (photo mode — v18 template)")'
new = '    print("Card saved (photo mode — v18.1 template)")'
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 6j: version string")

# ── PATCH 7: Add _estimate_baseline helper ──
baseline_func = '''
# ── ESTIMATE BASELINE FOR CHART COMPARISON ────────────────────
def _estimate_baseline(stat_hook):
    """
    v18.1: Estimate a 'before' value from the stat hook for chart comparison.
    """
    if not stat_hook:
        return "0"
    import re as _re2
    m = _re2.search(r'([+-]?)([\\d.]+)%', stat_hook)
    if m:
        sign = m.group(1)
        val  = float(m.group(2))
        if sign == '+':
            baseline = max(1, val * 0.35)
        elif sign == '-':
            baseline = val + 30
        else:
            baseline = max(1, val * 0.5)
        return f"{baseline:.0f}%"
    m = _re2.search(r'\\$?([\\d.]+)([BMKT]?)', stat_hook)
    if m:
        val = float(m.group(1))
        suffix = m.group(2)
        baseline = max(0.1, val * 0.4)
        return f"${baseline:.1f}{suffix}"
    m = _re2.search(r'([\\d,]+)', stat_hook)
    if m:
        val = float(m.group(1).replace(',', ''))
        return f"{int(val * 0.3):,}"
    return "0"

'''
marker = "# ── CLAUDE: NEWS (legacy fallback"
if marker in code and "_estimate_baseline" not in code:
    code = code.replace(marker, baseline_func + marker, 1)
    patches_applied += 1
    print("✓ Patch 7: added _estimate_baseline helper")

# ── PATCH 8: Fix blob compare values ──
old = '''        "compare_a_label": "Before",
        "compare_a_value": "",
        "compare_b_label": "Now",
        "compare_b_value": TLW_STORY.get("stat_hook", ""),'''
new = '''        "compare_a_label": TLW_STORY.get("compare_a_label", "Before"),
        "compare_a_value": TLW_STORY.get("compare_a_value", _estimate_baseline(TLW_STORY.get("stat_hook", ""))),
        "compare_b_label": TLW_STORY.get("compare_b_label", "Now"),
        "compare_b_value": TLW_STORY.get("stat_hook", ""),'''
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 8: blob compare values use _estimate_baseline")

# ── PATCH 9: post_to_buffer_document — thumbnail_url param ──
old = 'def post_to_buffer_document(post_text, doc_url, channel_id, api_key, retries=2):'
new = 'def post_to_buffer_document(post_text, doc_url, channel_id, api_key, thumbnail_url=None, retries=2):'
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 9a: post_to_buffer_document — added thumbnail_url param")

old = """    query = (
        'mutation CreatePost {\\n'
        '  createPost(input: {\\n'
        '    text: "%s",\\n'
        '    channelId: "%s",\\n'
        '    schedulingType: automatic,\\n'
        '    mode: addToQueue,\\n'
        '    assets: { documents: [{ url: "%s", title: "The Ledger Wire", thumbnailUrl: "%s" }] }\\n'
        '  }) {\\n'
        '    ... on PostActionSuccess { post { id text } }\\n'
        '    ... on MutationError { message }\\n'
        '  }\\n'
        '}'
    ) % (safe_text, cid, doc_url, doc_url)"""
new = """    thumb = thumbnail_url or doc_url
    query = (
        'mutation CreatePost {\\n'
        '  createPost(input: {\\n'
        '    text: "%s",\\n'
        '    channelId: "%s",\\n'
        '    schedulingType: automatic,\\n'
        '    mode: addToQueue,\\n'
        '    assets: { documents: [{ url: "%s", title: "The Ledger Wire", thumbnailUrl: "%s" }] }\\n'
        '  }) {\\n'
        '    ... on PostActionSuccess { post { id text } }\\n'
        '    ... on MutationError { message }\\n'
        '  }\\n'
        '}'
    ) % (safe_text, cid, doc_url, thumb)"""
if "doc_url, doc_url)" in code:
    code = code.replace(") % (safe_text, cid, doc_url, doc_url)", """) % (safe_text, cid, doc_url, thumb)""", 1)
    code = code.replace("    query = (\n", "    thumb = thumbnail_url or doc_url\n    query = (\n", 1)
    patches_applied += 1
    print("✓ Patch 9b: thumbnailUrl uses card image")

# ── PATCH 10: LinkedIn carousel — 20s wait + thumbnail ──
old = "                        time.sleep(5)\n                        ok_li = post_to_buffer_document(linkedin_text, pdf_url, BUFFER_PROFILE_LI, BUFFER_API_KEY)"
new = """                        # v18.1: Wait 20s for GitHub raw URL propagation (was 5s)
                        print("Waiting 20s for GitHub raw URL propagation...")
                        time.sleep(20)
                        ok_li = post_to_buffer_document(linkedin_text, pdf_url, BUFFER_PROFILE_LI, BUFFER_API_KEY, thumbnail_url=RAW_URL)"""
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 10: LinkedIn carousel — 20s wait + thumbnail")

# ── PATCH 11: Remove Instagram PDF carousel ──
ig_old = """        # Instagram
        if BUFFER_PROFILE_IG:
            time.sleep(3)
            ig_posted = False
            if do_carousel and stat_number:
                print("--- Building Instagram PDF carousel ---")"""
ig_new = """        # Instagram — v18.1: always single image (IG doesn't support document posts)
        if BUFFER_PROFILE_IG:
            time.sleep(3)
            ig_posted_skip = True  # v18.1: skip PDF carousel for IG
            if False:  # v18.1: disabled — IG doesn't support docs
                print("--- Building Instagram PDF carousel ---")"""
if ig_old in code:
    code = code.replace(ig_old, ig_new, 1)
    patches_applied += 1
    print("✓ Patch 11: disabled IG PDF carousel")

# ── PATCH 12: Better carousel diagnostics ──
old = 'print(f"DEBUG carousel fields — stat_label:\'{stat_label}\' | fact1:\'{fact1}\' | fact2:\'{fact2}\'")'
new = """print(f"DEBUG carousel fields — stat_label:'{stat_label}' | fact1:'{fact1}' | fact2:'{fact2}'")
print(f"DEBUG compare — A:'{compare_a_label}'='{compare_a_value}' | B:'{compare_b_label}'='{compare_b_value}'")
if not do_carousel:
    _reasons = []
    if story_tier != "1": _reasons.append(f"tier={story_tier} (need 1)")
    if not stat_is_real: _reasons.append(f"stat '{stat_number}' has no $/%/digit")
    if not carousel_allowed(): _reasons.append("daily limit reached")
    print(f"CAROUSEL SKIPPED — reasons: {', '.join(_reasons)}")"""
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 12: better carousel diagnostics")

# ── PATCH 13: Version string ──
old = '=== TLW v18 ==='
new = '=== TLW v18.1 ==='
if old in code:
    code = code.replace(old, new, 1)
    patches_applied += 1
    print("✓ Patch 13: version string v18→v18.1")

# ── Write patched file ──
with open("generate_image.py", "w") as f:
    f.write(code)

print(f"\n{'='*50}")
print(f"DONE — {patches_applied} patches applied")
print(f"File saved: generate_image.py (v18.1)")
print(f"{'='*50}")

if patches_applied < 10:
    print(f"\n⚠ WARNING: Only {patches_applied} patches matched.")
    print("Some patches may not have found their targets.")
    print("Check that generate_image.py is the unmodified v18 version.")
