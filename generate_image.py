# TLW v12 - X + LinkedIn separate copy, correct model, card design updated, tweet validation
import os
import re
import time
import requests
import base64
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

BUFFER_API_KEY    = os.environ.get("BUFFER_API_KEY", "")
BUFFER_PROFILE_X  = os.environ.get("BUFFER_PROFILE_X", "")
BUFFER_PROFILE_LI = os.environ.get("BUFFER_PROFILE_LI", "")
GITHUB_TOKEN      = os.environ.get("GITHUB_TOKEN", "")
ANTHROPIC_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
UNSPLASH_KEY      = os.environ.get("UNSPLASH_KEY", "")
STORY_TITLE       = os.environ.get("STORY_TITLE", "")
STORY_SUMMARY     = os.environ.get("STORY_SUMMARY", "")
IMAGE_KEYWORD     = os.environ.get("IMAGE_KEYWORD", "finance technology")

REPO       = "theledgerwire/tlw-content-engine"
IMAGE_PATH = f"cards/card_{int(time.time())}.png"
RAW_URL    = f"https://raw.githubusercontent.com/{REPO}/main/{IMAGE_PATH}"

W, H      = 1080, 1080
GOLD      = (245, 197, 24)
WHITE     = (255, 255, 255)
NAVY      = (10, 22, 40)
LGREY     = (175, 190, 215)
DGREY     = (100, 115, 148)
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

print("=== TLW Card Generator v12 ===")
print(f"Story: {STORY_TITLE[:60]}...")


# ── TWEET CHARACTER COUNT (X counts URLs as 23 chars) ─────────────
def x_char_count(text):
    """Count characters as X does — URLs always = 23 chars."""
    t = re.sub(r'https?://\S+|[\w]+\.com\S*', 'X' * 23, text)
    return len(t)


# ── CLAUDE ────────────────────────────────────────────────────────
def call_claude(title, summary):
    if not ANTHROPIC_KEY:
        print("No Anthropic key — using title as fallback")
        return None

    prompt = f"""You are a strict content filter for The Ledger Wire — an AI and Finance newsletter for North American professionals.

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

TWEET: [Morning Brew style — STRICTLY under 220 chars. Rule: NEVER explain the full story. Create a curiosity gap — give ONE shocking hook that makes them NEED to tap to find out more. Structure: shocking statement or stat → one sentence that raises more questions than it answers → → theledgerwire.com #AI #Finance. Examples of good style: "A bank just replaced 700 people with one AI. Your department is next. → theledgerwire.com #AI #Finance" / "The Fed blinked. Your mortgage rate didn't. Here's why that matters. → theledgerwire.com #AI #Finance" / "Goldman just made it official. AI is doing the job you trained 4 years for. → theledgerwire.com #AI #Finance". NEVER write: "X company did Y and Z happened" — that kills the click.]
LINKEDIN: [Morning Brew style for professionals. Open with ONE punchy statement that stops the scroll — a stat, a quote, or a provocative claim. Then 2-3 short paragraphs that build the story but always leave the "so what for ME" partially unanswered — make them want to read the full briefing. End with a direct question that triggers replies. No link — goes in first comment. NEVER write a press release. Write like a smart colleague sharing intel over coffee.]
H1: [1-3 words ONLY. The shocking STAT or NUMBER — big and visual. This is the first thing eyes land on. Must be a number, dollar amount, or ultra-short gut-shot. Use abbreviations always — never spell out. No asterisks. GOOD: "$60B." / "30,000 jobs." / "$114 oil." / "4% up." / "Week 5." BAD: "$60 Billion" / "Thirty thousand jobs" — too long, kills the punch.]
H2: [2-4 words ONLY. Company name + what happened — gives context to H1. This is the "who" and "what". No asterisks. GOOD: "Anthropic. Going public." / "Oracle. 6am email." / "Brent crude. Iran war." / "Fed. No cuts." / "Goldman. Claude deployed." BAD: "IPO season just changed" — too vague, no company.]
HOOK: [2-5 words. The bottom closer — the twist or "so what" that creates the curiosity gap and makes them tap to read. This goes at the very bottom above the footer. No asterisks. GOOD: "No ticker. Yet." / "Stock went up 4%." / "Your job is next." / "Rate cuts are dead." / "Read before markets open." BAD: "This is very interesting" — no tension.]
LINES: [Exactly 3 short lines of supporting context — each line max 8 words, white text, fills the card. These sit between the headline and the hook. Give the key facts that make the headline make sense. Format: one line per row, separated by | character. Example: "Anthropic valuing at $60B | OpenAI already at $25B revenue | Both heading to public markets"]
KEYWORD: [2-3 word Unsplash search term — concrete visual, not abstract. Examples: wall street, office technology, trading floor, data center, bank building]"""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 800,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        print(f"Claude status: {r.status_code}")
        if r.status_code != 200:
            print(f"Claude error: {r.text[:200]}")
            return None

        text = r.json()["content"][0]["text"].strip()
        print(f"Claude response:\n{text[:400]}")

        if text.strip().upper() == "SKIP":
            print("Claude says SKIP — not relevant")
            return "SKIP"

        result = {}
        # Parse multi-line fields (LINKEDIN spans multiple lines)
        current_key = None
        current_val = []

        for line in text.split("\n"):
            if line.startswith("TWEET:"):
                if current_key:
                    result[current_key] = "\n".join(current_val).strip()
                current_key = "tweet"
                current_val = [line.replace("TWEET:", "").strip()]
            elif line.startswith("LINKEDIN:"):
                if current_key:
                    result[current_key] = "\n".join(current_val).strip()
                current_key = "linkedin"
                current_val = [line.replace("LINKEDIN:", "").strip()]
            elif line.startswith("H1:"):
                if current_key:
                    result[current_key] = "\n".join(current_val).strip()
                current_key = "h1"
                current_val = [line.replace("H1:", "").strip()]
            elif line.startswith("H2:"):
                if current_key:
                    result[current_key] = "\n".join(current_val).strip()
                current_key = "h2"
                current_val = [line.replace("H2:", "").strip()]
            elif line.startswith("LINES:"):
                if current_key:
                    result[current_key] = "\n".join(current_val).strip()
                current_key = "lines"
                current_val = [line.replace("LINES:", "").strip()]
            elif line.startswith("HOOK:"):
                if current_key:
                    result[current_key] = "\n".join(current_val).strip()
                current_key = "hook"
                current_val = [line.replace("HOOK:", "").strip()]
            elif line.startswith("KEYWORD:"):
                if current_key:
                    result[current_key] = "\n".join(current_val).strip()
                current_key = "keyword"
                current_val = [line.replace("KEYWORD:", "").strip()]
            elif current_key:
                current_val.append(line)

        if current_key:
            result[current_key] = "\n".join(current_val).strip()

        # Validate tweet character count
        tweet = result.get("tweet", title)
        count = x_char_count(tweet)
        if count > 280:
            print(f"WARNING: Tweet is {count} chars — trimming")
            # Trim from the end, keeping hashtags
            parts = tweet.rsplit("#", 1)
            base = parts[0].strip()
            tags = "#" + parts[1] if len(parts) > 1 else ""
            while x_char_count(f"{base}... {tags}") > 278 and len(base) > 20:
                base = base[:base.rfind(" ")]
            tweet = f"{base}... {tags}".strip()
            result["tweet"] = tweet
            print(f"Trimmed tweet: {tweet}")

        # Defaults
        result.setdefault("tweet", title)
        result.setdefault("linkedin", title)
        result.setdefault("h1", "Breaking Now")
        result.setdefault("h2", "Read Full Story")
        result.setdefault("lines", "")
        result.setdefault("hook", "")
        result.setdefault("keyword", "finance technology")

        # Strip asterisks from headlines
        result["h1"] = result["h1"].replace("**", "").replace("*", "").strip()
        result["h2"] = result["h2"].replace("**", "").replace("*", "").strip()

        print(f"Tweet ({x_char_count(result['tweet'])} chars): {result['tweet'][:80]}...")
        print(f"H1: {result['h1']}")
        print(f"H2: {result['h2']}")
        print(f"LinkedIn preview: {result['linkedin'][:100]}...")

        return result

    except Exception as e:
        print(f"Claude exception: {e}")
        return None


# ── UNSPLASH ──────────────────────────────────────────────────────
# Reliable fallback keywords — concrete, specific, tested on Unsplash
UNSPLASH_FALLBACKS = [
    "stock market screen",
    "trading screens",
    "skyscraper glass",
    "corporate office interior",
    "server data center",
    "city skyline night",
    "bank vault",
    "financial chart",
]

def fetch_unsplash(keyword):
    """Try a single keyword — return photo or None."""
    try:
        r = requests.get(
            "https://api.unsplash.com/photos/random",
            params={"query": keyword, "orientation": "squarish"},
            headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
            timeout=15
        )
        print(f"Unsplash [{keyword}]: {r.status_code}")
        if r.status_code != 200:
            return None
        data = r.json()
        img_url  = data["urls"]["regular"]
        img_data = requests.get(img_url, timeout=15).content
        from PIL import ImageEnhance
        photo = Image.open(BytesIO(img_data)).convert("RGB")
        pw, ph = photo.size
        scale  = max(W / pw, H / ph)
        nw, nh = int(pw * scale), int(ph * scale)
        photo  = photo.resize((nw, nh), Image.LANCZOS)
        left   = (nw - W) // 2
        top    = (nh - H) // 2
        photo  = photo.crop((left, top, left + W, top + H))
        photo  = ImageEnhance.Color(photo).enhance(0.78)
        photo  = ImageEnhance.Brightness(photo).enhance(0.65)
        return photo
    except Exception as e:
        print(f"Unsplash exception [{keyword}]: {e}")
        return None

def get_unsplash_photo(keyword):
    """Try Claude keyword first, then fallbacks until one works."""
    if not UNSPLASH_KEY:
        return None
    for kw in [keyword] + UNSPLASH_FALLBACKS:
        photo = fetch_unsplash(kw)
        if photo:
            print(f"Unsplash success with keyword: {kw}")
            return photo
    print("All Unsplash keywords failed — using navy fallback")
    return None


def apply_gradient(img, start=0.30):
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(int(H * start), H):
        t = float(y - H * start) / float(H * (1 - start))
        t = max(0.0, min(1.0, t))
        a = int(255 * t ** 0.78)
        gd.line([(0, y), (W, y)], fill=(10, 22, 40, a))
    for y in range(0, 88):
        t = 1 - (y / 88)
        a = int(55 * t ** 0.55)
        gd.line([(0, y), (W, y)], fill=(10, 22, 40, a))
    return Image.alpha_composite(img.convert("RGBA"), grad).convert("RGB")


# ── CARD GENERATOR ─────────────────────────────────────────────────
def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        w = draw.textbbox((0, 0), test, font=font)[2]
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_footer(draw):
    """Gold footer bar — same on both card types."""
    PAD   = 56
    draw.rectangle([(0, H - 72), (W, H)], fill=GOLD)
    url_f   = ImageFont.truetype(FONT_BOLD, 19)
    tags_f  = ImageFont.truetype(FONT_REG, 19)
    brand_t = "THE LEDGER WIRE"
    url_t   = "theledgerwire.com"
    btb     = draw.textbbox((0, 0), brand_t, font=url_f)
    utb     = draw.textbbox((0, 0), url_t, font=tags_f)
    uw      = utb[2] - utb[0]
    foot_y  = H - 72 + (72 - btb[3]) // 2
    draw.text((PAD, foot_y), brand_t, font=url_f, fill=NAVY)
    draw.text((W - PAD - uw, foot_y), url_t, font=tags_f, fill=NAVY)


def card_with_photo(img, headline1, headline2, hook=""):
    """DESIGN MODE 1 — Full bleed photo.
    Layout bottom-up:
      source line (grey, tiny)
      HOOK (white bold — biggest closer)
      H2 (gold, medium — company/context)
      H1 (white, large — stat/number)
      gold rule
    """
    draw       = ImageDraw.Draw(img)
    PAD        = 56
    MAX_TEXT_W = W - PAD - 40

    # Left gold bar
    draw.rectangle([(0, 0), (6, H - 72)], fill=GOLD)

    # Logo top left
    logo_f = ImageFont.truetype(FONT_BOLD, 20)
    logo_t = "THE LEDGER WIRE"
    lb     = draw.textbbox((0, 0), logo_t, font=logo_f)
    lw     = lb[2] - lb[0]
    draw.text((PAD, 36), logo_t, font=logo_f, fill=WHITE)
    draw.rectangle([(PAD, 60), (PAD + lw, 63)], fill=GOLD)

    # Font hierarchy — H1 big, H2 medium, HOOK bold closer
    h1_f   = ImageFont.truetype(FONT_BOLD, 90)   # stat — biggest
    h2_f   = ImageFont.truetype(FONT_BOLD, 46)   # context — medium
    hook_f = ImageFont.truetype(FONT_BOLD, 46)   # closer — same as H2
    src_f  = ImageFont.truetype(FONT_REG,  20)   # source — tiny

    h1_lines   = wrap_text(draw, headline1, h1_f, MAX_TEXT_W)
    h2_lines   = wrap_text(draw, headline2, h2_f, MAX_TEXT_W)
    hook_lines = wrap_text(draw, hook, hook_f, MAX_TEXT_W) if hook else []

    h1_lh   = draw.textbbox((0, 0), "Ag", font=h1_f)[3]
    h2_lh   = draw.textbbox((0, 0), "Ag", font=h2_f)[3]
    hook_lh = draw.textbbox((0, 0), "Ag", font=hook_f)[3]
    src_h   = draw.textbbox((0, 0), "theledgerwire.com", font=src_f)[3]

    total_h1   = h1_lh   * len(h1_lines)   + 4 * max(0, len(h1_lines)   - 1)
    total_h2   = h2_lh   * len(h2_lines)   + 4 * max(0, len(h2_lines)   - 1)
    total_hook = hook_lh * len(hook_lines) + 4 * max(0, len(hook_lines) - 1)

    # Build layout bottom-up
    SAFE_BOT = H - 72 - 24
    src_y    = SAFE_BOT - src_h
    hook_y   = src_y - 14 - total_hook if hook else src_y
    h2_y     = hook_y - 14 - total_h2
    h1_y     = h2_y  - 10 - total_h1
    rule_y   = h1_y  - 20

    # Gold accent rule
    draw.rectangle([(PAD, rule_y), (PAD + 52, rule_y + 4)], fill=GOLD)

    # H1 — white, large stat
    y = h1_y
    for line in h1_lines:
        draw.text((PAD, y), line, font=h1_f, fill=WHITE)
        y += h1_lh + 4

    # H2 — gold, company/context
    y = h2_y
    for line in h2_lines:
        draw.text((PAD, y), line, font=h2_f, fill=GOLD)
        y += h2_lh + 4

    # HOOK — white bold closer
    if hook_lines:
        y = hook_y
        for line in hook_lines:
            draw.text((PAD, y), line, font=hook_f, fill=WHITE)
            y += hook_lh + 4

    # Source
    draw.text((PAD, src_y), "theledgerwire.com", font=src_f, fill=DGREY)
    draw_footer(draw)
    img.save("card.png", "PNG")
    print("Card saved (photo mode)")


def card_no_photo(headline1, headline2, support_lines=None, hook=""):
    """DESIGN MODE 2 — Navy grid fallback. Like starcloud."""
    img  = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(img)

    # Navy gradient
    for y_px in range(0, H):
        t = y_px / H
        draw.line(
            [(0, y_px), (W, y_px)],
            fill=(int(10 + 15*t), int(22 + 18*t), int(40 + 28*t))
        )

    # Grid overlay
    grid_img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grid_draw = ImageDraw.Draw(grid_img)
    for x in range(0, W, 54):
        grid_draw.line([(x, 0), (x, H - 72)], fill=(255, 255, 255, 10))
    for y_px in range(0, H - 72, 54):
        grid_draw.line([(0, y_px), (W, y_px)], fill=(255, 255, 255, 10))
    img  = Image.alpha_composite(img.convert("RGBA"), grid_img).convert("RGB")
    draw = ImageDraw.Draw(img)

    PAD        = 86
    MAX_TEXT_W = W - PAD - 40

    # Left gold bar
    draw.rectangle([(0, 0), (6, H - 72)], fill=GOLD)

    # Logo
    logo_f = ImageFont.truetype(FONT_BOLD, 18)
    logo_t = "THE LEDGER WIRE"
    lb     = draw.textbbox((0, 0), logo_t, font=logo_f)
    lw     = lb[2] - lb[0]
    draw.text((PAD, 52), logo_t, font=logo_f, fill=WHITE)
    draw.rectangle([(PAD, 74), (PAD + lw, 77)], fill=GOLD)

    # Dominant H1 — large gold at top
    h1_f     = ImageFont.truetype(FONT_BOLD, 120)
    h1_lines = wrap_text(draw, headline1, h1_f, MAX_TEXT_W)
    h1_lh    = draw.textbbox((0, 0), "Ag", font=h1_f)[3]

    y = 110
    for line in h1_lines:
        draw.text((PAD, y), line, font=h1_f, fill=GOLD)
        y += h1_lh + 4

    # H2 — white subtitle
    h2_f     = ImageFont.truetype(FONT_BOLD, 52)
    h2_lines = wrap_text(draw, headline2, h2_f, MAX_TEXT_W)
    h2_lh    = draw.textbbox((0, 0), "Ag", font=h2_f)[3]

    y += 16
    for line in h2_lines:
        draw.text((PAD, y), line, font=h2_f, fill=WHITE)
        y += h2_lh + 4

    # Gold divider
    y += 20
    draw.rectangle([(PAD, y), (PAD + 200, y + 5)], fill=GOLD)
    y += 32

    # Supporting bullet lines
    if support_lines:
        line_f  = ImageFont.truetype(FONT_REG, 28)
        line_lh = draw.textbbox((0, 0), "Ag", font=line_f)[3]
        for line_text in support_lines:
            if y + line_lh > H - 72 - 80:
                break
            # Gold left bar per line
            draw.rectangle([(PAD, y + 4), (PAD + 4, y + line_lh - 4)], fill=GOLD)
            draw.text((PAD + 18, y), line_text.strip(), font=line_f, fill=WHITE)
            y += line_lh + 16

    # Hook line at bottom (white + gold)
    hook_y = H - 72 - 110
    if hook:
        hook_parts = hook.split(".")
        hook_f  = ImageFont.truetype(FONT_BOLD, 48)
        hook_lh = draw.textbbox((0, 0), "Ag", font=hook_f)[3]
        hk_y = hook_y
        for part in hook_parts:
            part = part.strip()
            if not part:
                continue
            col = GOLD if hook_parts.index(part) % 2 == 1 else WHITE
            draw.text((PAD, hk_y), part + ("." if not part.endswith(".") else ""), font=hook_f, fill=col)
            hk_y += hook_lh + 4

    # Source
    src_f = ImageFont.truetype(FONT_REG, 22)
    draw.text((PAD, H - 72 - 36), "theledgerwire.com", font=src_f, fill=DGREY)

    draw_footer(draw)
    img.save("card.png", "PNG")
    print("Card saved (fallback mode)")


def generate_card(headline1, headline2, keyword, support_lines=None, hook=""):
    photo = get_unsplash_photo(keyword)
    if photo:
        img = apply_gradient(photo)
        print("Photo found → photo card design")
        card_with_photo(img, headline1, headline2, hook)
    else:
        print("No photo → navy stat card design")
        card_no_photo(headline1, headline2, support_lines, hook)
    return "card.png"



# ── GITHUB ────────────────────────────────────────────────────────
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


# ── BUFFER ────────────────────────────────────────────────────────
def post_to_buffer(post_text, image_url, channel_id, api_key, platform="", retries=2):
    print(f"Posting to Buffer {platform}...")
    time.sleep(3)

    # Escape for GraphQL string
    safe_text = post_text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

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

    for attempt in range(retries + 1):
        try:
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
            print(f"Buffer {platform} response: {r.text[:300]}")

            response_data = r.json()
            if "errors" in response_data:
                print(f"Buffer GraphQL errors: {response_data['errors']}")
                if attempt < retries:
                    print(f"Retrying in 5s... (attempt {attempt + 1}/{retries})")
                    time.sleep(5)
                    continue
                return False

            post_data = response_data.get("data", {}).get("createPost", {})
            if "message" in post_data and "post" not in post_data:
                print(f"Buffer error message: {post_data['message']}")
                if attempt < retries:
                    time.sleep(5)
                    continue
                return False

            return r.status_code == 200

        except Exception as e:
            print(f"Buffer {platform} exception: {e}")
            if attempt < retries:
                time.sleep(5)
            continue

    return False


# ── MAIN ──────────────────────────────────────────────────────────
if not STORY_TITLE:
    print("No story title provided — exiting")
    exit(0)

claude_result = call_claude(STORY_TITLE, STORY_SUMMARY)

if claude_result == "SKIP" or claude_result is None:
    print("Story skipped or Claude failed — exiting")
    exit(0)

tweet_text    = claude_result.get("tweet", STORY_TITLE)
linkedin_text = claude_result.get("linkedin", STORY_TITLE)
headline1     = claude_result.get("h1", "Breaking Now")
headline2     = claude_result.get("h2", "Read Full Story")
img_keyword   = claude_result.get("keyword", IMAGE_KEYWORD)
lines_raw     = claude_result.get("lines", "")
support_lines = [l.strip() for l in lines_raw.split("|") if l.strip()][:3]
hook_text     = claude_result.get("hook", "").replace("**","").replace("*","").strip()

# Final tweet char count check
final_count = x_char_count(tweet_text)
print(f"Final tweet: {final_count} chars")
if final_count > 280:
    print(f"ERROR: Tweet still over 280 chars ({final_count}) — exiting to avoid bad post")
    exit(1)

generate_card(headline1, headline2, img_keyword, support_lines, hook_text)

if BUFFER_API_KEY and GITHUB_TOKEN:
    pushed = push_to_github("card.png", GITHUB_TOKEN, REPO, IMAGE_PATH)
    if pushed:
        time.sleep(5)  # Let GitHub CDN propagate

        if BUFFER_PROFILE_X:
            success_x = post_to_buffer(tweet_text, RAW_URL, BUFFER_PROFILE_X, BUFFER_API_KEY, "X")
            print("X: SUCCESS" if success_x else "X: FAILED")

        if BUFFER_PROFILE_LI:
            time.sleep(3)
            # LinkedIn gets full long-form text — link goes in first comment via Buffer
            li_post = f"{linkedin_text}\n\n(Full story: theledgerwire.com)"
            success_li = post_to_buffer(li_post, RAW_URL, BUFFER_PROFILE_LI, BUFFER_API_KEY, "LinkedIn")
            print("LinkedIn: SUCCESS" if success_li else "LinkedIn: FAILED")
    else:
        print("FAILED: GitHub push failed")
else:
    missing = [k for k, v in {
        "BUFFER_API_KEY": BUFFER_API_KEY,
        "GITHUB_TOKEN": GITHUB_TOKEN
    }.items() if not v]
    print(f"Missing credentials: {', '.join(missing)}")
