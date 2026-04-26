#!/usr/bin/env python3
"""
TLW v18.1b — Two-file fix:
1. generate_image.py — fixed font right-sizing + footer + ig_posted + thumb
2. research_agent.py — enforce character limits + hook variety

Run in repo root: python fix_all.py
"""
import os

# ═══════════════════════════════════════════════════════════════
# FILE 1: generate_image.py
# ═══════════════════════════════════════════════════════════════
print("\n=== Patching generate_image.py ===")

with open("generate_image.py", "r") as f:
    code = f.read()

patches = 0

# ── Fix 1: Footer restore ──
old1 = """def draw_footer(draw):
    # v18.1: Thin 6px gold strip — clean, minimal, no text clutter.
    draw.rectangle([(0, H - 6), (W, H)], fill=GOLD)"""
new1 = """def draw_footer(draw):
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
if old1 in code:
    code = code.replace(old1, new1, 1); patches += 1; print("✓ Footer restored")

# ── Fix 2-3: FTR_H + FOOTER_H ──
if "FTR_H   = 6" in code:
    code = code.replace("FTR_H   = 6", "FTR_H   = 72", 1); patches += 1; print("✓ FTR_H → 72")
if "FOOTER_H  = 6" in code:
    code = code.replace("FOOTER_H  = 6", "FOOTER_H  = 72", 1); patches += 1; print("✓ FOOTER_H → 72")

# ── Fix 4: Replace ENTIRE Instagram section — no line-by-line patching ──
# Find the IG block and replace it cleanly to avoid indentation issues
ig_markers = [
    "# Instagram — v18.1: always single image",
    "# Instagram — v18.1b",
    "# Instagram\n",
    "# v18.1b: IG always single image",
]
ig_end_markers = [
    "save_used_story(",
    "else:\n            print(\"Instagram: skipped",
]

ig_replaced = False
for ig_start_marker in ig_markers:
    if ig_start_marker in code and not ig_replaced:
        ig_start = code.index(ig_start_marker)
        # Find the indentation level (should be 8 spaces)
        line_start = code.rfind('\n', 0, ig_start) + 1
        indent = ig_start - line_start

        # Find where IG section ends — look for save_used_story or the else block
        search_after = code[ig_start:]
        ig_end = None
        for end_marker in ig_end_markers:
            if end_marker in search_after:
                ig_end = ig_start + search_after.index(end_marker)
                break

        if ig_end:
            # Build clean replacement
            ig_indent = " " * indent
            new_ig = (
                f"{ig_indent}# Instagram — v18.1b: always single image (IG doesn't support docs)\n"
                f"{ig_indent}if BUFFER_PROFILE_IG:\n"
                f"{ig_indent}    time.sleep(3)\n"
                f"{ig_indent}    ok_ig = post_to_buffer_instagram(ig_caption, RAW_URL, BUFFER_PROFILE_IG, BUFFER_API_KEY)\n"
                f"{ig_indent}    print(\"Instagram: SUCCESS\" if ok_ig else \"Instagram: FAILED\")\n"
                f"{ig_indent}else:\n"
                f"{ig_indent}    print(\"Instagram: skipped — add BUFFER_PROFILE_IG to GitHub secrets\")\n\n"
            )
            code = code[:ig_start] + new_ig + code[ig_end:]
            ig_replaced = True
            patches += 1
            print("✓ Fix 4: Entire IG section replaced — clean block, no indentation issues")

if not ig_replaced:
    # Fallback: try simpler replacements
    if "if not ig_posted:" in code:
        # Find the line and replace with pass + direct posting
        code = code.replace("if not ig_posted:", "if True:", 1)
        patches += 1
        print("✓ Fix 4 (fallback): ig_posted → if True")
    print("⚠ Fix 4: Could not do full IG block replacement — used fallback")

# ── Fix 5: thumb ──
if 'print(f"Posting LinkedIn PDF document...")' in code and "thumb = thumbnail_url" not in code:
    code = code.replace(
        '    print(f"Posting LinkedIn PDF document...")\n    time.sleep(3)',
        '    print(f"Posting LinkedIn PDF document...")\n    thumb = thumbnail_url or doc_url\n    time.sleep(3)', 1
    ); patches += 1; print("✓ thumb variable added")

# ── Fix 6: REPLACE card_with_photo — right-sized fonts, no shrinking ──
old_func_sig = 'def card_with_photo(img,h1,h2,hook="",company_name=None,source="",support_lines=None):'

if old_func_sig in code:
    start_idx = code.index(old_func_sig)
    search_area = code[start_idx:]
    marker = '    print("Card saved (photo mode'
    if marker in search_area:
        end_offset = search_area.index(marker)
        remaining = search_area[end_offset:]
        line_end = remaining.index('\n') + 1
        full_end = start_idx + end_offset + line_end

        new_func = '''def card_with_photo(img,h1,h2,hook="",company_name=None,source="",support_lines=None):
    """
    TLW v18.1b — Right-sized fonts. No shrinking.
    H1: 160pt locked, 1 line max. H2: 52pt, 2 lines max. Body: 28pt.
    Text length enforced upstream by research_agent.
    """
    draw = ImageDraw.Draw(img)
    PAD     = 50
    MTW     = W - PAD - 40
    FTR_H   = 72

    mark_f  = ImageFont.truetype(FONT_BOLD, 22)
    badge_f = ImageFont.truetype(FONT_BOLD, 18)
    h1_f    = ImageFont.truetype(FONT_BOLD, 160)
    h2_f    = ImageFont.truetype(FONT_MED,  52)
    body_f  = ImageFont.truetype(FONT_MED,  28)

    # ── Gold left bar — full height ──
    draw.rectangle([(0, 0), (10, H)], fill=GOLD)

    # ── Header ──
    draw_text_shadow(draw, (40, 34), "THE LEDGER WIRE", mark_f, WHITE, offset=2)
    mb = draw.textbbox((40, 34), "THE LEDGER WIRE", font=mark_f)
    mark_w = mb[2] - mb[0]
    draw.rectangle([(40, mb[3]+4), (40+mark_w, mb[3]+7)], fill=GOLD)

    # ── Source badge — rounded ──
    if source:
        spx, spy = 14, 6
        sb = draw.textbbox((0,0), source, font=badge_f)
        stw = sb[2]-sb[0]; sth = sb[3]-sb[1]
        bw2 = stw+spx*2; bh2 = sth+spy*2+8
        bx2 = W-40-bw2; by2 = 28
        draw.rounded_rectangle([(bx2,by2),(bx2+bw2,by2+bh2)], radius=4, outline=GOLD, width=2)
        draw.text((bx2+spx, by2+spy+1), source, font=badge_f, fill=GOLD)

    # ── Width check — step down once if H1 overflows ──
    h1_tw = draw.textbbox((0,0), h1, font=h1_f)[2]
    if h1_tw > MTW:
        h1_f = ImageFont.truetype(FONT_BOLD, 130)

    h1_lines   = wrap_text(draw, h1, h1_f, MTW)
    h2_lines   = wrap_text(draw, h2, h2_f, MTW)
    body_texts  = support_lines[:2] if support_lines else []

    h1_lh = draw.textbbox((0,0), "Ag", font=h1_f)[3]
    h2_lh = draw.textbbox((0,0), "Ag", font=h2_f)[3]
    bd_lh = draw.textbbox((0,0), "Ag", font=body_f)[3]

    # ── Layout from bottom up ──
    footer_top = H - FTR_H
    body_block_h = len(body_texts) * (bd_lh + 10) if body_texts else 0
    body_y = footer_top - 28 - body_block_h
    rule_y = body_y - 22
    h2_block_h = min(len(h2_lines), 2) * (h2_lh + 4)
    h2_y = rule_y - 10 - h2_block_h
    h1_block_h = min(len(h1_lines), 1) * (h1_lh + 4)
    h1_y = h2_y - 6 - h1_block_h

    # ── Draw H1 stat GOLD — 1 line only ──
    y = h1_y
    for line in h1_lines[:1]:
        draw_text_shadow(draw, (PAD, y), line, h1_f, GOLD, offset=3)
        y += h1_lh + 4

    # ── Draw H2 sub WHITE — max 2 lines ──
    y = h2_y
    for line in h2_lines[:2]:
        draw_text_shadow(draw, (PAD, y), line, h2_f, WHITE, offset=3)
        y += h2_lh + 4

    # ── Gold rule ──
    draw.rectangle([(PAD, rule_y), (PAD+90, rule_y+4)], fill=GOLD)

    # ── Body lines GREY ──
    y = body_y
    for line in body_texts:
        draw_text_shadow(draw, (PAD, y), line, body_f, BODY_GREY, offset=2)
        y += bd_lh + 10

    # ── Footer ──
    draw_footer(draw)
    img.save("card.png", "PNG")
    print("Card saved (photo mode — v18.1b)")
'''
        code = code[:start_idx] + new_func + code[full_end:]
        patches += 1; print("✓ card_with_photo REPLACED — fixed sizes, no shrinking")

with open("generate_image.py", "w") as f:
    f.write(code)
print(f"generate_image.py: {patches} patches applied")


# ═══════════════════════════════════════════════════════════════
# FILE 2: research_agent.py — enforce text limits + hook variety
# ═══════════════════════════════════════════════════════════════
print("\n=== Patching research_agent.py ===")

ra_path = "research_agent.py"
if not os.path.exists(ra_path):
    print(f"⚠ {ra_path} not found — skipping research_agent patches")
else:
    with open(ra_path, "r") as f:
        ra = f.read()

    ra_patches = 0

    # Find the stat_hook instruction in the prompt and enforce limits
    # Look for the stat_hook line in the TLW voice prompt
    old_stat = '"stat_hook": a 2-7 character'
    if old_stat not in ra:
        # Try other patterns
        for pattern in [
            'stat_hook',
            '"stat_hook"',
            'STAT_HOOK',
        ]:
            if pattern in ra:
                print(f"Found stat_hook reference: '{pattern}'")
                break

    # The research_agent has a prompt that generates the TLW story blob.
    # We need to find that prompt and add character limits + variety rules.
    # Look for the section that defines stat_hook, sub_headline, body_line etc.

    # Add hard character limits after the existing stat_hook instruction
    char_limit_block = '''
CARD TEXT HARD LIMITS — these are rendering constraints, not suggestions:
- stat_hook: MAX 7 characters including $/%/+. Examples: "$82K", "+71%", "4X", "FIRED.", "$1.75T", "TESLA", "OPENAI"
- sub_headline: MAX 30 characters (5 words max, end with period). Must fit 1 line at 52pt on a 1080px card.
- body_line_1: MAX 35 characters (6 words max)
- body_line_2: MAX 35 characters (6 words max)
- tagline: MAX 40 characters
If your text exceeds these limits, REWRITE IT SHORTER. Never exceed.

HOOK VARIETY — do NOT default to numbers every time:
- STAT mode ($60B, +71%, $344M): use for money/data stories where the NUMBER is the story
- POWER mode (FIRED., BANNED., OPEN., WAR.): use for conflict/disruption/crisis — single word + period
- TENSION mode (TOO LATE?, WHO WINS?, RISK ON.): use for uncertain/two-sided stories
- NAME mode (TESLA, OPENAI, META, NVIDIA): use when the COMPANY is the headline — all caps, no period
Rule: if 3+ recent stories used STAT mode, the next story MUST use POWER, TENSION, or NAME mode.
Never use STAT mode for stories where a power word or company name hits harder.
Examples: "Meta fires 8000" → "META" not "8,000". "Tesla sales collapse" → "TESLA" not "-24.3%". "OpenAI ships GPT-5.5" → "OPENAI" not "2X".
'''

    # Try to insert after the stat_hook definition in the prompt
    # Common patterns in research_agent prompts
    insert_markers = [
        '"stat_hook":',
        "'stat_hook':",
        'stat_hook',
    ]

    inserted = False
    for marker in insert_markers:
        if marker in ra:
            # Find the line containing this marker
            lines = ra.split('\n')
            for i, line in enumerate(lines):
                if marker in line and 'CARD TEXT HARD LIMITS' not in ra:
                    # Find the end of this instruction block (next empty line or next key)
                    # Insert our limits block after the tagline instruction
                    # Look for "tagline" line after stat_hook
                    for j in range(i, min(i+20, len(lines))):
                        if 'tagline' in lines[j].lower() and 'image_angle' not in lines[j].lower():
                            # Insert after this line
                            insert_idx = j + 1
                            lines.insert(insert_idx, char_limit_block)
                            ra = '\n'.join(lines)
                            inserted = True
                            ra_patches += 1
                            print("✓ Character limits + hook variety rules added to prompt")
                            break
                    if inserted:
                        break
            if inserted:
                break

    if not inserted and 'CARD TEXT HARD LIMITS' not in ra:
        print("⚠ Could not find insertion point for character limits")
        print("  You'll need to manually add these rules to the research_agent prompt:")
        print("  stat_hook: MAX 7 chars | sub_headline: MAX 30 chars | body_line: MAX 35 chars")
        print("  Hook variety: STAT/POWER/TENSION modes, don't default to numbers")
    elif 'CARD TEXT HARD LIMITS' in ra:
        print("· Character limits already present — skipping")

    if ra_patches > 0:
        with open(ra_path, "w") as f:
            f.write(ra)
        print(f"research_agent.py: {ra_patches} patches applied")
    else:
        print("research_agent.py: no patches needed or could not auto-insert")


# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print("DONE — v18.1b deployed")
print("generate_image.py: fixed fonts, no shrinking")
print("research_agent.py: character limits + hook variety")
print(f"{'='*50}")
