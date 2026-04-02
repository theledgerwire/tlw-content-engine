# TLW v11 - Posts to X + LinkedIn, text wrapping, strict filter
import os
import time
import requests
import base64
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

BUFFER_API_KEY   = os.environ.get("BUFFER_API_KEY", "")
BUFFER_PROFILE_X = os.environ.get("BUFFER_PROFILE_X", "")
BUFFER_PROFILE_LI= os.environ.get("BUFFER_PROFILE_LI", "")
GITHUB_TOKEN     = os.environ.get("GITHUB_TOKEN", "")
ANTHROPIC_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")
UNSPLASH_KEY     = os.environ.get("UNSPLASH_KEY", "")
PEXELS_KEY       = os.environ.get("PEXELS_KEY", "")
STORY_TITLE      = os.environ.get("STORY_TITLE", "")
STORY_SUMMARY    = os.environ.get("STORY_SUMMARY", "")
IMAGE_KEYWORD    = os.environ.get("IMAGE_KEYWORD", "finance technology")

REPO             = "theledgerwire/tlw-content-engine"
IMAGE_PATH       = f"cards/card_{int(time.time())}.png"
RAW_URL          = f"https://raw.githubusercontent.com/{REPO}/main/{IMAGE_PATH}"

W, H      = 1080, 1080
GOLD      = (240, 185, 11)
WHITE     = (255, 255, 255)
NAVY      = (4, 8, 20)
LGREY     = (175, 190, 215)
DGREY     = (100, 115, 148)
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

print("=== TLW Card Generator v11 ===")
print(f"Story: {STORY_TITLE[:60]}...")

def call_claude(title, summary):
    if not ANTHROPIC_KEY:
        print("No Anthropic key — using title as fallback")
        return None

    prompt = f"""You are a strict content filter for The Ledger Wire — an AI and Finance newsletter.

Story title: {title}
Story summary: {summary}

Reply SKIP if the story is primarily about ANY of these:
- Geopolitics, war, military, Iran, Middle East, Russia, China politics
- Food, consumer products, coffee, restaurants
- Sports, entertainment, celebrities
- General manufacturing or trade unless directly about AI or fintech

Reply SKIP unless the story is DIRECTLY and PRIMARILY about:
- Artificial intelligence in finance or banking
- Federal Reserve, interest rates, inflation policy
- Major bank earnings or AI strategy (JPMorgan, Goldman, BlackRock etc)
- Fintech companies or cryptocurrency
- Stock market moves caused specifically by AI or tech earnings

If relevant, reply in this EXACT format with no extra text:
TWEET: [tweet STRICTLY under 220 chars including spaces, lead with surprise, make it personal, end with dry wit, finish with → theledgerwire.com #AI #Finance]
H1: [3-4 words, gut punch headline, write like texting a smart friend, use "you" or action words, never corporate language like deploys/utilizes/leverages, no asterisks. Examples: "Your banker is AI." / "Powell said no." / "AI ate banking." / "The Fed blinked."]
H2: [3-4 words, punchy follow-up that adds twist or "so what", creates curiosity, no asterisks. Examples: "Goldman made it official." / "Your mortgage feels it." / "Here's the bill." / "Now what?"]
KEYWORD: [2-3 word Unsplash search term]"""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        print(f"Claude status: {r.status_code}")
        if r.status_code != 200:
            print(f"Claude error: {r.text[:200]}")
            return None

        text = r.json()["content"][0]["text"].strip()
        print(f"Claude response: {text[:200]}")

        if text.strip().upper() == "SKIP":
            print("Claude says SKIP — not relevant")
            return "SKIP"

        result = {}
        for line in text.split("\n"):
            if line.startswith("TWEET:"):
                result["tweet"] = line.replace("TWEET:", "").strip()
            elif line.startswith("H1:"):
                result["h1"] = line.replace("H1:", "").strip()
            elif line.startswith("H2:"):
                result["h2"] = line.replace("H2:", "").strip()
            elif line.startswith("KEYWORD:"):
                result["keyword"] = line.replace("KEYWORD:", "").strip()

        if not result.get("tweet"):
            result["tweet"] = title
        if not result.get("h1"):
            result["h1"] = "Breaking Now"
        if not result.get("h2"):
            result["h2"] = "Read Full Story"
        if not result.get("keyword"):
            result["keyword"] = "finance technology"

        return result

    except Exception as e:
        print(f"Claude exception: {e}")
        return None

def get_pexels_photo(keyword):
    if not PEXELS_KEY:
        return None
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": keyword, "per_page": 10, "orientation": "square"},
            headers={"Authorization": PEXELS_KEY},
            timeout=15
        )
        print(f"Pexels status: {r.status_code}")
        if r.status_code != 200:
            return None
        data = r.json()
        photos = data.get("photos", [])
        if not photos:
            print("Pexels: no photos found")
            return None
        import random
        photo_data = random.choice(photos[:5])
        img_url = photo_data["src"]["large"]
        img_data = requests.get(img_url, timeout=15).content
        from PIL import ImageEnhance
        photo = Image.open(BytesIO(img_data)).convert("RGB")
        pw, ph = photo.size
        scale = max(W/pw, H/ph)
        nw, nh = int(pw*scale), int(ph*scale)
        photo = photo.resize((nw, nh), Image.LANCZOS)
        left = (nw-W)//2
        top = (nh-H)//2
        photo = photo.crop((left, top, left+W, top+H))
        photo = ImageEnhance.Color(photo).enhance(0.78)
        photo = ImageEnhance.Brightness(photo).enhance(0.70)
        print("Pexels photo found")
        return photo
    except Exception as e:
        print(f"Pexels exception: {e}")
        return None

def get_unsplash_photo(keyword):
    if not UNSPLASH_KEY:
        return None
    try:
        r = requests.get(
            "https://api.unsplash.com/photos/random",
            params={"query": keyword, "orientation": "squarish"},
            headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
            timeout=15
        )
        print(f"Unsplash status: {r.status_code}")
        if r.status_code != 200:
            return None
        data = r.json()
        img_url = data["urls"]["regular"]
        img_data = requests.get(img_url, timeout=15).content
        from PIL import ImageEnhance
        photo = Image.open(BytesIO(img_data)).convert("RGB")
        pw, ph = photo.size
        scale = max(W/pw, H/ph)
        nw, nh = int(pw*scale), int(ph*scale)
        photo = photo.resize((nw, nh), Image.LANCZOS)
        left = (nw-W)//2
        top = (nh-H)//2
        photo = photo.crop((left, top, left+W, top+H))
        photo = ImageEnhance.Color(photo).enhance(0.78)
        photo = ImageEnhance.Brightness(photo).enhance(0.70)
        return photo
    except Exception as e:
        print(f"Unsplash exception: {e}")
        return None

def apply_gradient(img, start=0.30):
    grad = Image.new("RGBA", (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(grad)
    for y in range(int(H*start), H):
        t = float(y - H*start) / float(H*(1-start))
        t = max(0.0, min(1.0, t))
        a = int(255 * t**0.78)
        gd.line([(0,y),(W,y)], fill=(4,8,20,a))
    for y in range(0, 88):
        t = 1-(y/88)
        a = int(55 * t**0.55)
        gd.line([(0,y),(W,y)], fill=(4,8,20,a))
    return Image.alpha_composite(img.convert("RGBA"), grad).convert("RGB")

def wrap_text(draw, text, font, max_width):
    """Wrap text to fit within max_width, return list of lines."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        w = draw.textbbox((0,0), test, font=font)[2]
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

def generate_card(headline1, headline2, keyword):
    photo = get_pexels_photo(keyword)
    if not photo:
        print("Pexels failed — trying Unsplash...")
        photo = get_unsplash_photo(keyword)
    if photo:
        img = apply_gradient(photo)
        print("Using Unsplash photo")
    else:
        # Navy gradient fallback
        img = Image.new("RGB", (W, H), NAVY)
        draw_fb = ImageDraw.Draw(img)
        for y in range(0, H):
            t = y / H
            r_val = int(4 + (20-4)*t)
            g_val = int(8 + (30-8)*t)
            b_val = int(20 + (60-20)*t)
            draw_fb.line([(0,y),(W,y)], fill=(r_val, g_val, b_val))
        print("Using navy gradient fallback")

    draw = ImageDraw.Draw(img)
    PAD = 52
    MAX_TEXT_W = W - PAD*2

    # Logo
    logo_f = ImageFont.truetype(FONT_BOLD, 19)
    logo_t = "THE LEDGER WIRE"
    lb = draw.textbbox((0,0), logo_t, font=logo_f)
    lw = lb[2]-lb[0]
    draw.text((PAD, 36), logo_t, font=logo_f, fill=WHITE)
    draw.rectangle([(PAD, 59),(PAD+lw, 62)], fill=GOLD)

    h1_f  = ImageFont.truetype(FONT_BOLD, 72)
    h2_f  = ImageFont.truetype(FONT_BOLD, 60)
    src_f = ImageFont.truetype(FONT_REG, 21)

    # Wrap headlines
    h1_lines = wrap_text(draw, headline1, h1_f, MAX_TEXT_W)
    h2_lines = wrap_text(draw, headline2, h2_f, MAX_TEXT_W)

    # Calculate heights
    h1_line_h = draw.textbbox((0,0), "Ag", font=h1_f)[3]
    h2_line_h = draw.textbbox((0,0), "Ag", font=h2_f)[3]
    src_h     = draw.textbbox((0,0), "theledgerwire.com", font=src_f)[3]

    total_h1 = h1_line_h * len(h1_lines) + 4 * (len(h1_lines)-1)
    total_h2 = h2_line_h * len(h2_lines) + 4 * (len(h2_lines)-1)

    SAFE_BOT = H - 46 - 18
    src_y  = SAFE_BOT - src_h
    l2_y   = src_y - 20 - total_h2
    l1_y   = l2_y - 10 - total_h1
    rule_y = l1_y - 18

    # Gold rule
    draw.rectangle([(PAD, rule_y),(PAD+90, rule_y+4)], fill=GOLD)

    # Draw H1 lines
    y = l1_y
    for line in h1_lines:
        draw.text((PAD, y), line, font=h1_f, fill=WHITE)
        y += h1_line_h + 4

    # Draw H2 lines
    y = l2_y
    for line in h2_lines:
        draw.text((PAD, y), line, font=h2_f, fill=GOLD)
        y += h2_line_h + 4

    draw.text((PAD, src_y), "theledgerwire.com", font=src_f, fill=DGREY)

    # Footer
    draw.rectangle([(0, H-46),(W, H)], fill=NAVY)
    draw.rectangle([(0, H-48),(W, H-46)], fill=GOLD)
    url_f = ImageFont.truetype(FONT_REG, 19)
    tag_f = ImageFont.truetype(FONT_BOLD, 19)
    draw.text((PAD, H-31), "theledgerwire.com", font=url_f, fill=GOLD)
    draw.text((W-220, H-31), "#AI  #Finance", font=tag_f, fill=LGREY)

    img.save("card.png", "PNG")
    print("Card saved: card.png")
    return "card.png"

def push_to_github(image_path, token, repo, file_path):
    print(f"Pushing image to GitHub: {file_path}")
    with open(image_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    get_r = requests.get(
        f"https://api.github.com/repos/{repo}/contents/{file_path}",
        headers=headers
    )
    sha = get_r.json().get("sha") if get_r.status_code == 200 else None
    payload = {"message": "Add card image", "content": content, "branch": "main"}
    if sha:
        payload["sha"] = sha
    put_r = requests.put(
        f"https://api.github.com/repos/{repo}/contents/{file_path}",
        headers=headers,
        json=payload,
        timeout=30
    )
    print(f"GitHub push status: {put_r.status_code}")
    return put_r.status_code in [200, 201]

def post_to_buffer(post_text, image_url, channel_id, api_key, platform=""):
    print(f"Posting to Buffer {platform}...")
    time.sleep(3)
    safe_text = post_text.replace('\\', '\\\\').replace('"', '\\"')
    query = '''mutation CreatePost {
      createPost(input: {
        text: "%s",
        channelId: "%s",
        schedulingType: automatic,
        mode: addToQueue,
        assets: {
          images: [{ url: "%s" }]
        }
      }) {
        ... on PostActionSuccess {
          post { id text }
        }
        ... on MutationError {
          message
        }
      }
    }''' % (safe_text, channel_id.strip(), image_url)
    r = requests.post(
        "https://api.buffer.com",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={"query": query},
        timeout=30
    )
    print(f"Buffer {platform} status: {r.status_code}")
    print(f"Buffer {platform} response: {r.text[:200]}")
    response_data = r.json()
    if "errors" in response_data:
        print(f"Buffer GraphQL errors: {response_data['errors']}")
        return False
    post_data = response_data.get("data", {}).get("createPost", {})
    if "message" in post_data and "post" not in post_data:
        print(f"Buffer error message: {post_data['message']}")
        return False
    return r.status_code == 200

# ── MAIN ──────────────────────────────────────────────────────────
if not STORY_TITLE:
    print("No story title provided — exiting")
    exit(0)

claude_result = call_claude(STORY_TITLE, STORY_SUMMARY)

if claude_result == "SKIP" or claude_result is None:
    print("Story skipped or Claude failed — exiting")
    exit(0)

tweet_text  = claude_result.get("tweet", STORY_TITLE)
headline1   = claude_result.get("h1", "Breaking Now").replace("**", "").replace("*", "").strip()
headline2   = claude_result.get("h2", "Read Full Story").replace("**", "").replace("*", "").strip()
img_keyword = claude_result.get("keyword", IMAGE_KEYWORD)

print(f"Tweet: {tweet_text[:80]}...")
print(f"H1: {headline1}")
print(f"H2: {headline2}")
print(f"Keyword: {img_keyword}")

generate_card(headline1, headline2, img_keyword)

if BUFFER_API_KEY and GITHUB_TOKEN:
    pushed = push_to_github("card.png", GITHUB_TOKEN, REPO, IMAGE_PATH)
    if pushed:
        time.sleep(5)
        if BUFFER_PROFILE_X:
            success_x = post_to_buffer(tweet_text, RAW_URL, BUFFER_PROFILE_X, BUFFER_API_KEY, "X")
            print("X: SUCCESS" if success_x else "X: FAILED")
        if BUFFER_PROFILE_LI:
            time.sleep(3)
            success_li = post_to_buffer(tweet_text, RAW_URL, BUFFER_PROFILE_LI, BUFFER_API_KEY, "LinkedIn")
            print("LinkedIn: SUCCESS" if success_li else "LinkedIn: FAILED")
    else:
        print("FAILED: GitHub push failed")
else:
    missing = [k for k, v in {"BUFFER_API_KEY": BUFFER_API_KEY, "GITHUB_TOKEN": GITHUB_TOKEN}.items() if not v]
    print(f"Missing credentials: {', '.join(missing)}")
