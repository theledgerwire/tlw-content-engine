# TLW Flux.1 Test Script
# Run via GitHub Actions to test image generation
import os
import requests
import time

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FAL_KEY       = os.environ.get("FAL_KEY", "")

# Test story
TEST_TITLE   = "Morgan Stanley launches Bitcoin ETF — first major US bank"
TEST_SUMMARY = "Morgan Stanley spot Bitcoin ETF launched with $34M first day volume, 16,000 advisors selling in-house, lowest fee at 0.14%"

# ── STEP 1: Claude generates image prompt ────────────────────────
def generate_image_prompt(title, summary):
    print(f"Generating image prompt for: {title[:50]}...")
    prompt = f"""You are an AI image director for The Ledger Wire, a finance and AI newsletter.

Story: {title}
Summary: {summary}

Write a Flux.1 image generation prompt that:
1. Visually represents THIS specific story
2. Dark cinematic style, navy blue and gold tones
3. No text, no logos, no faces
4. Photorealistic, dramatic lighting
5. Max 25 words

Examples:
- Bitcoin ETF → "Wall Street trading floor at night, golden Bitcoin symbol on screens, dramatic cinematic lighting, navy blue tones, photorealistic"
- AI jobs → "Empty corporate office night, vacant chairs, blue screen glow, dramatic shadows, cinematic"
- Fed rates → "Federal Reserve neoclassical columns, stormy sky, gold light, dramatic"

Reply with ONLY the image prompt, nothing else."""

    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=30
    )
    if r.status_code == 200:
        img_prompt = r.json()["content"][0]["text"].strip()
        print(f"Image prompt: {img_prompt}")
        return img_prompt
    else:
        print(f"Claude error: {r.status_code}")
        return "Wall Street trading floor at night, golden light, cinematic, navy blue, photorealistic"

# ── STEP 2: Flux.1 generates image ───────────────────────────────
def generate_flux_image(img_prompt):
    print(f"Generating Flux image...")
    r = requests.post(
        "https://fal.run/fal-ai/flux-pro/v1.1",
        headers={
            "Authorization": f"Key {FAL_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "prompt": img_prompt + ", TLW style, dark cinematic, navy blue gold, no text, photorealistic",
            "image_size": "square_hd",
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
            "num_images": 1,
            "safety_tolerance": "2"
        },
        timeout=60
    )
    print(f"Flux status: {r.status_code}")
    if r.status_code == 200:
        data    = r.json()
        img_url = data["images"][0]["url"]
        print(f"Flux image URL: {img_url}")
        
        # Download image
        img_data = requests.get(img_url, timeout=30).content
        with open("flux_test.jpg", "wb") as f:
            f.write(img_data)
        print(f"Image saved: flux_test.jpg ({len(img_data)/1024:.0f}KB)")
        return "flux_test.jpg"
    else:
        print(f"Flux error: {r.text[:300]}")
        return None

# ── STEP 3: Build TLW card with generated image ──────────────────
def build_card_with_image(img_path, title):
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance
    from io import BytesIO

    W, H   = 1080, 1080
    GOLD   = (245, 197, 24)
    WHITE  = (255, 255, 255)
    NAVY   = (10, 22, 40)
    DGREY  = (100, 115, 148)
    FONT_B = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    FONT_R = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

    # Load and process image
    photo  = Image.open(img_path).convert("RGB")
    pw, ph = photo.size
    scale  = max(W/pw, H/ph)
    nw, nh = int(pw*scale), int(ph*scale)
    photo  = photo.resize((nw, nh), Image.LANCZOS)
    left   = (nw-W)//2
    top    = (nh-H)//2
    photo  = photo.crop((left, top, left+W, top+H))
    photo  = ImageEnhance.Brightness(photo).enhance(0.55)

    # Apply gradient
    grad = Image.new("RGBA", (W,H), (0,0,0,0))
    gd   = ImageDraw.Draw(grad)
    for y in range(int(H*0.3), H):
        t = (y - H*0.3) / (H*0.7)
        a = int(255 * min(1.0, t**0.78))
        gd.line([(0,y),(W,y)], fill=(10,22,40,a))
    img = Image.alpha_composite(photo.convert("RGBA"), grad).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Gold left bar
    draw.rectangle([(0,0),(6,H-72)], fill=GOLD)

    # Brand
    logo_f = ImageFont.truetype(FONT_B, 20)
    draw.text((56,36), "THE LEDGER WIRE", font=logo_f, fill=WHITE)
    lb = draw.textbbox((0,0), "THE LEDGER WIRE", font=logo_f)
    draw.rectangle([(56,60),(56+lb[2]-lb[0],63)], fill=GOLD)

    # H1
    h1_f = ImageFont.truetype(FONT_B, 90)
    draw.rectangle([(56, H-72-400), (108, H-72-396)], fill=GOLD)
    draw.text((56, H-72-380), "$34M.", font=h1_f, fill=WHITE)

    # H2
    h2_f = ImageFont.truetype(FONT_B, 46)
    draw.text((56, H-72-270), "Morgan Stanley. Bitcoin ETF.", font=h2_f, fill=GOLD)

    # Hook
    hook_f = ImageFont.truetype(FONT_B, 44)
    draw.text((56, H-72-190), "First major US bank.", font=hook_f, fill=WHITE)
    draw.text((56, H-72-136), "The distribution war begins.", font=hook_f, fill=GOLD)

    # Source
    src_f = ImageFont.truetype(FONT_R, 19)
    draw.text((56, H-72-60), "theledgerwire.com", font=src_f, fill=DGREY)

    # Footer
    draw.rectangle([(0,H-72),(W,H)], fill=GOLD)
    draw.text((56, H-72+26), "THE LEDGER WIRE", font=ImageFont.truetype(FONT_B,19), fill=NAVY)
    draw.text((W-230, H-72+26), "theledgerwire.com", font=ImageFont.truetype(FONT_R,19), fill=NAVY)

    img.save("flux_card_test.png", "PNG")
    print("Card saved: flux_card_test.png")
    return "flux_card_test.png"

# ── MAIN ─────────────────────────────────────────────────────────
print("=== TLW Flux.1 Test ===")
print(f"FAL_KEY: {'set' if FAL_KEY else 'MISSING'}")
print(f"ANTHROPIC_KEY: {'set' if ANTHROPIC_KEY else 'MISSING'}")

img_prompt = generate_image_prompt(TEST_TITLE, TEST_SUMMARY)
time.sleep(2)
img_path   = generate_flux_image(img_prompt)

if img_path:
    card_path = build_card_with_image(img_path, TEST_TITLE)
    print(f"\n✅ SUCCESS — Card ready: {card_path}")
else:
    print("\n❌ Flux generation failed")
