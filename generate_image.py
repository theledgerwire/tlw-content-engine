# TLW v17
# - Style variants: dark (60%) / vivid (20%) / warm (20%) — FORCE_STYLE env to override
# - Carousel: Slide 1 (existing card) + Slide 2 (stat) + Slide 3 (context) for Tier 1 stories
# - Carousel posted to LinkedIn only (2 per day max) — X stays single card
# - Daily carousel counter stored in data/carousel_count.json
# - PREVIEW_MODE: generates all 3 variants locally without posting
import os, re, time, random, requests, base64, json
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from datetime import datetime

# ── CREDENTIALS ───────────────────────────────────────────────────
BUFFER_API_KEY    = os.environ.get("BUFFER_API_KEY", "")
BUFFER_PROFILE_X  = os.environ.get("BUFFER_PROFILE_X", "")
BUFFER_PROFILE_LI = os.environ.get("BUFFER_PROFILE_LI", "")
BUFFER_PROFILE_IG = os.environ.get("BUFFER_PROFILE_IG", "")  # Instagram
GITHUB_TOKEN      = os.environ.get("GITHUB_TOKEN", "")
ANTHROPIC_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
UNSPLASH_KEY      = os.environ.get("UNSPLASH_KEY", "")
PEXELS_KEY        = os.environ.get("PEXELS_KEY", "")
FAL_KEY           = os.environ.get("FAL_KEY", "")
CARD_TYPE         = os.environ.get("CARD_TYPE", "news")
WEEKLY_HEADLINES  = os.environ.get("WEEKLY_HEADLINES", "")
IMAGE_KEYWORD       = os.environ.get("IMAGE_KEYWORD", "finance technology")
CAROUSEL_MAX_DAILY  = 4          # max PDF carousel posts per day
CAROUSEL_COUNT_PATH = "data/carousel_count.json"
PREVIEW_MODE      = os.environ.get("PREVIEW_MODE", "0") == "1"
FORCE_STYLE       = os.environ.get("FORCE_STYLE", "").lower().strip()  # set to "dark"/"vivid"/"warm" to override random

# ── STYLE VARIANTS ────────────────────────────────────────────────
# Weights control how often each style fires (must sum to 100)
STYLE_VARIANTS = [
    {
        "name":        "dark",
        "weight":       50,
        "flux_style":  "dark background, dramatic studio lighting, navy blue and gold color tones",
        "brightness":   0.62,
        "saturation":   0.85,
        "gradient_opacity": 1.0,   # full navy overlay — current behaviour
    },
    {
        "name":        "vivid",
        "weight":       30,
        "flux_style":  "vibrant colorful background, bold electric blue and emerald green tones, high contrast, bright dramatic lighting, NO dark backgrounds, bright and colourful",
        "brightness":   0.88,
        "saturation":   1.35,
        "gradient_opacity": 0.42,  # lighter overlay — photo colour shows through
    },
    {
        "name":        "warm",
        "weight":       20,
        "flux_style":  "warm rich tones, deep amber and teal color palette, bright cinematic lighting, premium editorial feel, well-lit, NOT dark",
        "brightness":   0.85,
        "saturation":   1.22,
        "gradient_opacity": 0.42,  # middle ground — warm but not washed out
    },
]

def pick_style():
    # FORCE_STYLE override — set env var to lock a specific style
    if FORCE_STYLE:
        for s in STYLE_VARIANTS:
            if s["name"] == FORCE_STYLE:
                print(f"Style FORCED: {s['name']}")
                return s
        print(f"FORCE_STYLE '{FORCE_STYLE}' not recognised — falling back to random")
    weights = [s["weight"] for s in STYLE_VARIANTS]
    chosen  = random.choices(STYLE_VARIANTS, weights=weights, k=1)[0]
    print(f"Style variant: {chosen['name']}")
    return chosen

# Pick once per run so every function uses the same style
ACTIVE_STYLE = pick_style()

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

# ── STORY DEDUPLICATION ───────────────────────────────────────────
USED_STORIES_PATH = "data/used_stories.json"

def load_used_stories():
    """Load set of already-processed story title hashes from GitHub."""
    try:
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}",
                   "Accept": "application/vnd.github.v3+json"}
        r = requests.get(
            f"https://api.github.com/repos/{REPO}/contents/{USED_STORIES_PATH}",
            headers=headers, timeout=10
        )
        if r.status_code == 200:
            import base64 as _b64, json as _json
            data = _b64.b64decode(r.json()["content"]).decode("utf-8")
            return set(_json.loads(data).get("hashes", []))
    except Exception as e:
        print(f"Could not load used stories: {e}")
    return set()

def save_used_story(title_hash):
    """Append a story hash to used_stories.json on GitHub."""
    try:
        import json as _json, base64 as _b64
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}",
                   "Accept": "application/vnd.github.v3+json"}
        # Get current file
        r = requests.get(
            f"https://api.github.com/repos/{REPO}/contents/{USED_STORIES_PATH}",
            headers=headers, timeout=10
        )
        existing = set()
        sha = None
        if r.status_code == 200:
            data = _b64.b64decode(r.json()["content"]).decode("utf-8")
            existing = set(_json.loads(data).get("hashes", []))
            sha = r.json().get("sha")
        existing.add(title_hash)
        # Keep last 200 hashes only
        hashes_list = list(existing)[-200:]
        content_str = _json.dumps({"hashes": hashes_list}, indent=2)
        encoded = _b64.b64encode(content_str.encode()).decode()
        payload = {"message": "Update used stories", "content": encoded, "branch": "main"}
        if sha:
            payload["sha"] = sha
        requests.put(
            f"https://api.github.com/repos/{REPO}/contents/{USED_STORIES_PATH}",
            headers=headers, json=payload, timeout=15
        )
    except Exception as e:
        print(f"Could not save used story: {e}")

def story_hash(title):
    """Create a short hash from story title for dedup."""
    import hashlib
    return hashlib.md5(title.lower().strip()[:80].encode()).hexdigest()[:12]

def story_already_used(title, used_stories):
    """Check if this story title was already processed."""
    h = story_hash(title)
    return h in used_stories

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

_sname = ACTIVE_STYLE["name"]
# ── CAROUSEL DAILY COUNTER ────────────────────────────────────────
CAROUSEL_COUNT_URL = f"https://raw.githubusercontent.com/{REPO}/main/{CAROUSEL_COUNT_PATH}?t={int(time.time())}"

def load_carousel_count():
    try:
        r = requests.get(CAROUSEL_COUNT_URL, timeout=10)
        if r.status_code == 200:
            data = r.json()
            today = datetime.now().strftime("%Y-%m-%d")
            return data.get("date") == today, data.get("count", 0)
    except Exception as e:
        print(f"Could not load carousel count: {e}")
    return False, 0

def save_carousel_count(count):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        payload_data = json.dumps({"date": today, "count": count}, indent=2)
        encoded = base64.b64encode(payload_data.encode()).decode()
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        get_r = requests.get(f"https://api.github.com/repos/{REPO}/contents/{CAROUSEL_COUNT_PATH}", headers=headers, timeout=10)
        sha = get_r.json().get("sha") if get_r.status_code == 200 else None
        payload = {"message": "Update carousel count", "content": encoded, "branch": "main"}
        if sha:
            payload["sha"] = sha
        put_r = requests.put(f"https://api.github.com/repos/{REPO}/contents/{CAROUSEL_COUNT_PATH}", headers=headers, json=payload, timeout=15)
        print(f"Carousel count saved ({count}): {put_r.status_code}")
    except Exception as e:
        print(f"Could not save carousel count: {e}")

def carousel_allowed():
    same_day, count = load_carousel_count()
    if not same_day:
        return True   # new day — reset
    return count < CAROUSEL_MAX_DAILY

print(f"=== TLW v17 === CARD_TYPE: {CARD_TYPE} | Style: {_sname} | Preview: {PREVIEW_MODE}")

# ── PREVIEW MODE — generate all 3 style variants locally, no posting ─
if PREVIEW_MODE:
    import sys
    test_title   = STORY_TITLE or "Fed holds rates as inflation fears mount"
    test_summary = STORY_SUMMARY or "Federal Reserve kept interest rates unchanged, citing persistent inflation"
    print("PREVIEW MODE — generating all 3 style variants...")
    for variant in STYLE_VARIANTS:
        vname = variant["name"]
        print(f"\n--- Rendering style: {vname} ---")
        flux_prompt = generate_flux_prompt(test_title, test_summary, style=variant)
        photo, img_url = fetch_flux_image(flux_prompt) if FAL_KEY and flux_prompt else (None, None)
        if photo:
            gradient_photo = apply_gradient(photo, style=variant)
            out_path = f"preview_{vname}.png"
            gradient_photo.save(out_path, "PNG")
            print(f"Saved: {out_path}")
        else:
            print(f"Flux failed for {vname} — check FAL_KEY")
    print("\nPreview complete. Check preview_dark.png / preview_vivid.png / preview_warm.png")
    sys.exit(0)
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

MANDATORY COVERAGE RULE — these two categories are ALWAYS TIER 1, never skip:
1. CRYPTO: Any story mentioning Bitcoin, Ethereum, crypto, DeFi, stablecoins, blockchain, Coinbase, Binance → always Tier 1
2. MARKETS: Any story mentioning S&P 500, Nasdaq, Dow, stock market rally/crash/correction, sector rotation, VIX → always Tier 1
These topics are core to TLW's audience. Never skip them regardless of other content.

Before writing, decide the angle:
- CAREER IMPACT: "Your job in X just changed." — use when story affects jobs/roles/skills
- MONEY IMPACT: "Your portfolio just got a new variable." — use for markets/valuations/earnings  
- POWER SHIFT: "The company that X is now Y." — use for competition/disruption/bans

Reply in this EXACT format (output ONLY the values, no labels or instructions):

TIER: [1 or 2]
TWEET: [STRICTLY under 220 chars. Write from reader's personal perspective — career, money, or power angle. Curiosity gap. Never explain the full story. End with -> theledgerwire.com #AI #Finance]
LINKEDIN: [Morning Brew style. STRUCTURE:
  LINE 1: Career/personal impact hook — "If you work in [X], this week changed your job." / "The [profession] role just got harder to justify." / "Your [sector] competitors just got a new weapon."
  LINES 2-4: 2-3 short punchy paragraphs. What happened. Why it matters personally. The uncomfortable truth.
  FINAL LINE: One direct question that challenges the reader — "How is your team responding to this?" / "Is your company in the 20% or the 80%?" / "What would you cut first?"
  ABSOLUTELY NO URLs, NO website links, NO theledgerwire.com anywhere.
  Write like a smart senior colleague who just read something important and wants your reaction — not a news anchor.]
H1: [1-3 words MAX — pick the mode that hits hardest for THIS story:
  STAT mode (money/data stories): "$60B." / "58%." / "30,000 jobs." — abbreviate, never spell out
  POWER mode (conflict/ban/crisis/disruption): "Banned." / "War." / "Zero." / "Game Over." / "Fired."
  TENSION mode (two-sided/uncertain stories): "Risk On." / "Too Late?" / "Who Wins?" / "Not Yet."
  Never default to a dollar stat if a power word hits harder. Never repeat H1 formats used today.]
H2: [2-4 words, company + what happened. GOOD: Anthropic. Going public. / Oracle. 6am email. / China. Copying stopped.]
HOOK: [2-5 words, story-specific curiosity gap — must reference something unique to THIS story.
  NEVER use generic phrases like "Watch this space" / "Locals aren't sure" / "More to come" / "Stay tuned"
  GOOD: "Wafer prices next." / "IPO clock starts." / "Beijing not happy." / "One supplier left."
  BAD: "Markets are watching." / "This could change everything." / "Nobody saw this coming."
  REPOST TRIGGER: The hook should make the reader want to tag someone — "Your [colleague/manager/team] needs to see this." type energy.]
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
- Semiconductor/chip → "semiconductor chip close up"
- Europe/EU → "european parliament building"
- Sanctions/trade → "cargo ship port aerial"
- Jobs/layoffs → "empty office building"
NEVER use: "finance technology" / "business" / "woman laptop"
CRITICAL: Never repeat the same keyword as a story posted earlier today. Be specific to THIS story.]
STAT_NUMBER: [the single most impactful number from the story e.g. $2.2B or 40% or 30,000. If no specific number exists use the H1 value]
STAT_LABEL: [3-5 words describing what the stat represents]
STAT_CONTEXT: [one punchy sentence explaining the stat in context]
COMPARE_A_LABEL: [label for smaller/reference comparison e.g. "Industry average" — if no comparison exists write "Before"]
COMPARE_A_VALUE: [value for reference bar — estimate if needed]
COMPARE_B_LABEL: [label for hero comparison e.g. "Oracle-Bloom deal" — if no comparison write "Now"]
COMPARE_B_VALUE: [value for hero bar]
FACT1: [first key fact, max 12 words]
FACT2: [second key fact, max 12 words]
FACT3: [third key fact, max 12 words]"""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 1200, "messages": [{"role": "user", "content": prompt}]},
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
            for key in ["TIER","TWEET","LINKEDIN","H1","H2","HOOK","LINES","KEYWORD","STAT_NUMBER","STAT_LABEL","STAT_CONTEXT","COMPARE_A_LABEL","COMPARE_A_VALUE","COMPARE_B_LABEL","COMPARE_B_VALUE","FACT1","FACT2","FACT3"]:
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
def process_photo(img_data, style=None):
    from PIL import ImageEnhance
    if style is None:
        style = ACTIVE_STYLE
    photo  = Image.open(BytesIO(img_data)).convert("RGB")
    pw, ph = photo.size
    scale  = max(W/pw, H/ph)
    nw, nh = int(pw*scale), int(ph*scale)
    photo  = photo.resize((nw, nh), Image.LANCZOS)
    left   = (nw-W)//2
    top    = (nh-H)//2
    photo  = photo.crop((left, top, left+W, top+H))
    photo  = ImageEnhance.Color(photo).enhance(style["saturation"])
    photo  = ImageEnhance.Brightness(photo).enhance(style["brightness"])
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
def generate_flux_prompt(title, summary, style=None):
    """Claude writes a story-specific Flux.1 image prompt."""
    if style is None:
        style = ACTIVE_STYLE
    if not ANTHROPIC_KEY:
        return None
    try:
        prompt = f"""You are an AI image director for The Ledger Wire, a finance and AI newsletter.

Story: {title}
Summary: {summary}

Generate a Flux.1 image prompt for this financial news card. 

RULES:
1. Match the story LITERALLY — what physical object, building, product, or scene best represents it?
2. Style: {style["flux_style"]}
3. NO text, NO logos, NO faces, NO people
4. Must feel like editorial photography or premium stock — NOT generic tech backgrounds
5. VARY the shot: close-up / wide angle / aerial / macro — not always the same framing
6. Max 25 words

STORY-TO-VISUAL MAPPING:
- IPO/stock listing → trading floor screens with green numbers, wide angle, dramatic lighting
- AI company → specific product shot (not generic circuit boards) e.g. "Anthropic Claude interface on MacBook screen"
- Crypto/Bitcoin → gold coin on dark marble, macro lens, shallow depth of field
- Data centre/cloud → rows of server racks with blue LED lights, wide angle perspective
- Job cuts/layoffs → empty open-plan office, chairs pushed in, late evening light
- Defence/military tech → radar equipment or satellite dish, dramatic sky, photorealistic
- IPO/valuation → NYSE or Nasdaq building facade, golden hour light
- Oil/energy → oil refinery at dusk, orange sky reflection on water
- Fed/interest rates → Federal Reserve building exterior, marble columns, overcast sky
- Trade/tariffs → cargo containers stacked at port, aerial drone shot
- Healthcare/pharma → laboratory glassware, clean white environment, macro
- Semiconductor → silicon wafer close-up, iridescent rainbow surface, macro photography

Your assigned style: {style["name"].upper()}

Reply ONLY with the image prompt. No explanation."""

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
            story_context,
            style=ACTIVE_STYLE
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
def apply_gradient(img, start=0.15, style=None):
    if style is None:
        style = ACTIVE_STYLE
    op        = style["gradient_opacity"]
    sname     = style["name"]
    # Dark style: deep navy overlay. Vivid/warm: near-black but much lighter
    if sname == "dark":
        overlay_rgb = (10, 22, 40)
        top_rgb     = (10, 22, 40)
    elif sname == "vivid":
        overlay_rgb = (0, 10, 30)   # near-black, not navy
        top_rgb     = (0, 10, 30)
    else:  # warm
        overlay_rgb = (15, 10, 5)   # very dark warm tint
        top_rgb     = (15, 10, 5)
    grad = Image.new("RGBA",(W,H),(0,0,0,0))
    gd   = ImageDraw.Draw(grad)
    # Bottom gradient — stronger and starts earlier
    for y in range(int(H*start),H):
        t = float(y-H*start)/float(H*(1-start))
        t = max(0.0,min(1.0,t))
        a = int(255*t**0.65 * op)
        gd.line([(0,y),(W,y)],fill=(*overlay_rgb,a))
    # Top brand bar overlay — stronger so brand text is always readable
    for y in range(0,120):
        t = 1-(y/120)
        a = int(180*t**0.5 * op)
        gd.line([(0,y),(W,y)],fill=(*top_rgb,a))
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

# ── TEXT SHADOW HELPER ───────────────────────────────────────────
def draw_text_shadow(draw, pos, text, font, fill, shadow_color=(0,0,0), offset=3, blur_passes=2):
    """Draw text with a subtle single-offset drop shadow for legibility."""
    x, y = pos
    # Single clean shadow — just draw offset text in dark, then real text on top
    shadow = (0, 0, 0, 160)
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=fill)

# ── COMPANY NAME EXTRACTOR ────────────────────────────────────────
KNOWN_COMPANIES = [
    "OpenAI","Anthropic","Google","Microsoft","Apple","Amazon","Meta","Nvidia",
    "Tesla","Oracle","Samsung","Intel","AMD","TSMC","Qualcomm","IBM","Salesforce",
    "JPMorgan","Goldman Sachs","Goldman","BlackRock","Citigroup","Morgan Stanley",
    "Wells Fargo","Bank of America","HSBC","Barclays","JPMorgan Chase",
    "Coinbase","Binance","Bitcoin","Ethereum","Robinhood","PayPal","Stripe",
    "SpaceX","Uber","Airbnb","Netflix","Spotify","TikTok","ByteDance",
    "Alibaba","Tencent","Baidu","Huawei","SoftBank","Arm","ASML",
    "Palantir","Snowflake","Databricks","Mistral","xAI","DeepMind",
    "LinkedIn","Reddit","Shopify","Zoom","Slack","Adobe","Canva",
    "Boeing","Lockheed","Pfizer","Moderna","Fervo","Factory","Lululemon",
    "Federal Reserve","Fed","SEC","FTC","OPEC","NATO","EU",
]

# Countries and generic words that should NEVER be used as company hero
NOT_COMPANIES = {
    "vietnam","china","india","japan","korea","russia","ukraine","iran","israel",
    "france","germany","spain","italy","europe","asia","africa","america",
    "big","tech","market","retail","traders","bank","banks","house","white",
    "new","the","this","that","its","their","global","world","local",
    "government","ministry","congress","senate","president","minister",
}

def extract_company(h2, story_title=""):
    """Extract the dominant company name from H2 or story title."""
    import re as _re
    text = f"{h2} {story_title}"
    # Check known companies first (longest match wins)
    for co in sorted(KNOWN_COMPANIES, key=len, reverse=True):
        if co.lower() in text.lower():
            return co.upper()
    # Fallback: grab first capitalised word — but filter out countries/generic words
    m = _re.match(r"([A-Z][A-Za-z&]+)", h2.strip())
    if m:
        word = m.group(1).rstrip(".,")
        if len(word) >= 3 and word.lower() not in NOT_COMPANIES:
            return word.upper()
    return None  # Return None — card will show H1 stat as hero instead

def get_source_label(story_title=""):
    """Infer source from story context."""
    t = story_title.lower()
    if "bloomberg" in t: return "Bloomberg"
    if "reuters" in t:   return "Reuters"
    if "wsj" in t or "wall street" in t: return "WSJ"
    if "techcrunch" in t: return "TechCrunch"
    if "ft" in t or "financial times" in t: return "FT"
    if "coindesk" in t:  return "CoinDesk"
    if "marketwatch" in t: return "MarketWatch"
    if "ai news" in t or "artificialintelligence" in t: return "AI News"
    return ""   # No badge if source unknown — cleaner than "TLW Research"

# ── CARD: PHOTO ───────────────────────────────────────────────────
def card_with_photo(img,h1,h2,hook="",company_name=None,source=""):
    """Concept B: Company name as hero element, stat below, source badge top-right."""
    draw = ImageDraw.Draw(img)
    PAD  = 56
    MTW  = W - PAD - 40

    # ── Fonts ──
    co_f    = ImageFont.truetype(FONT_BOLD, 100)  # company name — BIG
    h1_f    = ImageFont.truetype(FONT_BOLD, 76)   # stat
    h2_f    = ImageFont.truetype(FONT_BOLD, 38)   # description
    hook_f  = ImageFont.truetype(FONT_BOLD, 36)   # hook
    src_f   = ImageFont.truetype(FONT_REG,  18)
    badge_f = ImageFont.truetype(FONT_BOLD, 16)
    logo_f  = ImageFont.truetype(FONT_BOLD, 18)

    # ── Top brand bar ──
    draw_text_shadow(draw, (PAD, 34), "THE LEDGER WIRE", logo_f, WHITE, shadow_color=(0,0,0), offset=2)
    lb = draw.textbbox((0,0), "THE LEDGER WIRE", font=logo_f)
    draw.rectangle([(PAD, 56), (PAD + lb[2] - lb[0], 58)], fill=GOLD)

    # ── Source badge top-right — only if we have a real source ──
    if source:
        sb = draw.textbbox((0,0), source, font=badge_f)
        sb_w = sb[2] - sb[0] + 20
        sb_x = W - PAD - sb_w
        draw.rectangle([(sb_x, 28), (sb_x + sb_w, 56)], outline=GOLD, width=1)
        draw.text((sb_x + 10, 36), source, font=badge_f, fill=GOLD)

    # ── Measure all text blocks ──
    company_display = company_name if company_name else ""
    has_company = bool(company_display)

    # If no company found, bump H1 to 100pt as the hero element
    if not has_company:
        co_f = h1_f   # reuse h1 slot visually
        h1_f = ImageFont.truetype(FONT_BOLD, 60)  # shrink h1 since it's secondary

    co_lines  = wrap_text(draw, company_display, co_f, MTW) if has_company else []
    h1_lines  = wrap_text(draw, h1,  h1_f,  MTW)
    h2_lines  = wrap_text(draw, h2,  h2_f,  MTW)
    hook_lines= wrap_text(draw, hook, hook_f, MTW) if hook else []

    co_lh  = draw.textbbox((0,0), "Ag", font=co_f)[3]
    h1_lh  = draw.textbbox((0,0), "Ag", font=h1_f)[3]
    h2_lh  = draw.textbbox((0,0), "Ag", font=h2_f)[3]
    hk_lh  = draw.textbbox((0,0), "Ag", font=hook_f)[3]

    tco  = co_lh  * min(len(co_lines), 2)  + 4
    th1  = h1_lh  * min(len(h1_lines), 2)  + 4
    th2  = h2_lh  * min(len(h2_lines), 2)  + 4
    thk  = hk_lh  * min(len(hook_lines), 1)

    # ── Layout from bottom up ──
    SAFE   = H - 72 - 20
    src_y  = SAFE - 20
    hook_y = src_y  - 16 - thk if hook_lines else src_y
    h2_y   = hook_y - 12 - th2
    rule_y = h2_y   - 18
    h1_y   = rule_y - 14 - th1
    co_y   = h1_y   - 8  - tco

    # Gold accent line between company and stat
    draw.rectangle([(PAD, rule_y), (PAD + 56, rule_y + 4)], fill=GOLD)

    # ── Company name — GOLD, massive ──
    if co_lines:
        y = co_y
        for line in co_lines[:2]:
            draw_text_shadow(draw, (PAD, y), line, co_f, GOLD,
                             shadow_color=(0,0,0), offset=3)
            y += co_lh + 4

    # ── H1 stat — WHITE, bold ──
    y = h1_y
    for line in h1_lines[:2]:
        draw_text_shadow(draw, (PAD, y), line, h1_f, WHITE,
                         shadow_color=(0,0,0), offset=3)
        y += h1_lh + 4

    # ── H2 description — lighter white ──
    y = h2_y
    for line in h2_lines[:2]:
        draw_text_shadow(draw, (PAD, y), line, h2_f,
                         (210, 210, 210), shadow_color=(0,0,0), offset=2)
        y += h2_lh + 4

    # ── Hook — white italic feel ──
    if hook_lines:
        draw_text_shadow(draw, (PAD, hook_y), hook_lines[0], hook_f,
                         (180, 180, 180), shadow_color=(0,0,0), offset=2)

    # ── Footer URL ──
    draw_text_shadow(draw, (PAD, src_y), "theledgerwire.com", src_f,
                     WHITE, shadow_color=(0,0,0), offset=1)

    draw_footer(draw)
    img.save("card.png", "PNG")
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

# ── CAROUSEL: STAT CARD (Slide 2) — Data Viz Chart ──────────────
def card_carousel_stat(stat_number, stat_label, stat_context, compare_a_label, compare_a_value, compare_b_label, compare_b_value):
    """Bold data visualisation chart card for carousel slide 2 — Var 2: White/Blue/Gold."""
    UA_BLUE = (58, 101, 185)
    NAVY2   = (10, 22, 40)
    GREY_T  = (160, 160, 160)

    img  = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    PAD  = 72

    # ── Double stripe header: UA_BLUE on top, GOLD below ──
    draw.rectangle([(0, 0),  (W, 18)], fill=UA_BLUE)
    draw.rectangle([(0, 18), (W, 32)], fill=GOLD)
    # ── Bottom footer bar ──
    draw.rectangle([(0, H - 12), (W, H)], fill=UA_BLUE)

    # ── Brand label — UA_BLUE, fully readable on white ──
    lf = ImageFont.truetype(FONT_BOLD, 22)
    draw.text((PAD, 50), "THE LEDGER WIRE", font=lf, fill=UA_BLUE)

    # ── Big bold ALL-CAPS title (stat_label as headline) ──
    tf  = ImageFont.truetype(FONT_BOLD, 68)
    tlh = draw.textbbox((0, 0), "Ag", font=tf)[3]
    title_lines = wrap_text(draw, stat_label.upper(), tf, W - PAD * 2)
    y = 110
    for line in title_lines[:2]:
        draw.text((PAD, y), line, font=tf, fill=NAVY2)
        y += tlh + 4

    # ── Source label ──
    sf2 = ImageFont.truetype(FONT_REG, 22)
    draw.text((PAD, y + 8), f"SOURCE: THE LEDGER WIRE  ·  {stat_context[:40].upper()}", font=sf2, fill=GREY_T)
    y += 52

    # ── Parse values for chart bars ──
    def parse_val(v):
        """Extract numeric from strings like $30B, 74%, 25,000"""
        import re
        v = str(v).replace(',','').replace('$','').replace('%','')
        m = re.search(r'[\d.]+([BMK])?', v, re.I)
        if not m: return 1.0
        n = float(m.group(0).rstrip('BMKbmk'))
        suf = (m.group(1) or '').upper()
        if suf == 'B': n *= 1000
        elif suf == 'M': n *= 1
        elif suf == 'K': n *= 0.001
        return max(n, 0.01)

    val_a = parse_val(compare_a_value)
    val_b = parse_val(compare_b_value)
    max_v = max(val_a, val_b) * 1.15

    # ── Chart area ──
    chart_left  = PAD
    chart_right = W - PAD
    chart_w     = chart_right - chart_left
    chart_top   = y + 20
    chart_bot   = H - 160
    chart_h     = chart_bot - chart_top

    # ── Horizontal grid lines ──
    gf = ImageFont.truetype(FONT_REG, 20)
    for pct in [0, 25, 50, 75, 100]:
        gy = chart_bot - int(chart_h * pct / 100)
        draw.line([(chart_left, gy), (chart_right, gy)], fill=(225, 225, 225), width=1)
        # y-axis label
        lbl_v = f"{int(max_v * pct / 100)}"
        draw.text((chart_left - 8, gy - 12), lbl_v, font=gf, fill=(160, 160, 160), anchor="ra")

    # ── Bar dimensions ──
    n_bars   = 2
    grp_w    = chart_w // n_bars
    bar_w    = int(grp_w * 0.52)
    colors   = [GOLD, UA_BLUE]
    values   = [val_a, val_b]
    labels   = [compare_a_label or "Before", compare_b_label or "Now"]
    raw_vals = [compare_a_value, compare_b_value]

    bvf = ImageFont.truetype(FONT_BOLD, 28)
    blf = ImageFont.truetype(FONT_BOLD, 24)

    val_colors = [(160, 120, 0), UA_BLUE]
    for i, (val, col, lbl, raw) in enumerate(zip(values, colors, labels, raw_vals)):
        bx    = chart_left + i * grp_w + (grp_w - bar_w) // 2
        bar_h2 = int(chart_h * min(val / max_v, 1.0))
        by    = chart_bot - bar_h2

        # Bar
        draw.rectangle([(bx, by), (bx + bar_w, chart_bot)], fill=col)

        # Value label ON TOP of bar
        vb = draw.textbbox((0, 0), raw, font=bvf)
        vw = vb[2] - vb[0]
        draw.text((bx + (bar_w - vw) // 2, by - 40), raw, font=bvf, fill=val_colors[i])

        # X-axis label below bar
        lb2 = draw.textbbox((0, 0), lbl, font=blf)
        lw  = lb2[2] - lb2[0]
        draw.text((bx + (bar_w - lw) // 2, chart_bot + 14), lbl, font=blf, fill=NAVY2)

    # ── Stat number callout (bottom left) ──
    snf  = ImageFont.truetype(FONT_BOLD, 52)
    snlf = ImageFont.truetype(FONT_REG, 22)
    draw.text((PAD, H - 130), stat_number, font=snf, fill=UA_BLUE)
    snb  = draw.textbbox((0, 0), stat_number, font=snf)
    draw.text((PAD + snb[2] + 12, H - 115), "KEY FIGURE", font=snlf, fill=(160, 160, 160))

    # ── Footer ──
    ff = ImageFont.truetype(FONT_REG, 22)
    draw.text((W - PAD, H - 48), "theledgerwire.com", font=ff, fill=UA_BLUE, anchor="ra")

    img.save("carousel_2.png", "PNG")
    print("Carousel slide 2 saved (chart mode)")

# ── CAROUSEL: CONTEXT CARD (Slide 3) ─────────────────────────────
def card_carousel_context(fact1, fact2, fact3, h1, h2):
    """Light white context card for carousel slide 3."""
    img  = Image.new("RGB", (W, H), (255, 255, 255))   # pure white
    draw = ImageDraw.Draw(img)
    PAD  = 80

    # Left gold accent bar
    draw.rectangle([(0, 0), (10, H)], fill=GOLD)

    # Top labels
    lf = ImageFont.truetype(FONT_BOLD, 24)
    draw.text((PAD, 64),  "THE LEDGER WIRE", font=lf, fill=GOLD)
    draw.text((PAD, 100), "WHY IT MATTERS",  font=lf, fill=(160, 160, 160))

    # Story reference — navy bold
    h2f  = ImageFont.truetype(FONT_BOLD, 52)
    h2lh = draw.textbbox((0, 0), "Ag", font=h2f)[3]
    ref  = f"{h1} — {h2}"
    ref_lines = wrap_text(draw, ref, h2f, W - PAD * 2)
    y = 164
    for rl in ref_lines[:2]:
        draw.text((PAD, y), rl, font=h2f, fill=NAVY)
        y += h2lh + 6
    y += 16
    draw.rectangle([(PAD, y), (PAD + 140, y + 5)], fill=GOLD)
    y += 44

    # Three bullet facts — larger text, more breathing room
    bf       = ImageFont.truetype(FONT_REG,  38)
    bfb      = ImageFont.truetype(FONT_BOLD, 38)
    blh      = draw.textbbox((0, 0), "Ag", font=bf)[3]
    colors   = [GOLD, (83, 74, 183), (29, 158, 117)]
    facts    = [f for f in [fact1, fact2, fact3] if f]

    for i, fact in enumerate(facts[:3]):
        col        = colors[i]
        bar_top    = y + 6
        bar_bottom = y + blh - 6
        draw.rounded_rectangle([(PAD, bar_top), (PAD + 7, bar_bottom)], radius=3, fill=col)
        fact_lines = wrap_text(draw, fact, bf, W - PAD * 2 - 36)
        for fl in fact_lines[:2]:
            draw.text((PAD + 36, y), fl, font=bf, fill=(45, 45, 45))
            y += blh + 8
        y += 52   # generous gap between facts

    # Footer
    ff = ImageFont.truetype(FONT_REG, 24)
    draw.text((PAD, H - 60), "theledgerwire.com", font=ff, fill=GOLD)
    draw.rectangle([(0, H - 10), (W, H)], fill=GOLD)
    img.save("carousel_3.png", "PNG")
    print("Carousel slide 3 saved")

# ── CAROUSEL: CTA CARD (Slide 4 — Instagram only) ─────────────────
def card_carousel_cta():
    """Dark CTA card for carousel slide 4."""
    img  = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(img)
    cx   = W // 2

    # Circle logo
    r = 110
    draw.ellipse([(cx - r, 340), (cx + r, 340 + r * 2)], fill=GOLD)
    lf = ImageFont.truetype(FONT_BOLD, 56)
    lb = draw.textbbox((0, 0), "TLW", font=lf)
    draw.text((cx - (lb[2] - lb[0]) // 2, 340 + r - (lb[3] - lb[1]) // 2), "TLW", font=lf, fill=NAVY)

    # Tagline
    tf  = ImageFont.truetype(FONT_BOLD, 52)
    tag = "AI & Finance,"
    tb  = draw.textbbox((0, 0), tag, font=tf)
    draw.text((cx - (tb[2] - tb[0]) // 2, 620), tag, font=tf, fill=WHITE)
    tag2 = "decoded daily."
    tb2  = draw.textbbox((0, 0), tag2, font=tf)
    draw.text((cx - (tb2[2] - tb2[0]) // 2, 686), tag2, font=tf, fill=GOLD)

    # Handle
    hf  = ImageFont.truetype(FONT_REG, 34)
    hb  = draw.textbbox((0, 0), "@LedgerWire", font=hf)
    draw.text((cx - (hb[2] - hb[0]) // 2, 780), "@LedgerWire", font=hf, fill=(150, 150, 180))

    # CTA pill
    pill_w, pill_h, pill_r = 420, 72, 36
    pill_x = cx - pill_w // 2
    pill_y = 870
    draw.rounded_rectangle([(pill_x, pill_y), (pill_x + pill_w, pill_y + pill_h)], radius=pill_r, fill=GOLD)
    wf  = ImageFont.truetype(FONT_BOLD, 28)
    wb  = draw.textbbox((0, 0), "theledgerwire.com", font=wf)
    draw.text((cx - (wb[2] - wb[0]) // 2, pill_y + (pill_h - (wb[3] - wb[1])) // 2), "theledgerwire.com", font=wf, fill=NAVY)

    img.save("carousel_4.png", "PNG")
    print("Carousel slide 4 saved (CTA)")


# ── PDF CAROUSEL GENERATOR ────────────────────────────────────────
def generate_carousel_pdf(output_path, h1, h2, hook,
                           stat_number, stat_label, stat_context,
                           compare_a_label, compare_a_value,
                           compare_b_label, compare_b_value,
                           fact1, fact2, fact3, takeaway):
    """Generate a 5-slide LinkedIn PDF carousel."""
    try:
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.colors import HexColor, white
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import re as _re
    except ImportError:
        print("ERROR: reportlab not installed — add to pip install in workflow YAML")
        return False

    _W = _H = 1080
    _NAVY    = HexColor('#0A1628')
    _GOLD    = HexColor('#F5C518')
    _UABLUE  = HexColor('#3A65B9')
    _PURPLE  = HexColor('#534AB7')
    _TEAL    = HexColor('#1D9E75')
    _WHITE   = white
    _LGREY   = HexColor('#F0EDE5')
    _MGREY   = HexColor('#999999')
    _DGREY   = HexColor('#333333')
    _BOLD    = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    _REG     = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

    try:
        pdfmetrics.registerFont(TTFont('TLW-Bold', _BOLD))
        pdfmetrics.registerFont(TTFont('TLW-Reg',  _REG))
    except Exception: pass

    def _wrap(text, width_chars):
        words = text.split(); lines = []; line = ""
        for w in words:
            test = (line + " " + w).strip()
            if len(test) <= width_chars: line = test
            else:
                if line: lines.append(line)
                line = w
        if line: lines.append(line)
        return lines

    def _footer(c, slide_num, total=5):
        c.setFillColor(_GOLD)
        c.rect(0, 0, _W, 56, fill=1, stroke=0)
        c.setFillColor(_NAVY)
        c.setFont('TLW-Bold', 18)
        c.drawString(40, 18, "THE LEDGER WIRE")
        c.setFont('TLW-Reg', 16)
        c.drawRightString(_W - 40, 18, "theledgerwire.com")
        dot_y = _H - 20
        dot_start = _W/2 - (total * 16)/2
        for i in range(total):
            if i == slide_num:
                c.setFillColor(_NAVY); c.circle(dot_start + i*16, dot_y, 5, fill=1, stroke=0)
            else:
                c.setFillColor(HexColor('#CCCCCC')); c.circle(dot_start + i*16, dot_y, 3, fill=1, stroke=0)

    c = rl_canvas.Canvas(output_path, pagesize=(_W, _H))

    # ── SLIDE 1: Cover ──
    c.setFillColor(_NAVY); c.rect(0, 0, _W, _H, fill=1, stroke=0)
    c.setFillColor(_GOLD); c.rect(0, 56, 8, _H-56, fill=1, stroke=0)
    c.setFillColor(_GOLD); c.setFont('TLW-Bold', 20); c.drawString(52, _H-52, "THE LEDGER WIRE")
    c.setFillColor(HexColor('#8892A4')); c.setFont('TLW-Reg', 14); c.drawString(52, _H-76, "AI & FINANCE · DECODED")
    c.setFillColor(_GOLD); c.rect(52, _H-104, 60, 3, fill=1, stroke=0)
    c.setFillColor(_GOLD); c.setFont('TLW-Bold', 130)
    sw = c.stringWidth(stat_number, 'TLW-Bold', 130)
    fs = 90 if sw > _W-104 else 130
    c.setFont('TLW-Bold', fs); c.drawString(52, _H-290, stat_number)
    c.setFillColor(_WHITE); c.setFont('TLW-Bold', 52)
    y = _H - 360
    for line in _wrap(h1, 22)[:3]: c.drawString(52, y, line); y -= 62
    c.setFillColor(_GOLD); c.setFont('TLW-Bold', 36)
    for line in _wrap(h2, 30)[:2]: c.drawString(52, y, line); y -= 44
    if hook:
        c.setFillColor(_WHITE); c.setFont('TLW-Bold', 30); c.drawString(52, y-14, hook)
    c.setFillColor(HexColor('#8892A4')); c.setFont('TLW-Reg', 18)
    c.drawRightString(_W-40, 72, "Swipe for the data →")
    _footer(c, 0); c.showPage()

    # ── SLIDE 2: Chart ──
    c.setFillColor(_WHITE); c.rect(0, 0, _W, _H, fill=1, stroke=0)
    c.setFillColor(_UABLUE); c.rect(0, _H-18, _W, 18, fill=1, stroke=0)
    c.setFillColor(_GOLD);   c.rect(0, _H-32, _W, 14, fill=1, stroke=0)
    c.setFillColor(_UABLUE); c.rect(0, 0, _W, 56, fill=1, stroke=0)
    c.setFillColor(_UABLUE); c.setFont('TLW-Bold', 20); c.drawString(52, _H-66, "THE LEDGER WIRE")
    c.setFillColor(_MGREY);  c.setFont('TLW-Reg', 14);  c.drawString(52, _H-86, "BY THE NUMBERS")
    c.setFillColor(_NAVY);   c.setFont('TLW-Bold', 54)
    y = _H - 148
    for line in _wrap(stat_label.upper(), 20)[:2]: c.drawString(52, y, line); y -= 64
    c.setFillColor(_MGREY); c.setFont('TLW-Reg', 17)
    c.drawString(52, y-8, f"SOURCE: THE LEDGER WIRE  ·  {stat_context[:32].upper()}"); y -= 52
    def _pval(v):
        v = str(v).replace(',','').replace('$','').replace('%','')
        m = _re.search(r'[\d.]+([BMK])?', v, _re.I)
        if not m: return 1.0
        n = float(m.group(0).rstrip('BMKbmk'))
        suf = (m.group(1) or '').upper()
        if suf=='B': n*=1000
        return max(n, 0.01)
    va=_pval(compare_a_value); vb=_pval(compare_b_value); mv=max(va,vb)*1.18
    cl=100; cr=_W-60; cw=cr-cl; cbot=140; ctop=y-20; ch=ctop-cbot
    c.setStrokeColor(HexColor('#E5E5E5')); c.setLineWidth(0.8)
    c.setFillColor(_MGREY); c.setFont('TLW-Reg', 15)
    for pct in [0,25,50,75,100]:
        gy=cbot+int(ch*pct/100); c.line(cl,gy,cr,gy)
        c.drawRightString(cl-8, gy-5, f"{int(mv*pct/100)}B")
    gw=cw//2; bw=int(gw*0.52)
    bcols=[_GOLD,_UABLUE]; vcols=[HexColor('#A07800'),_UABLUE]
    vals=[va,vb]; lbls=[compare_a_label or "Before",compare_b_label or "Now"]
    raws=[compare_a_value,compare_b_value]
    for i,(val,bc,vc,lbl,raw) in enumerate(zip(vals,bcols,vcols,lbls,raws)):
        bx=cl+i*gw+(gw-bw)//2; bh2=int(ch*min(val/mv,1.0))
        c.setFillColor(bc); c.rect(bx,cbot,bw,bh2,fill=1,stroke=0)
        c.setFillColor(vc); c.setFont('TLW-Bold',24); c.drawCentredString(bx+bw/2,cbot+bh2+10,raw)
        c.setFillColor(_NAVY); c.setFont('TLW-Bold',18); c.drawCentredString(bx+bw/2,cbot-26,lbl)
    c.setFillColor(_UABLUE); c.setFont('TLW-Bold',38); c.drawString(52,66,stat_number)
    c.setFillColor(_MGREY);  c.setFont('TLW-Reg',15)
    sw2=c.stringWidth(stat_number,'TLW-Bold',38); c.drawString(52+sw2+10,76,"KEY FIGURE")
    c.setFillColor(_WHITE); c.setFont('TLW-Reg',15); c.drawRightString(_W-40,18,"theledgerwire.com")
    _footer(c, 1); c.showPage()

    # ── SLIDE 3: Context ──
    c.setFillColor(_WHITE); c.rect(0, 0, _W, _H, fill=1, stroke=0)
    c.setFillColor(_GOLD); c.rect(0, 56, 10, _H-56, fill=1, stroke=0)
    c.setFillColor(_GOLD); c.setFont('TLW-Bold',20); c.drawString(52,_H-52,"THE LEDGER WIRE")
    c.setFillColor(_MGREY); c.setFont('TLW-Reg',14); c.drawString(52,_H-76,"WHY IT MATTERS")
    c.setFillColor(_NAVY); c.setFont('TLW-Bold',42)
    y=_H-148
    for line in _wrap(f"{h1} — {h2}", 26)[:2]: c.drawString(52,y,line); y-=52
    c.setFillColor(_GOLD); c.rect(52,y-10,140,4,fill=1,stroke=0); y-=52
    fact_cols=[_GOLD,_PURPLE,_TEAL]
    facts=[f for f in [fact1,fact2,fact3] if f]
    c.setFont('TLW-Reg',28)
    for fact,col in zip(facts[:3],fact_cols):
        c.setFillColor(col); c.rect(52,y+4,7,28,fill=1,stroke=0)
        c.setFillColor(_DGREY)
        for fl in _wrap(fact,40)[:2]: c.drawString(76,y,fl); y-=34
        y-=42
    # ── TLW Takeaway strip embedded at bottom of slide 3 ──
    if y > 150:
        c.setFillColor(_NAVY)
        c.rect(40, 68, _W-80, 74, fill=1, stroke=0)
        c.setFillColor(_GOLD)
        c.rect(40, 68, 6, 74, fill=1, stroke=0)
        c.setFillColor(_GOLD); c.setFont('TLW-Bold', 13)
        c.drawString(60, 124, "⚡ TLW TAKEAWAY")
        c.setFillColor(_WHITE); c.setFont('TLW-Reg', 19)
        tw_lines = _wrap(takeaway, 54)
        ty = 104
        for tl in tw_lines[:2]:
            c.drawString(60, ty, tl); ty -= 22

    _footer(c, 2)
    c.save()
    print(f"PDF carousel saved: {output_path}")
    return True

# ── GENERATE CARD ─────────────────────────────────────────────────
def generate_news_card(h1,h2,keyword,support_lines=None,hook="",story_context="",used_images=None,story_title="",story_summary=""):
    if used_images is None:
        used_images={}
    company = extract_company(h2, story_title)
    source  = get_source_label(story_title)
    photo,img_url=get_photo(keyword,story_context,used_images)
    if photo:
        card_with_photo(apply_gradient(photo), h1, h2, hook,
                        company_name=company, source=source)
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
def post_to_buffer_carousel(post_text, image_urls, channel_id, api_key, platform="", retries=2):
    """Post a multi-image carousel to Buffer (LinkedIn / Instagram)."""
    print(f"Posting carousel to Buffer {platform} ({len(image_urls)} slides)...")
    time.sleep(3)
    def esc(s):
        return s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','')
    safe_text = esc(post_text)
    cid       = channel_id.strip()
    imgs_gql  = ", ".join([f'{{ url: "{u}" }}' for u in image_urls])
    query = (
        'mutation CreatePost {\n'
        '  createPost(input: {\n'
        '    text: "%s",\n'
        '    channelId: "%s",\n'
        '    schedulingType: automatic,\n'
        '    mode: addToQueue,\n'
        '    assets: { images: [%s] }\n'
        '  }) {\n'
        '    ... on PostActionSuccess { post { id text } }\n'
        '    ... on MutationError { message }\n'
        '  }\n'
        '}'
    ) % (safe_text, cid, imgs_gql)
    for attempt in range(retries + 1):
        try:
            r = requests.post(
                "https://api.buffer.com",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"query": query}, timeout=30
            )
            print(f"Buffer {platform} carousel: {r.status_code} — {r.text[:200]}")
            data      = r.json()
            post_data = data.get("data", {}).get("createPost", {})
            if "errors" in data:
                if attempt < retries: time.sleep(5); continue
                return False
            if "message" in post_data and "post" not in post_data:
                if attempt < retries: time.sleep(5); continue
                return False
            return r.status_code == 200
        except Exception as e:
            print(f"Buffer {platform} carousel exception: {e}")
            if attempt < retries: time.sleep(5)
    return False

def post_to_buffer_document(post_text, doc_url, channel_id, api_key, retries=2):
    """Post a PDF document carousel to LinkedIn via Buffer."""
    print(f"Posting LinkedIn PDF document...")
    time.sleep(3)
    def esc(s):
        return s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','')
    safe_text = esc(post_text)
    cid = channel_id.strip()
    query = (
        'mutation CreatePost {\n'
        '  createPost(input: {\n'
        '    text: "%s",\n'
        '    channelId: "%s",\n'
        '    schedulingType: automatic,\n'
        '    mode: addToQueue,\n'
        '    assets: { documents: [{ url: "%s" }] }\n'
        '  }) {\n'
        '    ... on PostActionSuccess { post { id text } }\n'
        '    ... on MutationError { message }\n'
        '  }\n'
        '}'
    ) % (safe_text, cid, doc_url)
    for attempt in range(retries + 1):
        try:
            r = requests.post(
                "https://api.buffer.com",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"query": query}, timeout=30
            )
            print(f"Buffer LinkedIn doc: {r.status_code} — {r.text[:200]}")
            data = r.json()
            post_data = data.get("data", {}).get("createPost", {})
            if "errors" in data:
                if attempt < retries: time.sleep(5); continue
                return False
            if "message" in post_data and "post" not in post_data:
                if attempt < retries: time.sleep(5); continue
                return False
            return r.status_code == 200
        except Exception as e:
            print(f"Buffer LinkedIn doc exception: {e}")
            if attempt < retries: time.sleep(5)
    return False


def post_to_buffer_instagram(post_text, image_url, channel_id, api_key, retries=2):
    """Post to Instagram via Buffer — requires mediaType: IMAGE explicitly."""
    print(f"Posting to Buffer Instagram...")
    time.sleep(3)
    def esc(s):
        return s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','')
    safe_text = esc(post_text)
    cid = channel_id.strip()
    query = '''mutation CreatePost {
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
}''' % (safe_text, cid, image_url)
    for attempt in range(retries + 1):
        try:
            r = requests.post(
                "https://api.buffer.com",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"query": query}, timeout=30
            )
            print(f"Buffer Instagram: {r.status_code} — {r.text[:300]}")
            data = r.json()
            post_data = data.get("data", {}).get("createPost", {})
            if "errors" in data:
                print(f"GraphQL errors: {data['errors']}")
                if attempt < retries: time.sleep(5); continue
                return False
            if "message" in post_data and "post" not in post_data:
                print(f"Buffer Instagram error: {post_data['message']}")
                if attempt < retries: time.sleep(5); continue
                return False
            return r.status_code == 200
        except Exception as e:
            print(f"Buffer Instagram exception: {e}")
            if attempt < retries: time.sleep(5)
    return False

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
            if BUFFER_PROFILE_IG:
                time.sleep(3)
                ok_ig=post_to_buffer_instagram(ig_caption if 'ig_caption' in dir() else linkedin_text,RAW_URL,BUFFER_PROFILE_IG,BUFFER_API_KEY)
                print("Instagram: SUCCESS" if ok_ig else "Instagram: FAILED")
    exit(0)

# ── NEWS FLOW ─────────────────────────────────────────────────────
if not STORY_TITLE:
    print("No story title — exiting"); exit(0)

# ── Check if story already processed ──
used_stories = load_used_stories()
if story_already_used(STORY_TITLE, used_stories):
    print(f"DUPLICATE: Story already processed — skipping: {STORY_TITLE[:60]}")
    exit(0)

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

# Carousel fields — always populated by Claude for Tier 1
stat_number     = claude_result.get("stat_number",     headline1)
stat_label      = claude_result.get("stat_label",      headline2)
stat_context    = claude_result.get("stat_context",    "")
compare_a_label = claude_result.get("compare_a_label", "")
compare_a_value = claude_result.get("compare_a_value", "")
compare_b_label = claude_result.get("compare_b_label", "")
compare_b_value = claude_result.get("compare_b_value", "")
fact1           = claude_result.get("fact1",            "")
fact2           = claude_result.get("fact2",            "")
fact3           = claude_result.get("fact3",            "")

# Stat number guard — only carousel if stat contains a real number/symbol
def has_real_stat(val):
    """Returns True if stat_number contains $, %, or a digit — i.e. is a real data point."""
    return bool(re.search(r'[$%\d]', val)) if val else False

stat_is_real = has_real_stat(stat_number)

# Carousel fires automatically for Tier 1 stories WITH a real stat, within daily limit
do_carousel = (story_tier == "1") and stat_is_real and carousel_allowed()
if story_tier == "1" and not stat_is_real:
    print(f"Carousel skipped — no real stat found in: '{stat_number}'")
if story_tier == "1" and stat_is_real and not carousel_allowed():
    print("Carousel daily limit reached (2/day) — falling back to single card")

print(f"Tier:{story_tier} | Stat:'{stat_number}' | RealStat:{stat_is_real} | Carousel:{do_carousel} | Tweet:{x_char_count(tweet_text)} chars")
print(f"DEBUG carousel fields — stat_label:'{stat_label}' | fact1:'{fact1}' | fact2:'{fact2}'")

# Hard strip URLs from LinkedIn one more time
linkedin_text = strip_urls(linkedin_text)

# ── Instagram caption — punchy, hashtag-rich, no link (goes in bio) ──
ig_caption = f"""{headline1}

{headline2}

{hook_text}

Follow @theledgerwire.ai for daily AI & Finance intel.

#AI #Finance #Tech #Investing #Markets #ArtificialIntelligence #FinanceNews #AINews #StockMarket #Crypto"""

if x_char_count(tweet_text)>280:
    print("ERROR: Tweet over 280 — exiting"); exit(1)

# Load used images for dedup
used_images=load_used_images()

# Always build slide 1 (existing card)
_,used_img_url=generate_news_card(
    headline1,headline2,img_keyword,support_lines,hook_text,
    story_context=f"{STORY_TITLE} {STORY_SUMMARY}",
    used_images=used_images
)

if BUFFER_API_KEY and GITHUB_TOKEN:
    pushed=push_to_github("card.png",GITHUB_TOKEN,REPO,IMAGE_PATH)
    if pushed:
        if used_img_url:
            save_used_image(used_img_url,used_images)
        time.sleep(5)

        # ── X: always single card, no carousel ────────────────────
        if BUFFER_PROFILE_X:
            time.sleep(3)
            ok_x = post_to_buffer(tweet_text, RAW_URL, BUFFER_PROFILE_X, BUFFER_API_KEY, "X")
            print("X: SUCCESS" if ok_x else "X: FAILED")

        # ── LinkedIn: PDF carousel for Tier 1 with real stat ───────
        if BUFFER_PROFILE_LI:
            time.sleep(3)
            pdf_posted = False
            if do_carousel and stat_number:
                print("--- Building LinkedIn PDF carousel ---")
                ts       = int(time.time())
                pdf_path = f"cards/carousel_{ts}.pdf"
                pdf_url  = f"https://raw.githubusercontent.com/{REPO}/main/{pdf_path}"

                # Build takeaway from TLW fields
                takeaway_text = (
                    f"The first sign a company has peaked isn't when competitors beat them. "
                    f"It's when their own investors start talking to the press. "
                    f"{fact3}" if fact3 else
                    f"AI is landing on your P&L right now. The question is which side of the divide you're on."
                )

                pdf_ok = generate_carousel_pdf(
                    "carousel.pdf",
                    h1=headline1, h2=headline2, hook=hook_text,
                    stat_number=stat_number, stat_label=stat_label,
                    stat_context=stat_context,
                    compare_a_label=compare_a_label, compare_a_value=compare_a_value,
                    compare_b_label=compare_b_label, compare_b_value=compare_b_value,
                    fact1=fact1, fact2=fact2, fact3=fact3,
                    takeaway=takeaway_text
                )

                if pdf_ok:
                    pushed_pdf = push_to_github("carousel.pdf", GITHUB_TOKEN, REPO, pdf_path)
                    if pushed_pdf:
                        time.sleep(5)  # Let GitHub CDN propagate
                        ok_li = post_to_buffer_document(linkedin_text, pdf_url, BUFFER_PROFILE_LI, BUFFER_API_KEY)
                        print("LinkedIn PDF carousel: SUCCESS" if ok_li else "LinkedIn PDF carousel: FAILED — falling back to single card")
                        if ok_li:
                            pdf_posted = True
                            _, current_count = load_carousel_count()
                            save_carousel_count(current_count + 1)

            if not pdf_posted:
                ok_li = post_to_buffer(linkedin_text, RAW_URL, BUFFER_PROFILE_LI, BUFFER_API_KEY, "LinkedIn")
                print("LinkedIn: SUCCESS" if ok_li else "LinkedIn: FAILED")

        # ── Instagram: PDF carousel (Tier 1) or single card ────────
        if BUFFER_PROFILE_IG:
            time.sleep(3)
            ig_posted = False
            if do_carousel and stat_number:
                print("--- Building Instagram PDF carousel ---")
                ts_ig    = int(time.time()) + 1
                pdf_ig_path = f"cards/ig_carousel_{ts_ig}.pdf"
                pdf_ig_url  = f"https://raw.githubusercontent.com/{REPO}/main/{pdf_ig_path}"
                pdf_ig_ok = generate_carousel_pdf(
                    "carousel_ig.pdf",
                    h1=headline1, h2=headline2, hook=hook_text,
                    stat_number=stat_number, stat_label=stat_label,
                    stat_context=stat_context,
                    compare_a_label=compare_a_label, compare_a_value=compare_a_value,
                    compare_b_label=compare_b_label, compare_b_value=compare_b_value,
                    fact1=fact1, fact2=fact2, fact3=fact3,
                    takeaway=f"{fact1} {fact2}".strip() or headline2
                )
                if pdf_ig_ok:
                    pushed_ig = push_to_github("carousel_ig.pdf", GITHUB_TOKEN, REPO, pdf_ig_path)
                    if pushed_ig:
                        time.sleep(5)
                        ok_ig = post_to_buffer_document(ig_caption, pdf_ig_url, BUFFER_PROFILE_IG, BUFFER_API_KEY)
                        print("Instagram PDF carousel: SUCCESS" if ok_ig else "Instagram PDF carousel: FAILED — falling back to single card")
                        if ok_ig:
                            ig_posted = True
            if not ig_posted:
                ok_ig = post_to_buffer_instagram(ig_caption, RAW_URL, BUFFER_PROFILE_IG, BUFFER_API_KEY)
                print("Instagram: SUCCESS" if ok_ig else "Instagram: FAILED")
        else:
            print("Instagram: skipped — add BUFFER_PROFILE_IG to GitHub secrets")
        # ── Mark story as used ──────────────────────────────────
        save_used_story(story_hash(STORY_TITLE))
        print(f"Story hash saved: {story_hash(STORY_TITLE)}")
    else:
        print("FAILED: GitHub push failed")
else:
    missing=[k for k,v in {"BUFFER_API_KEY":BUFFER_API_KEY,"GITHUB_TOKEN":GITHUB_TOKEN}.items() if not v]
    print(f"Missing: {', '.join(missing)}")
