# TLW v15
# - Base64 decode for story title/summary (fixes Make.com JSON errors)
# - LinkedIn URL stripped from body (algorithm fix)
# - Photo dedup — tracks used URLs in GitHub, falls back to navy if repeat
# - Pexels primary, Unsplash secondary, navy fallback
# - Country/company keyword detection
# - Weekly tweet screenshot cards (Tuesday/Friday)
import os, re, time, random, requests, base64, json
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from datetime import datetime

# ── CREDENTIALS ───────────────────────────────────────────────────
BUFFER_API_KEY    = os.environ.get("BUFFER_API_KEY", "")
BUFFER_PROFILE_X  = os.environ.get("BUFFER_PROFILE_X", "")
BUFFER_PROFILE_LI = os.environ.get("BUFFER_PROFILE_LI", "")
GITHUB_TOKEN      = os.environ.get("GITHUB_TOKEN", "")
ANTHROPIC_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
UNSPLASH_KEY      = os.environ.get("UNSPLASH_KEY", "")
PEXELS_KEY        = os.environ.get("PEXELS_KEY", "")
FAL_KEY           = os.environ.get("FAL_KEY", "")
CARD_TYPE         = os.environ.get("CARD_TYPE", "news")
WEEKLY_HEADLINES  = os.environ.get("WEEKLY_HEADLINES", "")
IMAGE_KEYWORD     = os.environ.get("IMAGE_KEYWORD", "finance technology")

# ── BASE64 DECODE inputs from Make.com ────────────────────────────
def _decode(val):
    """Decode base64 if encoded, otherwise return raw."""
    try:
        decoded = base64.b64decode(val).decode('utf-8')
        # Sanity check — decoded should be readable text
        if decoded.isprintable() or '\n' in decoded:
            return decoded.strip()
    except Exception:
        pass
    return val.strip()

STORY_TITLE   = _decode(os.environ.get("STORY_TITLE",   ""))
STORY_SUMMARY = _decode(os.environ.get("STORY_SUMMARY", ""))

# Also strip any remaining control characters
STORY_TITLE   = re.sub(r'[\x00-\x1f\x7f]', ' ', STORY_TITLE).strip()
STORY_SUMMARY = re.sub(r'[\x00-\x1f\x7f]', ' ', STORY_SUMMARY).strip()

REPO       = "theledgerwire/tlw-content-engine"
IMAGE_PATH = f"cards/card_{int(time.time())}.png"
RAW_URL    = f"https://raw.githubusercontent.com/{REPO}/main/{IMAGE_PATH}"

# ── DESIGN ────────────────────────────────────────────────────────
W, H      = 1080, 1080
GOLD      = (245, 197, 24)
WHITE     = (255, 255, 255)
NAVY      = (10, 22, 40)
DGREY     = (100, 115, 148)
BLACK     = (20, 20, 20)
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

# ── PHOTO SOURCES ─────────────────────────────────────────────────
PHOTO_FALLBACKS = [
    "stock market trading",
    "wall street new york",
    "trading floor brokers",
    "corporate skyscraper",
    "technology server room",
    "cryptocurrency bitcoin",
    "federal reserve building",
    "bank building finance",
]

COUNTRY_KEYWORDS = {
    "korea":     ["south korea seoul skyline", "korean flag city"],
    "korean":    ["south korea seoul skyline", "korean flag city"],
    "china":     ["shanghai skyline night", "china flag beijing"],
    "chinese":   ["shanghai skyline night", "china flag beijing"],
    "alibaba":   ["shanghai skyline night", "china tech office"],
    "tencent":   ["hong kong skyline", "china tech shenzhen"],
    "baidu":     ["beijing china skyline", "china tech office"],
    "deepseek":  ["china tech office", "server room blue"],
    "japan":     ["tokyo skyline night", "japan flag mount fuji"],
    "japanese":  ["tokyo skyline night", "japan flag mount fuji"],
    "india":     ["mumbai skyline night", "india flag"],
    "sec":       ["courthouse steps washington", "federal building columns"],
    "lawsuit":   ["legal gavel courtroom", "courthouse steps"],
    "trial":     ["legal gavel courtroom", "justice scales"],
    "fed":       ["federal reserve building washington", "us dollar bills"],
    "federal reserve": ["federal reserve building washington", "us dollar bills"],
    "bitcoin":   ["bitcoin gold coin", "cryptocurrency digital"],
    "crypto":    ["cryptocurrency bitcoin coin", "blockchain digital"],
    "ethereum":  ["ethereum cryptocurrency", "crypto digital coins"],
    "hack":      ["computer hacker dark screen", "keyboard code programming"],
    "leak":      ["computer code screen dark", "keyboard programming"],
    "cyber":     ["cybersecurity lock digital", "computer hacker"],
    "oil":       ["oil pipeline sunset", "oil refinery night"],
    "energy":    ["oil refinery night", "solar panels field"],
    "space":     ["rocket launch nasa", "astronaut space earth"],
    "nasa":      ["rocket launch nasa", "astronaut space earth"],
    "rocket":    ["rocket launch fire", "spacex rocket"],
    "amazon":    ["amazon warehouse interior", "amazon delivery boxes"],
    "google":    ["google headquarters building", "tech campus"],
    "microsoft": ["microsoft headquarters", "windows logo tech"],
    "apple":     ["apple store glass", "apple headquarters campus"],
    "tesla":     ["tesla electric car", "electric vehicle charging"],
    "openai":    ["artificial intelligence neural", "chatgpt computer screen"],
    "anthropic": ["artificial intelligence claude", "ai computer code"],
    "nvidia":    ["gpu graphics card", "nvidia chip semiconductor"],
}

# ── USED IMAGES TRACKING ──────────────────────────────────────────
USED_IMAGES_PATH = "data/used_images.json"
USED_IMAGES_URL  = f"https://raw.githubusercontent.com/{REPO}/main/{USED_IMAGES_PATH}?t={int(time.time())}"
IMAGE_EXPIRY_SEC = 7 * 86400  # 7 days

def load_used_images():
    try:
        r = requests.get(USED_IMAGES_URL, timeout=10)
        if r.status_code == 200:
            data   = r.json()
            cutoff = time.time() - IMAGE_EXPIRY_SEC
            fresh  = {url: ts for url, ts in data.items() if ts > cutoff}
            print(f"Loaded {len(fresh)} used images")
            return fresh
    except Exception as e:
        print(f"Could not load used images: {e}")
    return {}

def save_used_image(img_url, used_images):
    try:
        used_images[img_url] = time.time()
        cutoff   = time.time() - IMAGE_EXPIRY_SEC
        fresh    = {u: t for u, t in used_images.items() if t > cutoff}
        encoded  = base64.b64encode(json.dumps(fresh, indent=2).encode()).decode()
        headers  = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        get_r    = requests.get(f"https://api.github.com/repos/{REPO}/contents/{USED_IMAGES_PATH}", headers=headers, timeout=10)
        sha      = get_r.json().get("sha") if get_r.status_code == 200 else None
        payload  = {"message": "Update used images", "content": encoded, "branch": "main"}
        if sha:
            payload["sha"] = sha
        put_r = requests.put(f"https://api.github.com/repos/{REPO}/contents/{USED_IMAGES_PATH}", headers=headers, json=payload, timeout=15)
        print(f"Saved used image: {put_r.status_code}")
    except Exception as e:
        print(f"Could not save used image: {e}")

print(f"=== TLW v15 === CARD_TYPE: {CARD_TYPE}")
print(f"Title: {STORY_TITLE[:60]}...")

# ── TWEET CHAR COUNT ──────────────────────────────────────────────
def x_char_count(text):
    t = re.sub(r'https?://\S+|[\w]+\.com\S*', 'X'*23, text)
    return len(t)

# ── STRIP URLS FROM TEXT ──────────────────────────────────────────
def strip_urls(text):
    """Remove all URLs and domain references from text."""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\S+\.com\S*', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# ── CLAUDE: NEWS ──────────────────────────────────────────────────
def call_claude_news(title, summary):
    if not ANTHROPIC_KEY:
        return None
    prompt = f"""You are a content writer for The Ledger Wire — an AI and Finance newsletter for North American professionals.

Story title: {title}
Story summary: {summary}

TIER 1 — PREFERRED: AI/finance/tech/crypto/Fed/bank earnings/trade tariffs/Chinese AI companies
TIER 2 — FALLBACK: Major company earnings, M&A, layoffs, stock market moves, economic data, central banks, $50M+ funding

Reply SKIP only if: pure geopolitics/war with no market angle, sports, entertainment, food, lifestyle.

Reply in this EXACT format:

TIER: [1 or 2]
TWEET: [Morning Brew style, STRICTLY under 220 chars, curiosity gap, never explain full story, end with -> theledgerwire.com #AI #Finance]
LINKEDIN: [Morning Brew style, ONE punchy opener, 2-3 short paragraphs, end with question. ABSOLUTELY NO URLs, NO website links, NO theledgerwire.com anywhere in the text. The algorithm penalises posts with links. Write like a smart colleague over coffee.]
H1: [1-3 words MAX, shocking stat or number, abbreviations only. GOOD: $60B. / 30,000 jobs. BAD: $60 Billion]
H2: [2-4 words, company + what happened. GOOD: Anthropic. Going public. / Oracle. 6am email.]
HOOK: [2-5 words, bottom closer, curiosity gap. GOOD: No ticker. Yet. / Stock went up 4%.]
LINES: [3 short facts max 8 words each separated by | character]
KEYWORD: [3-5 word SPECIFIC photo search. Match visually:
- Code/hack/leak → "computer hacker dark screen"
- SEC/legal/trial → "courthouse steps washington"
- Fed/rates → "federal reserve building washington"
- Korea story → "south korea seoul skyline"
- China story → "shanghai skyline night"
- Crypto → "bitcoin gold coin"
- Oil/energy → "oil pipeline sunset"
- Space/NASA → "rocket launch nasa"
- AI company → "artificial intelligence neural network"
NEVER use: "finance technology" / "business" / "woman laptop"]"""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 900, "messages": [{"role": "user", "content": prompt}]},
            timeout=30
        )
        print(f"Claude: {r.status_code}")
        if r.status_code != 200:
            return None
        text = r.json()["content"][0]["text"].strip()
        print(f"Claude response:\n{text[:500]}")
        if text.strip().upper() == "SKIP":
            return "SKIP"

        result = {}
        current_key = None
        current_val = []
        for line in text.split("\n"):
            matched = False
            for key in ["TIER","TWEET","LINKEDIN","H1","H2","HOOK","LINES","KEYWORD"]:
                if line.startswith(f"{key}:"):
                    if current_key:
                        result[current_key] = "\n".join(current_val).strip()
                    current_key = key.lower()
                    current_val = [line.replace(f"{key}:","").strip()]
                    matched = True
                    break
            if not matched and current_key:
                current_val.append(line)
        if current_key:
            result[current_key] = "\n".join(current_val).strip()

        # Trim tweet if over 280
        tweet = result.get("tweet", title)
        if x_char_count(tweet) > 280:
            parts = tweet.rsplit("#", 1)
            base  = parts[0].strip()
            tags  = "#" + parts[1] if len(parts) > 1 else ""
            while x_char_count(f"{base}... {tags}") > 278 and len(base) > 20:
                base = base[:base.rfind(" ")]
            result["tweet"] = f"{base}... {tags}".strip()

        # Hard guard
        if result.get("h1") in ["Breaking Now", "", None]:
            print("H1 default — SKIP")
            return "SKIP"

        # Strip asterisks
        for key in ["h1","h2","hook"]:
            if key in result:
                result[key] = result[key].replace("**","").replace("*","").strip()

        # HARD strip any URLs from LinkedIn text
        if "linkedin" in result:
            result["linkedin"] = strip_urls(result["linkedin"])

        result.setdefault("tweet",   title)
        result.setdefault("linkedin", title)
        result.setdefault("h1",      "Breaking Now")
        result.setdefault("h2",      "Read Full Story")
        result.setdefault("hook",    "")
        result.setdefault("lines",   "")
        result.setdefault("tier",    "1")
        result.setdefault("keyword", "stock market trading")

        print(f"Tier:{result['tier']} H1:{result['h1']} H2:{result['h2']}")
        print(f"Keyword: {result['keyword']}")
        return result
    except Exception as e:
        print(f"Claude exception: {e}")
        return None

# ── CLAUDE: WEEKLY ────────────────────────────────────────────────
def call_claude_weekly(headlines, card_type):
    if not ANTHROPIC_KEY:
        return None
    if card_type == "weekly_tuesday":
        instruction = """Write a Tuesday market recap for The Ledger Wire.
Pick the 3-4 most market-moving stories from Monday's headlines.
Format as witty tweet screenshot:
"Finance pros this Monday:
[Story 1 with dry emoji]
[Story 2 with dry emoji]
[Story 3 with dry emoji]
[Ironic closer about the week ahead]"
Under 260 chars. Maximum wit."""
    else:
        instruction = """Write a Friday week-in-review for The Ledger Wire.
Pick the most ironic or chaotic moments from this week's headlines.
Format as witty tweet screenshot:
"Finance pros this week:
Monday: [what happened] [emoji]
Wednesday: [twist] [emoji]
Thursday: [market reaction] [emoji]
Friday: [ironic closer] [emoji]"
Under 260 chars. Maximum dry humour."""

    prompt = f"""{instruction}

Headlines:
{headlines}

Reply in this EXACT format:

TWEET_SCREENSHOT: [witty recap for inside the tweet card]
X_POST: [short teaser under 180 chars ending with -> theledgerwire.com #AI #Finance]
LINKEDIN: [professional witty version, ends with engagement question, NO URLs anywhere]"""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 600, "messages": [{"role": "user", "content": prompt}]},
            timeout=30
        )
        if r.status_code != 200:
            return None
        text = r.json()["content"][0]["text"].strip()
        result = {}
        current_key = None
        current_val = []
        for line in text.split("\n"):
            matched = False
            for key in ["TWEET_SCREENSHOT","X_POST","LINKEDIN"]:
                if line.startswith(f"{key}:"):
                    if current_key:
                        result[current_key] = "\n".join(current_val).strip()
                    current_key = key.lower()
                    current_val = [line.replace(f"{key}:","").strip()]
                    matched = True
                    break
            if not matched and current_key:
                current_val.append(line)
        if current_key:
            result[current_key] = "\n".join(current_val).strip()
        if "linkedin" in result:
            result["linkedin"] = strip_urls(result["linkedin"])
        return result
    except Exception as e:
        print(f"Claude weekly exception: {e}")
        return None

# ── PHOTO PROCESSING ──────────────────────────────────────────────
def process_photo(img_data):
    from PIL import ImageEnhance
    photo  = Image.open(BytesIO(img_data)).convert("RGB")
    pw, ph = photo.size
    scale  = max(W/pw, H/ph)
    nw, nh = int(pw*scale), int(ph*scale)
    photo  = photo.resize((nw, nh), Image.LANCZOS)
    left   = (nw-W)//2
    top    = (nh-H)//2
    photo  = photo.crop((left, top, left+W, top+H))
    photo  = ImageEnhance.Color(photo).enhance(0.85)
    photo  = ImageEnhance.Brightness(photo).enhance(0.62)
    return photo

def fetch_pexels(keyword, used_images):
    if not PEXELS_KEY:
        return None, None
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": keyword, "per_page": 15, "orientation": "square"},
            headers={"Authorization": PEXELS_KEY},
            timeout=15
        )
        print(f"Pexels [{keyword}]: {r.status_code}")
        if r.status_code != 200:
            return None, None
        photos = r.json().get("photos", [])
        if not photos:
            return None, None
        # Shuffle and skip used images
        random.shuffle(photos)
        for p in photos:
            img_url = p["src"]["large"]
            if img_url in used_images:
                print(f"Skipping used image: {img_url[:50]}...")
                continue
            img_data = requests.get(img_url, timeout=15).content
            print(f"Pexels photo: {img_url[:60]}...")
            return process_photo(img_data), img_url
        print(f"All Pexels results for [{keyword}] already used")
        return None, None
    except Exception as e:
        print(f"Pexels exception [{keyword}]: {e}")
        return None, None

def fetch_unsplash(keyword, used_images):
    if not UNSPLASH_KEY:
        return None, None
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": keyword, "per_page": 15, "orientation": "squarish", "order_by": "relevant"},
            headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
            timeout=15
        )
        print(f"Unsplash [{keyword}]: {r.status_code}")
        if r.status_code != 200:
            return None, None
        results = r.json().get("results", [])
        if not results:
            return None, None
        random.shuffle(results)
        for p in results:
            img_url = p["urls"]["regular"]
            if img_url in used_images:
                print(f"Skipping used image: {img_url[:50]}...")
                continue
            img_data = requests.get(img_url, timeout=15).content
            print(f"Unsplash photo: {img_url[:60]}...")
            return process_photo(img_data), img_url
        print(f"All Unsplash results for [{keyword}] already used")
        return None, None
    except Exception as e:
        print(f"Unsplash exception [{keyword}]: {e}")
        return None, None

def get_country_keywords(keyword, story_context=""):
    combined = f"{keyword} {story_context}".lower()
    for trigger, replacements in COUNTRY_KEYWORDS.items():
        if trigger in combined:
            print(f"Country/company match: [{trigger}] → {replacements[0]}")
            return replacements
    return []

# ── FLUX.1 AI IMAGE GENERATION ────────────────────────────────────
def generate_flux_prompt(title, summary):
    """Claude writes a story-specific Flux.1 image prompt."""
    if not ANTHROPIC_KEY:
        return None
    try:
        prompt = f"""You are an AI image director for The Ledger Wire, a finance and AI newsletter.

Story: {title}
Summary: {summary}

Write a Flux.1 image generation prompt. Rules:
1. Be LITERAL and SPECIFIC to the story — describe exactly what object/place/thing represents it
2. Always photorealistic news photography style — NOT artistic, NOT painterly, NOT fantasy
3. Dark background, dramatic studio lighting, navy blue and gold color tones
4. No text, no logos, no faces, no people
5. Max 20 words

LITERAL examples — copy this style exactly:
- Battery/EV story: "Electric vehicle battery cells close up, blue glow, dark background, dramatic lighting, photorealistic"
- Bitcoin/Crypto: "Gold Bitcoin coin on dark surface, spotlight from above, bokeh background, photorealistic"
- China tech company: "Shanghai skyline at night through glass window, city lights, dark foreground, photorealistic"
- AI chips: "Nvidia GPU graphics card on dark surface, blue circuit glow, dramatic lighting, photorealistic"
- Bank/finance: "Federal Reserve building columns at night, gold light, dark sky, photorealistic"
- Layoffs/jobs: "Empty office chairs at night, blue computer screens, dark room, photorealistic"
- SoftBank/Japan: "Tokyo skyline at night through glass, neon reflections, dark foreground, photorealistic"
- TSMC/semiconductors: "Silicon wafer chip close up, blue light, dark background, dramatic, photorealistic"
- Battery/CATL: "Lithium battery pack glowing blue, dark industrial background, dramatic lighting, photorealistic"
- Energy/oil: "Oil pipeline at sunset, dramatic sky, cinematic, photorealistic"

NEVER use: horses, warriors, abstract art, mythology, fantasy elements, animals unrelated to story.
ALWAYS use: real objects, real places, real technology that directly relates to the story.

Reply with ONLY the prompt. No quotes, no explanation."""

        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 100,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=30
        )
        if r.status_code == 200:
            img_prompt = r.json()["content"][0]["text"].strip().strip('"')
            print(f"Flux prompt: {img_prompt}")
            return img_prompt
    except Exception as e:
        print(f"Flux prompt error: {e}")
    return None

def fetch_flux_image(img_prompt):
    """Generate image via Flux.1 Pro on fal.ai."""
    if not FAL_KEY or not img_prompt:
        return None, None
    try:
        full_prompt = img_prompt + ", photorealistic news photography, 8K, sharp focus, no text, no watermarks, no logos, professional studio lighting"
        r = requests.post(
            "https://fal.run/fal-ai/flux-pro/v1.1",
            headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
            json={
                "prompt": full_prompt,
                "image_size": "square_hd",
                "num_inference_steps": 28,
                "guidance_scale": 3.5,
                "num_images": 1,
                "safety_tolerance": "2"
            },
            timeout=60
        )
        print(f"Flux.1: {r.status_code}")
        if r.status_code == 200:
            img_url  = r.json()["images"][0]["url"]
            img_data = requests.get(img_url, timeout=30).content
            print(f"Flux image: {img_url[:60]}...")
            return process_photo(img_data), img_url
        else:
            print(f"Flux error: {r.text[:200]}")
    except Exception as e:
        print(f"Flux exception: {e}")
    return None, None

def get_photo(keyword, story_context="", used_images=None):
    if used_images is None:
        used_images = {}

    # Tier 1 — Flux.1 AI generated (story-specific, zero copyright)
    if FAL_KEY:
        print("--- Trying Flux.1 AI ---")
        flux_prompt = generate_flux_prompt(
            story_context.split(" ", 10)[0:10] and story_context or keyword,
            story_context
        )
        photo, img_url = fetch_flux_image(flux_prompt)
        if photo:
            print("Flux.1 success")
            return photo, img_url
        print("Flux.1 failed — trying Pexels")

    country_kws     = get_country_keywords(keyword, story_context)
    keywords_to_try = [keyword] + country_kws + PHOTO_FALLBACKS

    # Tier 2 — Pexels
    print("--- Trying Pexels ---")
    for kw in keywords_to_try:
        photo, img_url = fetch_pexels(kw, used_images)
        if photo:
            print(f"Pexels success: [{kw}]")
            return photo, img_url

    # Tier 3 — Unsplash
    print("--- Trying Unsplash ---")
    for kw in keywords_to_try:
        photo, img_url = fetch_unsplash(kw, used_images)
        if photo:
            print(f"Unsplash success: [{kw}]")
            return photo, img_url

    print("--- All photo sources failed — navy card ---")
    return None, None

# ── GRADIENT ──────────────────────────────────────────────────────
def apply_gradient(img, start=0.30):
    grad = Image.new("RGBA",(W,H),(0,0,0,0))
    gd   = ImageDraw.Draw(grad)
    for y in range(int(H*start),H):
        t = float(y-H*start)/float(H*(1-start))
        t = max(0.0,min(1.0,t))
        a = int(255*t**0.78)
        gd.line([(0,y),(W,y)],fill=(10,22,40,a))
    for y in range(0,88):
        t = 1-(y/88)
        a = int(55*t**0.55)
        gd.line([(0,y),(W,y)],fill=(10,22,40,a))
    return Image.alpha_composite(img.convert("RGBA"),grad).convert("RGB")

def wrap_text(draw,text,font,max_width):
    words=text.split()
    lines=[]
    current=""
    for word in words:
        test=f"{current} {word}".strip()
        if draw.textbbox((0,0),test,font=font)[2]<=max_width:
            current=test
        else:
            if current:
                lines.append(current)
            current=word
    if current:
        lines.append(current)
    return lines

def draw_footer(draw):
    PAD=56
    draw.rectangle([(0,H-72),(W,H)],fill=GOLD)
    url_f=ImageFont.truetype(FONT_BOLD,19)
    tag_f=ImageFont.truetype(FONT_REG,19)
    btb=draw.textbbox((0,0),"THE LEDGER WIRE",font=url_f)
    utb=draw.textbbox((0,0),"theledgerwire.com",font=tag_f)
    uw=utb[2]-utb[0]
    fy=H-72+(72-btb[3])//2
    draw.text((PAD,fy),"THE LEDGER WIRE",font=url_f,fill=NAVY)
    draw.text((W-PAD-uw,fy),"theledgerwire.com",font=tag_f,fill=NAVY)

# ── CARD: PHOTO ───────────────────────────────────────────────────
def card_with_photo(img,h1,h2,hook=""):
    draw=ImageDraw.Draw(img)
    PAD=56
    MTW=W-PAD-40
    draw.rectangle([(0,0),(6,H-72)],fill=GOLD)
    logo_f=ImageFont.truetype(FONT_BOLD,20)
    lb=draw.textbbox((0,0),"THE LEDGER WIRE",font=logo_f)
    draw.text((PAD,36),"THE LEDGER WIRE",font=logo_f,fill=WHITE)
    draw.rectangle([(PAD,60),(PAD+lb[2]-lb[0],63)],fill=GOLD)
    h1_f=ImageFont.truetype(FONT_BOLD,90)
    h2_f=ImageFont.truetype(FONT_BOLD,46)
    hook_f=ImageFont.truetype(FONT_BOLD,46)
    src_f=ImageFont.truetype(FONT_REG,20)
    h1_lines=wrap_text(draw,h1,h1_f,MTW)
    h2_lines=wrap_text(draw,h2,h2_f,MTW)
    hook_lines=wrap_text(draw,hook,hook_f,MTW) if hook else []
    h1_lh=draw.textbbox((0,0),"Ag",font=h1_f)[3]
    h2_lh=draw.textbbox((0,0),"Ag",font=h2_f)[3]
    hook_lh=draw.textbbox((0,0),"Ag",font=hook_f)[3]
    src_h=draw.textbbox((0,0),"theledgerwire.com",font=src_f)[3]
    th1=h1_lh*len(h1_lines)+4*max(0,len(h1_lines)-1)
    th2=h2_lh*len(h2_lines)+4*max(0,len(h2_lines)-1)
    thk=hook_lh*len(hook_lines)+4*max(0,len(hook_lines)-1)
    SAFE=H-72-24
    src_y=SAFE-src_h
    hook_y=src_y-14-thk if hook else src_y
    h2_y=hook_y-14-th2
    h1_y=h2_y-10-th1
    rule_y=h1_y-20
    draw.rectangle([(PAD,rule_y),(PAD+52,rule_y+4)],fill=GOLD)
    y=h1_y
    for line in h1_lines:
        draw.text((PAD,y),line,font=h1_f,fill=WHITE); y+=h1_lh+4
    y=h2_y
    for line in h2_lines:
        draw.text((PAD,y),line,font=h2_f,fill=GOLD); y+=h2_lh+4
    if hook_lines:
        y=hook_y
        for line in hook_lines:
            draw.text((PAD,y),line,font=hook_f,fill=WHITE); y+=hook_lh+4
    draw.text((PAD,src_y),"theledgerwire.com",font=src_f,fill=DGREY)
    draw_footer(draw)
    img.save("card.png","PNG")
    print("Card saved (photo mode)")

# ── CARD: NAVY ────────────────────────────────────────────────────
def card_no_photo(h1,h2,support_lines=None,hook=""):
    img=Image.new("RGB",(W,H),NAVY)
    draw=ImageDraw.Draw(img)
    for y_px in range(H):
        t=y_px/H
        draw.line([(0,y_px),(W,y_px)],fill=(int(10+15*t),int(22+18*t),int(40+28*t)))
    gi=Image.new("RGBA",(W,H),(0,0,0,0))
    gd=ImageDraw.Draw(gi)
    for x in range(0,W,54):
        gd.line([(x,0),(x,H-72)],fill=(255,255,255,10))
    for y_px in range(0,H-72,54):
        gd.line([(0,y_px),(W,y_px)],fill=(255,255,255,10))
    img=Image.alpha_composite(img.convert("RGBA"),gi).convert("RGB")
    draw=ImageDraw.Draw(img)
    PAD=86
    MTW=W-PAD-40
    draw.rectangle([(0,0),(6,H-72)],fill=GOLD)
    logo_f=ImageFont.truetype(FONT_BOLD,18)
    lb=draw.textbbox((0,0),"THE LEDGER WIRE",font=logo_f)
    draw.text((PAD,52),"THE LEDGER WIRE",font=logo_f,fill=WHITE)
    draw.rectangle([(PAD,74),(PAD+lb[2]-lb[0],77)],fill=GOLD)
    h1_f=ImageFont.truetype(FONT_BOLD,120)
    h1_lines=wrap_text(draw,h1,h1_f,MTW)
    h1_lh=draw.textbbox((0,0),"Ag",font=h1_f)[3]
    y=110
    for line in h1_lines:
        draw.text((PAD,y),line,font=h1_f,fill=GOLD); y+=h1_lh+4
    h2_f=ImageFont.truetype(FONT_BOLD,52)
    h2_lines=wrap_text(draw,h2,h2_f,MTW)
    h2_lh=draw.textbbox((0,0),"Ag",font=h2_f)[3]
    y+=16
    for line in h2_lines:
        draw.text((PAD,y),line,font=h2_f,fill=WHITE); y+=h2_lh+4
    y+=20
    draw.rectangle([(PAD,y),(PAD+200,y+5)],fill=GOLD)
    y+=32
    if support_lines:
        lf=ImageFont.truetype(FONT_REG,28)
        llh=draw.textbbox((0,0),"Ag",font=lf)[3]
        for lt in support_lines:
            if y+llh>H-72-160: break
            draw.rectangle([(PAD,y+6),(PAD+4,y+llh-6)],fill=GOLD)
            draw.text((PAD+18,y),lt.strip(),font=lf,fill=WHITE)
            y+=llh+16
    if hook:
        hf=ImageFont.truetype(FONT_BOLD,48)
        hlh=draw.textbbox((0,0),"Ag",font=hf)[3]
        parts=[p.strip() for p in hook.split(".") if p.strip()]
        hy=H-72-110
        for i,part in enumerate(parts):
            draw.text((PAD,hy),part+".",font=hf,fill=WHITE if i%2==0 else GOLD)
            hy+=hlh+4
    sf=ImageFont.truetype(FONT_REG,22)
    draw.text((PAD,H-72-36),"theledgerwire.com",font=sf,fill=DGREY)
    draw_footer(draw)
    img.save("card.png","PNG")
    print("Card saved (navy fallback)")

# ── CARD: TWEET SCREENSHOT ────────────────────────────────────────
def card_tweet_screenshot(tweet_text,label="THIS WEEK"):
    img=Image.new("RGB",(W,H),(10,22,40))
    draw=ImageDraw.Draw(img)
    for y_px in range(H//2):
        t=1-(y_px/(H//2))
        draw.line([(0,y_px),(W,y_px)],fill=(int(245*t+10*(1-t)),int(197*t+22*(1-t)),int(24*t+40*(1-t))))
    for y_px in range(H//2,H):
        t=(y_px-H//2)/(H//2)
        draw.line([(0,y_px),(W,y_px)],fill=(int(10+5*t),int(22+8*t),int(40+10*t)))
    CX,CY,CW,CH=72,120,W-144,660
    draw.rounded_rectangle([(CX,CY),(CX+CW,CY+CH)],radius=24,fill=WHITE)
    LX,LY,LR=CX+40,CY+44,36
    draw.ellipse([(LX,LY),(LX+LR*2,LY+LR*2)],fill=NAVY)
    sf=ImageFont.truetype(FONT_BOLD,11)
    draw.text((LX+8,LY+8),"The",font=sf,fill=GOLD)
    draw.text((LX+4,LY+22),"Ledger",font=sf,fill=WHITE)
    draw.text((LX+8,LY+36),"Wire",font=sf,fill=GOLD)
    nf=ImageFont.truetype(FONT_BOLD,26)
    hf=ImageFont.truetype(FONT_REG,22)
    draw.text((LX+LR*2+20,CY+50),"The Ledger Wire",font=nf,fill=BLACK)
    draw.text((LX+LR*2+20,CY+82),"@LedgerWire",font=hf,fill=(100,100,100))
    draw.line([(CX+40,CY+128),(CX+CW-40,CY+128)],fill=(220,220,220),width=1)
    tf=ImageFont.truetype(FONT_REG,30)
    tbf=ImageFont.truetype(FONT_BOLD,30)
    MTW=CW-80
    lines=tweet_text.split("\n")
    ty=CY+148
    line_h=draw.textbbox((0,0),"Ag",font=tf)[3]+10
    for i,line in enumerate(lines):
        if not line.strip():
            ty+=line_h//2; continue
        font=tbf if i==0 else tf
        wrapped=wrap_text(draw,line,font,MTW)
        for wl in wrapped:
            if ty>CY+CH-120: break
            draw.text((CX+40,ty),wl,font=font,fill=BLACK)
            ty+=line_h
    tif=ImageFont.truetype(FONT_REG,20)
    ts=datetime.now().strftime("%-I:%M %p · %b %-d, %Y")
    draw.text((CX+40,CY+CH-80),ts,font=tif,fill=(100,100,100))
    draw.line([(CX+40,CY+CH-52),(CX+CW-40,CY+CH-52)],fill=(220,220,220),width=1)
    stbf=ImageFont.truetype(FONT_BOLD,20)
    strf=ImageFont.truetype(FONT_REG,20)
    sx,sy=CX+40,CY+CH-36
    for bold_t,reg_t in [("344"," Replies"),("1.2K"," Reposts"),("6.7K"," Likes")]:
        draw.text((sx,sy),bold_t,font=stbf,fill=BLACK)
        bw=draw.textbbox((0,0),bold_t,font=stbf)[2]
        draw.text((sx+bw,sy),reg_t,font=strf,fill=(100,100,100))
        rw=draw.textbbox((0,0),reg_t,font=strf)[2]
        sx+=bw+rw+40
    lbf=ImageFont.truetype(FONT_BOLD,22)
    ubf=ImageFont.truetype(FONT_REG,22)
    draw.text((72,CY+CH+28),label,font=lbf,fill=GOLD)
    utb=draw.textbbox((0,0),"theledgerwire.com",font=ubf)
    draw.text((W-72-(utb[2]-utb[0]),CY+CH+28),"theledgerwire.com",font=ubf,fill=WHITE)
    img.save("card.png","PNG")
    print("Card saved (tweet screenshot)")

# ── GENERATE CARD ─────────────────────────────────────────────────
def generate_news_card(h1,h2,keyword,support_lines=None,hook="",story_context="",used_images=None,story_title="",story_summary=""):
    if used_images is None:
        used_images={}
    photo,img_url=get_photo(keyword,story_context,used_images)
    if photo:
        card_with_photo(apply_gradient(photo),h1,h2,hook)
    else:
        card_no_photo(h1,h2,support_lines,hook)
        img_url=None
    return "card.png",img_url

# ── GITHUB ────────────────────────────────────────────────────────
def push_to_github(image_path,token,repo,file_path):
    print(f"Pushing to GitHub: {file_path}")
    with open(image_path,"rb") as f:
        content=base64.b64encode(f.read()).decode("utf-8")
    headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github.v3+json"}
    get_r=requests.get(f"https://api.github.com/repos/{repo}/contents/{file_path}",headers=headers)
    sha=get_r.json().get("sha") if get_r.status_code==200 else None
    payload={"message":"Add card image","content":content,"branch":"main"}
    if sha: payload["sha"]=sha
    put_r=requests.put(f"https://api.github.com/repos/{repo}/contents/{file_path}",headers=headers,json=payload,timeout=30)
    print(f"GitHub push: {put_r.status_code}")
    return put_r.status_code in [200,201]

# ── BUFFER ────────────────────────────────────────────────────────
def post_to_buffer(post_text,image_url,channel_id,api_key,platform="",retries=2):
    print(f"Posting to Buffer {platform}...")
    time.sleep(3)
    def esc(s):
        return s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','')
    safe_text=esc(post_text)
    cid=channel_id.strip()
    query='''mutation CreatePost {
  createPost(input: {
    text: "%s",
    channelId: "%s",
    schedulingType: automatic,
    mode: addToQueue,
    assets: { images: [{ url: "%s" }] }
  }) {
    ... on PostActionSuccess { post { id text } }
    ... on MutationError { message }
  }
}''' % (safe_text,cid,image_url)
    for attempt in range(retries+1):
        try:
            r=requests.post(
                "https://api.buffer.com",
                headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},
                json={"query":query},timeout=30
            )
            print(f"Buffer {platform}: {r.status_code} — {r.text[:200]}")
            data=r.json()
            post_data=data.get("data",{}).get("createPost",{})
            if "errors" in data:
                print(f"GraphQL errors: {data['errors']}")
                if attempt<retries: time.sleep(5); continue
                return False
            if "message" in post_data and "post" not in post_data:
                print(f"Buffer error: {post_data['message']}")
                if attempt<retries: time.sleep(5); continue
                return False
            return r.status_code==200
        except Exception as e:
            print(f"Buffer {platform} exception: {e}")
            if attempt<retries: time.sleep(5)
    return False

# ── WEEKLY FLOW ───────────────────────────────────────────────────
if CARD_TYPE in ["weekly_tuesday","weekly_friday"]:
    if not WEEKLY_HEADLINES:
        print("No weekly headlines — exiting"); exit(0)
    label=("THIS WEEK" if CARD_TYPE=="weekly_friday" else "THIS MONDAY")
    weekly_result=call_claude_weekly(WEEKLY_HEADLINES,CARD_TYPE)
    if not weekly_result:
        print("Claude weekly failed — exiting"); exit(0)
    tweet_screenshot=weekly_result.get("tweet_screenshot","")
    x_post=weekly_result.get("x_post","")
    linkedin_text=weekly_result.get("linkedin","")
    if not tweet_screenshot:
        print("No screenshot text — exiting"); exit(0)
    card_tweet_screenshot(tweet_screenshot,label)
    if BUFFER_API_KEY and GITHUB_TOKEN:
        pushed=push_to_github("card.png",GITHUB_TOKEN,REPO,IMAGE_PATH)
        if pushed:
            time.sleep(5)
            if BUFFER_PROFILE_X and x_post:
                ok_x=post_to_buffer(x_post,RAW_URL,BUFFER_PROFILE_X,BUFFER_API_KEY,"X")
                print("X: SUCCESS" if ok_x else "X: FAILED")
            if BUFFER_PROFILE_LI and linkedin_text:
                time.sleep(3)
                ok_li=post_to_buffer(linkedin_text,RAW_URL,BUFFER_PROFILE_LI,BUFFER_API_KEY,"LinkedIn")
                print("LinkedIn: SUCCESS" if ok_li else "LinkedIn: FAILED")
    exit(0)

# ── NEWS FLOW ─────────────────────────────────────────────────────
if not STORY_TITLE:
    print("No story title — exiting"); exit(0)

claude_result=call_claude_news(STORY_TITLE,STORY_SUMMARY)
if claude_result=="SKIP" or claude_result is None:
    print("Story skipped — exiting"); exit(0)

tweet_text    =claude_result.get("tweet",    STORY_TITLE)
linkedin_text =claude_result.get("linkedin", STORY_TITLE)
headline1     =claude_result.get("h1",       "Breaking Now")
headline2     =claude_result.get("h2",       "Read Full Story")
hook_text     =claude_result.get("hook",     "")
lines_raw     =claude_result.get("lines",    "")
img_keyword   =claude_result.get("keyword",  IMAGE_KEYWORD)
story_tier    =claude_result.get("tier",     "1").strip()
support_lines =[l.strip() for l in lines_raw.split("|") if l.strip()][:3]

# Hard strip URLs from LinkedIn one more time
linkedin_text = strip_urls(linkedin_text)

print(f"Tier:{story_tier} | Tweet:{x_char_count(tweet_text)} chars")
if x_char_count(tweet_text)>280:
    print("ERROR: Tweet over 280 — exiting"); exit(1)

# Load used images for dedup
used_images=load_used_images()

_,used_img_url=generate_news_card(
    headline1,headline2,img_keyword,support_lines,hook_text,
    story_context=f"{STORY_TITLE} {STORY_SUMMARY}",
    used_images=used_images
)

if BUFFER_API_KEY and GITHUB_TOKEN:
    pushed=push_to_github("card.png",GITHUB_TOKEN,REPO,IMAGE_PATH)
    if pushed:
        # Save used image URL to prevent reuse
        if used_img_url:
            save_used_image(used_img_url,used_images)
        time.sleep(5)
        if BUFFER_PROFILE_X:
            ok_x=post_to_buffer(tweet_text,RAW_URL,BUFFER_PROFILE_X,BUFFER_API_KEY,"X")
            print("X: SUCCESS" if ok_x else "X: FAILED")
        if BUFFER_PROFILE_LI:
            time.sleep(3)
            ok_li=post_to_buffer(linkedin_text,RAW_URL,BUFFER_PROFILE_LI,BUFFER_API_KEY,"LinkedIn")
            print("LinkedIn: SUCCESS" if ok_li else "LinkedIn: FAILED")
    else:
        print("FAILED: GitHub push failed")
else:
    missing=[k for k,v in {"BUFFER_API_KEY":BUFFER_API_KEY,"GITHUB_TOKEN":GITHUB_TOKEN}.items() if not v]
    print(f"Missing: {', '.join(missing)}")
