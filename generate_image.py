# TLW v18.1b
# Changes from v18:
# - process_photo: no brightness pre-darkening (gradient handles fade)
# - apply_gradient: eased curve (t^0.7), no top overlay
# - card_with_photo: 160pt H1, 52pt H2, 28pt body, fixed sizes, no shrinking
# - draw_footer: 72px branded gold bar restored
# - Carousel: 20s GitHub wait, thumbnail fix, baseline estimation
# - Instagram: always single image (IG doesn't support docs)
# - Bugs fixed: thumb variable, ig_posted, indentation
import os, re, time, random, requests, base64, json
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from datetime import datetime

# ── CREDENTIALS ───────────────────────────────────────────────────
BUFFER_API_KEY    = os.environ.get("BUFFER_API_KEY", "")
BUFFER_PROFILE_X  = os.environ.get("BUFFER_PROFILE_X", "")
BUFFER_PROFILE_LI = os.environ.get("BUFFER_PROFILE_LI", "")
BUFFER_PROFILE_IG = os.environ.get("BUFFER_PROFILE_IG", "")
GITHUB_TOKEN      = os.environ.get("GITHUB_TOKEN", "")
ANTHROPIC_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
UNSPLASH_KEY      = os.environ.get("UNSPLASH_KEY", "")
PEXELS_KEY        = os.environ.get("PEXELS_KEY", "")
FAL_KEY           = os.environ.get("FAL_KEY", "")
CARD_TYPE         = os.environ.get("CARD_TYPE", "news")
WEEKLY_HEADLINES  = os.environ.get("WEEKLY_HEADLINES", "")
IMAGE_KEYWORD       = os.environ.get("IMAGE_KEYWORD", "finance technology")
CAROUSEL_MAX_DAILY  = 4
CAROUSEL_COUNT_PATH = "data/carousel_count.json"
PREVIEW_MODE      = os.environ.get("PREVIEW_MODE", "0") == "1"
FORCE_STYLE       = os.environ.get("FORCE_STYLE", "dark").lower().strip()

# ── STYLE VARIANTS ────────────────────────────────────────────────
STYLE_VARIANTS = [
    {
        "name":        "dark",
        "weight":       50,
        "flux_style":  "dark background, dramatic studio lighting, navy blue and gold color tones",
        "brightness":   0.62,
        "saturation":   0.85,
        "gradient_opacity": 1.0,
    },
    {
        "name":        "vivid",
        "weight":       30,
        "flux_style":  "vibrant colorful background, bold electric blue and emerald green tones, high contrast, bright dramatic lighting, NO dark backgrounds, bright and colourful",
        "brightness":   0.88,
        "saturation":   1.35,
        "gradient_opacity": 0.42,
    },
    {
        "name":        "warm",
        "weight":       20,
        "flux_style":  "warm rich tones, deep amber and teal color palette, bright cinematic lighting, premium editorial feel, well-lit, NOT dark",
        "brightness":   0.85,
        "saturation":   1.22,
        "gradient_opacity": 0.42,
    },
]

def pick_style():
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

ACTIVE_STYLE = pick_style()

# ── BASE64 DECODE inputs ──────────────────────────────────────────
def _decode(val):
    try:
        decoded = base64.b64decode(val).decode('utf-8')
        if decoded.isprintable() or '\n' in decoded:
            return decoded.strip()
    except Exception:
        pass
    return val.strip()

STORY_TITLE   = _decode(os.environ.get("STORY_TITLE",   ""))
STORY_SUMMARY = _decode(os.environ.get("STORY_SUMMARY", ""))
STORY_TITLE   = re.sub(r'[\x00-\x1f\x7f]', ' ', STORY_TITLE).strip()
STORY_SUMMARY = re.sub(r'[\x00-\x1f\x7f]', ' ', STORY_SUMMARY).strip()

STORY_BLOB_RAW = os.environ.get("STORY_BLOB", "")
TLW_STORY = None
if STORY_BLOB_RAW:
    try:
        TLW_STORY = json.loads(base64.b64decode(STORY_BLOB_RAW).decode('utf-8'))
        print(f"Loaded enriched story blob: {TLW_STORY.get('title','')[:50]}")
    except Exception as e:
        print(f"Could not parse STORY_BLOB: {e}")
        TLW_STORY = None

REPO       = "theledgerwire/tlw-content-engine"
IMAGE_PATH = f"cards/card_{int(time.time())}.png"
RAW_URL    = f"https://raw.githubusercontent.com/{REPO}/main/{IMAGE_PATH}"

# ── DESIGN ────────────────────────────────────────────────────────
W, H      = 1080, 1080
GOLD      = (245, 197, 24)
WHITE     = (255, 255, 255)
NAVY      = (10, 22, 40)
DGREY     = (100, 115, 148)
BODY_GREY = (190, 200, 215)
BLACK     = (20, 20, 20)
FOOTER_H  = 72

_POPPINS_BOLD = "/usr/share/fonts/truetype/poppins/Poppins-Bold.ttf"
_POPPINS_MED  = "/usr/share/fonts/truetype/poppins/Poppins-Medium.ttf"
_POPPINS_REG  = "/usr/share/fonts/truetype/poppins/Poppins-Regular.ttf"
_LIB_BOLD     = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
_LIB_REG      = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

import os as _os
FONT_BOLD = _POPPINS_BOLD if _os.path.exists(_POPPINS_BOLD) else _LIB_BOLD
FONT_MED  = _POPPINS_MED  if _os.path.exists(_POPPINS_MED)  else _LIB_BOLD
FONT_REG  = _POPPINS_REG  if _os.path.exists(_POPPINS_REG)  else _LIB_REG
print(f"Fonts: {'Poppins' if 'poppins' in FONT_BOLD else 'Liberation (fallback)'}")

# ── PHOTO SOURCES ─────────────────────────────────────────────────
PHOTO_FALLBACKS = [
    "stock market trading","wall street new york","trading floor brokers",
    "corporate skyscraper","technology server room","cryptocurrency bitcoin",
    "federal reserve building","bank building finance",
]

COUNTRY_KEYWORDS = {
    "korea":["south korea seoul skyline","korean flag city"],
    "korean":["south korea seoul skyline","korean flag city"],
    "china":["shanghai skyline night","china flag beijing"],
    "chinese":["shanghai skyline night","china flag beijing"],
    "alibaba":["shanghai skyline night","china tech office"],
    "tencent":["hong kong skyline","china tech shenzhen"],
    "baidu":["beijing china skyline","china tech office"],
    "deepseek":["china tech office","server room blue"],
    "japan":["tokyo skyline night","japan flag mount fuji"],
    "japanese":["tokyo skyline night","japan flag mount fuji"],
    "india":["mumbai skyline night","india flag"],
    "sec":["courthouse steps washington","federal building columns"],
    "lawsuit":["legal gavel courtroom","courthouse steps"],
    "trial":["legal gavel courtroom","justice scales"],
    "fed":["federal reserve building washington","us dollar bills"],
    "federal reserve":["federal reserve building washington","us dollar bills"],
    "bitcoin":["bitcoin gold coin","cryptocurrency digital"],
    "crypto":["cryptocurrency bitcoin coin","blockchain digital"],
    "ethereum":["ethereum cryptocurrency","crypto digital coins"],
    "hack":["computer hacker dark screen","keyboard code programming"],
    "leak":["computer code screen dark","keyboard programming"],
    "cyber":["cybersecurity lock digital","computer hacker"],
    "oil":["oil pipeline sunset","oil refinery night"],
    "energy":["oil refinery night","solar panels field"],
    "space":["rocket launch nasa","astronaut space earth"],
    "nasa":["rocket launch nasa","astronaut space earth"],
    "rocket":["rocket launch fire","spacex rocket"],
    "amazon":["amazon warehouse interior","amazon delivery boxes"],
    "google":["google headquarters building","tech campus"],
    "microsoft":["microsoft headquarters","windows logo tech"],
    "apple":["apple store glass","apple headquarters campus"],
    "tesla":["tesla electric car","electric vehicle charging"],
    "openai":["artificial intelligence neural","chatgpt computer screen"],
    "anthropic":["artificial intelligence claude","ai computer code"],
    "nvidia":["gpu graphics card","nvidia chip semiconductor"],
}

USED_IMAGES_PATH = "data/used_images.json"
USED_IMAGES_URL  = f"https://raw.githubusercontent.com/{REPO}/main/{USED_IMAGES_PATH}?t={int(time.time())}"
IMAGE_EXPIRY_SEC = 7 * 86400
USED_STORIES_PATH = "data/used_stories.json"

def load_used_stories():
    try:
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}","Accept": "application/vnd.github.v3+json"}
        r = requests.get(f"https://api.github.com/repos/{REPO}/contents/{USED_STORIES_PATH}", headers=headers, timeout=10)
        if r.status_code == 200:
            import base64 as _b64, json as _json
            data = _b64.b64decode(r.json()["content"]).decode("utf-8")
            return set(_json.loads(data).get("hashes", []))
    except Exception as e:
        print(f"Could not load used stories: {e}")
    return set()

def save_used_story(title_hash, title_text=""):
    try:
        import json as _json, base64 as _b64
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}","Accept": "application/vnd.github.v3+json"}
        r = requests.get(f"https://api.github.com/repos/{REPO}/contents/{USED_STORIES_PATH}", headers=headers, timeout=10)
        existing_hashes = set(); existing_titles = []; sha = None
        if r.status_code == 200:
            data = _b64.b64decode(r.json()["content"]).decode("utf-8")
            parsed = _json.loads(data)
            existing_hashes = set(parsed.get("hashes", []))
            existing_titles = parsed.get("titles", [])
            sha = r.json().get("sha")
        existing_hashes.add(title_hash)
        if title_text and title_text not in existing_titles: existing_titles.append(title_text)
        hashes_list = list(existing_hashes)[-200:]
        titles_list = existing_titles[-30:]
        content_str = _json.dumps({"hashes": hashes_list, "titles": titles_list}, indent=2)
        encoded = _b64.b64encode(content_str.encode()).decode()
        payload = {"message": "Update used stories", "content": encoded, "branch": "main"}
        if sha: payload["sha"] = sha
        requests.put(f"https://api.github.com/repos/{REPO}/contents/{USED_STORIES_PATH}", headers=headers, json=payload, timeout=15)
    except Exception as e:
        print(f"Could not save used story: {e}")

def story_hash(title):
    import hashlib
    return hashlib.md5(title.lower().strip()[:80].encode()).hexdigest()[:12]

def story_already_used(title, used_stories):
    return story_hash(title) in used_stories

def load_used_images():
    try:
        r = requests.get(USED_IMAGES_URL, timeout=10)
        if r.status_code == 200:
            data = r.json(); cutoff = time.time() - IMAGE_EXPIRY_SEC
            fresh = {url: ts for url, ts in data.items() if ts > cutoff}
            print(f"Loaded {len(fresh)} used images"); return fresh
    except Exception as e:
        print(f"Could not load used images: {e}")
    return {}

def save_used_image(img_url, used_images):
    try:
        used_images[img_url] = time.time()
        cutoff = time.time() - IMAGE_EXPIRY_SEC
        fresh = {u: t for u, t in used_images.items() if t > cutoff}
        encoded = base64.b64encode(json.dumps(fresh, indent=2).encode()).decode()
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        get_r = requests.get(f"https://api.github.com/repos/{REPO}/contents/{USED_IMAGES_PATH}", headers=headers, timeout=10)
        sha = get_r.json().get("sha") if get_r.status_code == 200 else None
        payload = {"message": "Update used images", "content": encoded, "branch": "main"}
        if sha: payload["sha"] = sha
        put_r = requests.put(f"https://api.github.com/repos/{REPO}/contents/{USED_IMAGES_PATH}", headers=headers, json=payload, timeout=15)
        print(f"Saved used image: {put_r.status_code}")
    except Exception as e:
        print(f"Could not save used image: {e}")

_sname = ACTIVE_STYLE["name"]

CAROUSEL_COUNT_URL = f"https://raw.githubusercontent.com/{REPO}/main/{CAROUSEL_COUNT_PATH}?t={int(time.time())}"

def load_carousel_count():
    try:
        r = requests.get(CAROUSEL_COUNT_URL, timeout=10)
        if r.status_code == 200:
            data = r.json(); today = datetime.now().strftime("%Y-%m-%d")
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
        if sha: payload["sha"] = sha
        put_r = requests.put(f"https://api.github.com/repos/{REPO}/contents/{CAROUSEL_COUNT_PATH}", headers=headers, json=payload, timeout=15)
        print(f"Carousel count saved ({count}): {put_r.status_code}")
    except Exception as e:
        print(f"Could not save carousel count: {e}")

def carousel_allowed():
    same_day, count = load_carousel_count()
    if not same_day: return True
    return count < CAROUSEL_MAX_DAILY

print(f"=== TLW v18.1b === CARD_TYPE: {CARD_TYPE} | Style: {_sname} | Preview: {PREVIEW_MODE} | Blob: {'YES' if TLW_STORY else 'NO'}")

def x_char_count(text):
    t = re.sub(r'https?://\S+|[\w]+\.com\S*', 'X'*23, text)
    return len(t)

def strip_urls(text):
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\S+\.com\S*', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def _build_linkedin_from_blob(blob):
    hook = blob.get("stat_hook",""); sub = blob.get("sub_headline","")
    tagline = blob.get("tagline",""); line1 = blob.get("body_line_1","")
    line2 = blob.get("body_line_2",""); title = blob.get("title",""); summary = blob.get("summary","")
    opening = f"{hook}. {sub}" if hook and sub else title
    body = f"{summary}\n\n\u2192 {line1}\n\u2192 {line2}"
    close = f"\n\n{tagline}\n\nWhat's your read?"
    return strip_urls(f"{opening}\n\n{body}{close}")

def _estimate_baseline(stat_hook):
    if not stat_hook: return "0"
    m = re.search(r'([+-]?)([\d.]+)%', stat_hook)
    if m:
        sign, val = m.group(1), float(m.group(2))
        if sign == '+': baseline = max(1, val * 0.35)
        elif sign == '-': baseline = val + 30
        else: baseline = max(1, val * 0.5)
        return f"{baseline:.0f}%"
    m = re.search(r'\$?([\d.]+)([BMKT]?)', stat_hook)
    if m:
        val, suffix = float(m.group(1)), m.group(2)
        return f"${max(0.1, val * 0.4):.1f}{suffix}"
    m = re.search(r'([\d,]+)', stat_hook)
    if m: return f"{int(float(m.group(1).replace(',','')) * 0.3):,}"
    return "0"

# ── CLAUDE: NEWS ──────────────────────────────────────────────────
def call_claude_news(title, summary):
    if not ANTHROPIC_KEY: return None
    prompt = f"""You are a content writer for The Ledger Wire \u2014 an AI and Finance newsletter for North American professionals.

Story title: {title}
Story summary: {summary}

TIER 1: AI/finance/tech/crypto/Fed/bank earnings/trade tariffs/Chinese AI companies
TIER 2: Major company earnings, M&A, layoffs, stock market moves, economic data, central banks, $50M+ funding
Reply SKIP only if: pure geopolitics/war with no market angle, sports, entertainment, food, lifestyle.
MANDATORY: CRYPTO and MARKETS stories are ALWAYS Tier 1.

Reply in this EXACT format:
TIER: [1 or 2]
TWEET: [under 220 chars, curiosity gap, end with -> theledgerwire.com #AI #Finance]
LINKEDIN: [Morning Brew style, NO URLs]
H1: [1-3 words MAX, STAT/POWER/TENSION mode]
H2: [2-4 words, company + what happened]
HOOK: [2-5 words, story-specific]
LINES: [3 short facts max 8 words each separated by |]
KEYWORD: [3-5 word SPECIFIC photo search]
STAT_NUMBER: [most impactful number]
STAT_LABEL: [3-5 words describing the stat]
STAT_CONTEXT: [one punchy sentence]
COMPARE_A_LABEL: [reference comparison label]
COMPARE_A_VALUE: [reference value]
COMPARE_B_LABEL: [hero comparison label]
COMPARE_B_VALUE: [hero value]
FACT1: [max 12 words]
FACT2: [max 12 words]
FACT3: [max 12 words]"""
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 1200, "messages": [{"role": "user", "content": prompt}]}, timeout=30)
        print(f"Claude: {r.status_code}")
        if r.status_code != 200: return None
        text = r.json()["content"][0]["text"].strip()
        print(f"Claude response:\n{text[:500]}")
        if text.strip().upper() == "SKIP": return "SKIP"
        result = {}; current_key = None; current_val = []
        for line in text.split("\n"):
            matched = False
            for key in ["TIER","TWEET","LINKEDIN","H1","H2","HOOK","LINES","KEYWORD","STAT_NUMBER","STAT_LABEL","STAT_CONTEXT","COMPARE_A_LABEL","COMPARE_A_VALUE","COMPARE_B_LABEL","COMPARE_B_VALUE","FACT1","FACT2","FACT3"]:
                if line.startswith(f"{key}:"):
                    if current_key: result[current_key] = "\n".join(current_val).strip()
                    current_key = key.lower(); current_val = [line.replace(f"{key}:","").strip()]; matched = True; break
            if not matched and current_key: current_val.append(line)
        if current_key: result[current_key] = "\n".join(current_val).strip()
        tweet = result.get("tweet", title)
        if x_char_count(tweet) > 280:
            parts = tweet.rsplit("#", 1); base = parts[0].strip(); tags = "#" + parts[1] if len(parts) > 1 else ""
            while x_char_count(f"{base}... {tags}") > 278 and len(base) > 20: base = base[:base.rfind(" ")]
            result["tweet"] = f"{base}... {tags}".strip()
        if result.get("h1") in ["Breaking Now", "", None]: return "SKIP"
        for key in ["h1","h2","hook"]:
            if key in result: result[key] = result[key].replace("**","").replace("*","").strip()
        if "linkedin" in result: result["linkedin"] = strip_urls(result["linkedin"])
        for k,v in {"tweet":title,"linkedin":title,"h1":"Breaking Now","h2":"Read Full Story","hook":"","lines":"","tier":"1","keyword":"stock market trading"}.items():
            result.setdefault(k, v)
        print(f"Tier:{result['tier']} H1:{result['h1']} H2:{result['h2']}"); return result
    except Exception as e:
        print(f"Claude exception: {e}"); return None

def call_claude_weekly(headlines, card_type):
    if not ANTHROPIC_KEY: return None
    if card_type == "weekly_tuesday":
        instruction = "Write a Tuesday market recap for The Ledger Wire. Pick 3-4 most market-moving stories. Format as witty tweet screenshot. Under 260 chars."
    else:
        instruction = "Write a Friday week-in-review for The Ledger Wire. Pick most ironic moments. Format as witty tweet screenshot. Under 260 chars."
    prompt = f"""{instruction}\n\nHeadlines:\n{headlines}\n\nReply in EXACT format:\nTWEET_SCREENSHOT: [witty recap]\nX_POST: [under 180 chars ending with -> theledgerwire.com #AI #Finance]\nLINKEDIN: [professional witty version, NO URLs]"""
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 600, "messages": [{"role": "user", "content": prompt}]}, timeout=30)
        if r.status_code != 200: return None
        text = r.json()["content"][0]["text"].strip()
        result = {}; current_key = None; current_val = []
        for line in text.split("\n"):
            matched = False
            for key in ["TWEET_SCREENSHOT","X_POST","LINKEDIN"]:
                if line.startswith(f"{key}:"):
                    if current_key: result[current_key] = "\n".join(current_val).strip()
                    current_key = key.lower(); current_val = [line.replace(f"{key}:","").strip()]; matched = True; break
            if not matched and current_key: current_val.append(line)
        if current_key: result[current_key] = "\n".join(current_val).strip()
        if "linkedin" in result: result["linkedin"] = strip_urls(result["linkedin"])
        return result
    except Exception as e:
        print(f"Claude weekly exception: {e}"); return None

# ── PHOTO PROCESSING ──────────────────────────────────────────────
def process_photo(img_data, style=None):
    from PIL import ImageEnhance
    if style is None: style = ACTIVE_STYLE
    photo = Image.open(BytesIO(img_data)).convert("RGB")
    pw, ph = photo.size; scale = max(W/pw, H/ph)
    nw, nh = int(pw*scale), int(ph*scale)
    photo = photo.resize((nw, nh), Image.LANCZOS)
    left, top = (nw-W)//2, (nh-H)//2
    photo = photo.crop((left, top, left+W, top+H))
    photo = ImageEnhance.Color(photo).enhance(min(style["saturation"], 1.05))
    return photo

def fetch_pexels(keyword, used_images):
    if not PEXELS_KEY: return None, None
    try:
        r = requests.get("https://api.pexels.com/v1/search", params={"query": keyword, "per_page": 15, "orientation": "square"}, headers={"Authorization": PEXELS_KEY}, timeout=15)
        if r.status_code != 200: return None, None
        photos = r.json().get("photos", [])
        if not photos: return None, None
        random.shuffle(photos)
        for p in photos:
            img_url = p["src"]["large"]
            if img_url in used_images: continue
            img_data = requests.get(img_url, timeout=15).content
            return process_photo(img_data), img_url
        return None, None
    except Exception as e:
        print(f"Pexels exception [{keyword}]: {e}"); return None, None

def fetch_unsplash(keyword, used_images):
    if not UNSPLASH_KEY: return None, None
    try:
        r = requests.get("https://api.unsplash.com/search/photos", params={"query": keyword, "per_page": 15, "orientation": "squarish", "order_by": "relevant"}, headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"}, timeout=15)
        if r.status_code != 200: return None, None
        results = r.json().get("results", [])
        if not results: return None, None
        random.shuffle(results)
        for p in results:
            img_url = p["urls"]["regular"]
            if img_url in used_images: continue
            img_data = requests.get(img_url, timeout=15).content
            return process_photo(img_data), img_url
        return None, None
    except Exception as e:
        print(f"Unsplash exception [{keyword}]: {e}"); return None, None

def get_country_keywords(keyword, story_context=""):
    combined = f"{keyword} {story_context}".lower()
    for trigger, replacements in COUNTRY_KEYWORDS.items():
        if trigger in combined: return replacements
    return []

def generate_flux_prompt(title, summary, style=None):
    if style is None: style = ACTIVE_STYLE
    if TLW_STORY and TLW_STORY.get("image_angle"):
        angle = TLW_STORY["image_angle"]
        print(f"Using pre-written image_angle: {angle[:80]}...")
        return f"{angle}, {style['flux_style']}"
    if not ANTHROPIC_KEY: return None
    try:
        prompt = f"""You are an AI image director for The Ledger Wire. Story: {title} Summary: {summary}
Generate an image prompt. RULES: Match story literally. Style: {style["flux_style"]}. NO text/logos/faces/people. Editorial photography. Max 25 words."""
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 100, "messages": [{"role": "user", "content": prompt}]}, timeout=30)
        if r.status_code == 200:
            img_prompt = r.json()["content"][0]["text"].strip().strip('"')
            print(f"Generated prompt: {img_prompt}"); return img_prompt
    except Exception as e:
        print(f"Prompt generation error: {e}")
    return None

def fetch_flux_image(img_prompt):
    if not FAL_KEY or not img_prompt: return None, None
    full_prompt = f"{img_prompt}, cinematic editorial photograph, deep navy and gold color palette, photorealistic, financial magazine style, dramatic lighting, no text, no logos, no watermarks"
    try:
        r = requests.post("https://fal.run/xai/grok-imagine-image", headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
            json={"prompt": full_prompt, "image_size": "square_hd", "num_images": 1}, timeout=60)
        print(f"Grok Imagine: {r.status_code}")
        if r.status_code == 200:
            img_url = r.json()["images"][0]["url"]
            img_data = requests.get(img_url, timeout=30).content
            return process_photo(img_data), img_url
        else: print(f"Grok error: {r.text[:200]} \u2014 falling back to Flux.1 Pro")
    except Exception as e:
        print(f"Grok exception: {e} \u2014 falling back to Flux.1 Pro")
    try:
        r2 = requests.post("https://fal.run/fal-ai/flux-pro/v1.1", headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
            json={"prompt": full_prompt, "image_size": "square_hd", "num_inference_steps": 28, "guidance_scale": 3.5, "num_images": 1, "safety_tolerance": "2"}, timeout=60)
        if r2.status_code == 200:
            img_url = r2.json()["images"][0]["url"]
            img_data = requests.get(img_url, timeout=30).content
            return process_photo(img_data), img_url
    except Exception as e:
        print(f"Flux exception: {e}")
    return None, None

def get_photo(keyword, story_context="", used_images=None):
    if used_images is None: used_images = {}
    if FAL_KEY:
        print("--- Trying AI image generation ---")
        flux_prompt = generate_flux_prompt(story_context or keyword, story_context, style=ACTIVE_STYLE)
        photo, img_url = fetch_flux_image(flux_prompt)
        if photo: print("AI image success"); return photo, img_url
        print("AI image failed \u2014 trying Pexels")
    country_kws = get_country_keywords(keyword, story_context)
    keywords_to_try = [keyword] + country_kws + PHOTO_FALLBACKS
    for kw in keywords_to_try:
        photo, img_url = fetch_pexels(kw, used_images)
        if photo: return photo, img_url
    for kw in keywords_to_try:
        photo, img_url = fetch_unsplash(kw, used_images)
        if photo: return photo, img_url
    print("--- All photo sources failed \u2014 navy card ---"); return None, None

# ── GRADIENT ──────────────────────────────────────────────────────
def apply_gradient(img, start=0.40, style=None):
    if style is None: style = ACTIVE_STYLE
    op = style["gradient_opacity"]
    overlay_rgb = (10, 22, 40)
    grad = Image.new("RGBA",(W,H),(0,0,0,0)); gd = ImageDraw.Draw(grad)
    for y in range(int(H * start), H):
        t = float(y - H * start) / float(H * (1 - start))
        t = max(0.0, min(1.0, t))
        a = int(255 * min(1.0, t ** 0.7) * op)
        gd.line([(0, y), (W, y)], fill=(*overlay_rgb, a))
    return Image.alpha_composite(img.convert("RGBA"), grad).convert("RGB")

def wrap_text(draw, text, font, max_width):
    words = text.split(); lines = []; current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0,0), test, font=font)[2] <= max_width: current = test
        else:
            if current: lines.append(current)
            current = word
    if current: lines.append(current)
    return lines

def draw_footer(draw):
    PAD = 56
    draw.rectangle([(0, H-72), (W, H)], fill=GOLD)
    url_f = ImageFont.truetype(FONT_BOLD, 19)
    tag_f = ImageFont.truetype(FONT_REG, 19)
    btb = draw.textbbox((0,0), "THE LEDGER WIRE", font=url_f)
    utb = draw.textbbox((0,0), "theledgerwire.com", font=tag_f)
    uw = utb[2] - utb[0]
    fy = H - 72 + (72 - btb[3]) // 2
    draw.text((PAD, fy), "THE LEDGER WIRE", font=url_f, fill=NAVY)
    draw.text((W - PAD - uw, fy), "theledgerwire.com", font=tag_f, fill=NAVY)

def draw_text_shadow(draw, pos, text, font, fill, shadow_color=(0,0,0), offset=3, blur_passes=2):
    x, y = pos
    draw.text((x+2, y+2), text, font=font, fill=(0,0,0))
    draw.text((x, y), text, font=font, fill=fill)

KNOWN_COMPANIES = ["OpenAI","Anthropic","Google","Microsoft","Apple","Amazon","Meta","Nvidia","Tesla","Oracle","Samsung","Intel","AMD","TSMC","Qualcomm","IBM","Salesforce","JPMorgan","Goldman Sachs","Goldman","BlackRock","Citigroup","Morgan Stanley","Wells Fargo","Bank of America","HSBC","Barclays","Coinbase","Binance","Bitcoin","Ethereum","Robinhood","PayPal","Stripe","SpaceX","Uber","Airbnb","Netflix","Spotify","TikTok","ByteDance","Alibaba","Tencent","Baidu","Huawei","SoftBank","Arm","ASML","Palantir","Snowflake","Databricks","Mistral","xAI","DeepMind","LinkedIn","Reddit","Shopify","Zoom","Slack","Adobe","Canva","Boeing","Lockheed","Pfizer","Moderna","Federal Reserve","Fed","SEC","FTC","OPEC"]
NOT_COMPANIES = {"vietnam","china","india","japan","korea","russia","ukraine","iran","israel","france","germany","spain","italy","europe","asia","africa","america","big","tech","market","retail","traders","bank","banks","house","white","new","the","this","that","its","their","global","world","local","government","ministry","congress","senate","president","minister"}

def extract_company(h2, story_title=""):
    text = f"{h2} {story_title}"
    for co in sorted(KNOWN_COMPANIES, key=len, reverse=True):
        if co.lower() in text.lower(): return co.upper()
    m = re.match(r"([A-Z][A-Za-z&]+)", h2.strip())
    if m:
        word = m.group(1).rstrip(".,")
        if len(word) >= 3 and word.lower() not in NOT_COMPANIES: return word.upper()
    return None

def get_source_label(story_title=""):
    if TLW_STORY and TLW_STORY.get("source_tag"): return TLW_STORY["source_tag"]
    t = story_title.lower()
    if "bloomberg" in t: return "Bloomberg"
    if "reuters" in t: return "Reuters"
    if "wsj" in t or "wall street" in t: return "WSJ"
    if "techcrunch" in t: return "TechCrunch"
    if "ft" in t or "financial times" in t: return "FT"
    if "coindesk" in t: return "CoinDesk"
    if "marketwatch" in t: return "MarketWatch"
    return ""

# ── CARD: PHOTO ───────────────────────────────────────────────────
def card_with_photo(img, h1, h2, hook="", company_name=None, source="", support_lines=None):
    """v18.1b: 160pt H1 (1 line), 52pt H2 (2 lines), 28pt body. Fixed sizes."""
    draw = ImageDraw.Draw(img)
    PAD, MTW, FTR_H = 50, W - 50 - 40, 72
    mark_f = ImageFont.truetype(FONT_BOLD, 22)
    badge_f = ImageFont.truetype(FONT_BOLD, 18)
    h1_f = ImageFont.truetype(FONT_BOLD, 160)
    h2_f = ImageFont.truetype(FONT_MED, 52)
    body_f = ImageFont.truetype(FONT_MED, 28)

    draw.rectangle([(0, 0), (10, H)], fill=GOLD)
    draw_text_shadow(draw, (40, 34), "THE LEDGER WIRE", mark_f, WHITE, offset=2)
    mb = draw.textbbox((40, 34), "THE LEDGER WIRE", font=mark_f)
    mark_w = mb[2] - mb[0]
    draw.rectangle([(40, mb[3]+4), (40+mark_w, mb[3]+7)], fill=GOLD)

    if source:
        spx, spy = 14, 6
        sb = draw.textbbox((0,0), source, font=badge_f)
        stw, sth = sb[2]-sb[0], sb[3]-sb[1]
        bw2, bh2 = stw+spx*2, sth+spy*2+8
        bx2, by2 = W-40-bw2, 28
        draw.rounded_rectangle([(bx2,by2),(bx2+bw2,by2+bh2)], radius=4, outline=GOLD, width=2)
        draw.text((bx2+spx, by2+spy+1), source, font=badge_f, fill=GOLD)

    h1_tw = draw.textbbox((0,0), h1, font=h1_f)[2]
    if h1_tw > MTW: h1_f = ImageFont.truetype(FONT_BOLD, 130)

    h1_lines = wrap_text(draw, h1, h1_f, MTW)
    h2_lines = wrap_text(draw, h2, h2_f, MTW)
    body_texts = support_lines[:2] if support_lines else []
    h1_lh = draw.textbbox((0,0), "Ag", font=h1_f)[3]
    h2_lh = draw.textbbox((0,0), "Ag", font=h2_f)[3]
    bd_lh = draw.textbbox((0,0), "Ag", font=body_f)[3]

    footer_top = H - FTR_H
    body_block_h = len(body_texts) * (bd_lh + 10) if body_texts else 0
    body_y = footer_top - 28 - body_block_h
    rule_y = body_y - 22
    h2_block_h = min(len(h2_lines), 2) * (h2_lh + 4)
    h2_y = rule_y - 6 - h2_block_h
    h1_block_h = min(len(h1_lines), 1) * (h1_lh + 4)
    h1_y = h2_y - 0 - h1_block_h

    y = h1_y
    for line in h1_lines[:1]:
        draw_text_shadow(draw, (PAD, y), line, h1_f, GOLD, offset=3); y += h1_lh + 4
    y = h2_y
    for line in h2_lines[:2]:
        draw_text_shadow(draw, (PAD, y), line, h2_f, WHITE, offset=3); y += h2_lh + 4
    draw.rectangle([(PAD, rule_y), (PAD+90, rule_y+4)], fill=GOLD)
    y = body_y
    for line in body_texts:
        draw_text_shadow(draw, (PAD, y), line, body_f, BODY_GREY, offset=2); y += bd_lh + 10
    draw_footer(draw)
    img.save("card.png", "PNG")
    print("Card saved (photo mode \u2014 v18.1b)")

# ── CARD: NAVY ────────────────────────────────────────────────────
def card_no_photo(h1, h2, support_lines=None, hook=""):
    img = Image.new("RGB",(W,H),NAVY); draw = ImageDraw.Draw(img)
    for y_px in range(H):
        t = y_px/H; draw.line([(0,y_px),(W,y_px)], fill=(int(10+15*t),int(22+18*t),int(40+28*t)))
    gi = Image.new("RGBA",(W,H),(0,0,0,0)); gd = ImageDraw.Draw(gi)
    for x in range(0,W,54): gd.line([(x,0),(x,H-72)], fill=(255,255,255,10))
    for y_px in range(0,H-72,54): gd.line([(0,y_px),(W,y_px)], fill=(255,255,255,10))
    img = Image.alpha_composite(img.convert("RGBA"),gi).convert("RGB"); draw = ImageDraw.Draw(img)
    PAD, MTW = 86, W-86-40
    draw.rectangle([(0,0),(6,H-72)], fill=GOLD)
    logo_f = ImageFont.truetype(FONT_BOLD,18)
    lb = draw.textbbox((0,0),"THE LEDGER WIRE",font=logo_f)
    draw.text((PAD,52),"THE LEDGER WIRE",font=logo_f,fill=WHITE)
    draw.rectangle([(PAD,74),(PAD+lb[2]-lb[0],77)],fill=GOLD)
    h1_f = ImageFont.truetype(FONT_BOLD,120); h1_lines = wrap_text(draw,h1,h1_f,MTW)
    h1_lh = draw.textbbox((0,0),"Ag",font=h1_f)[3]; y = 110
    for line in h1_lines: draw.text((PAD,y),line,font=h1_f,fill=GOLD); y+=h1_lh+4
    h2_f = ImageFont.truetype(FONT_BOLD,52); h2_lines = wrap_text(draw,h2,h2_f,MTW)
    h2_lh = draw.textbbox((0,0),"Ag",font=h2_f)[3]; y+=16
    for line in h2_lines: draw.text((PAD,y),line,font=h2_f,fill=WHITE); y+=h2_lh+4
    y+=20; draw.rectangle([(PAD,y),(PAD+200,y+5)],fill=GOLD); y+=32
    if support_lines:
        lf = ImageFont.truetype(FONT_REG,28); llh = draw.textbbox((0,0),"Ag",font=lf)[3]
        for lt in support_lines:
            if y+llh>H-72-160: break
            draw.rectangle([(PAD,y+6),(PAD+4,y+llh-6)],fill=GOLD)
            draw.text((PAD+18,y),lt.strip(),font=lf,fill=WHITE); y+=llh+16
    if hook:
        hf = ImageFont.truetype(FONT_BOLD,48); hlh = draw.textbbox((0,0),"Ag",font=hf)[3]
        parts = [p.strip() for p in hook.split(".") if p.strip()]; hy = H-72-110
        for i,part in enumerate(parts): draw.text((PAD,hy),part+".",font=hf,fill=WHITE if i%2==0 else GOLD); hy+=hlh+4
    sf = ImageFont.truetype(FONT_REG,22); draw.text((PAD,H-72-36),"theledgerwire.com",font=sf,fill=DGREY)
    draw_footer(draw); img.save("card.png","PNG"); print("Card saved (navy fallback)")

# ── CARD: TWEET SCREENSHOT ────────────────────────────────────────
def card_tweet_screenshot(tweet_text, label="THIS WEEK"):
    img = Image.new("RGB",(W,H),(10,22,40)); draw = ImageDraw.Draw(img)
    for y_px in range(H//2):
        t=1-(y_px/(H//2)); draw.line([(0,y_px),(W,y_px)],fill=(int(245*t+10*(1-t)),int(197*t+22*(1-t)),int(24*t+40*(1-t))))
    for y_px in range(H//2,H):
        t=(y_px-H//2)/(H//2); draw.line([(0,y_px),(W,y_px)],fill=(int(10+5*t),int(22+8*t),int(40+10*t)))
    CX,CY,CW,CH=72,120,W-144,660
    draw.rounded_rectangle([(CX,CY),(CX+CW,CY+CH)],radius=24,fill=WHITE)
    LX,LY,LR=CX+40,CY+44,36; draw.ellipse([(LX,LY),(LX+LR*2,LY+LR*2)],fill=NAVY)
    sf=ImageFont.truetype(FONT_BOLD,11)
    draw.text((LX+8,LY+8),"The",font=sf,fill=GOLD); draw.text((LX+4,LY+22),"Ledger",font=sf,fill=WHITE); draw.text((LX+8,LY+36),"Wire",font=sf,fill=GOLD)
    nf=ImageFont.truetype(FONT_BOLD,26); hf2=ImageFont.truetype(FONT_REG,22)
    draw.text((LX+LR*2+20,CY+50),"The Ledger Wire",font=nf,fill=BLACK)
    draw.text((LX+LR*2+20,CY+82),"@LedgerWire",font=hf2,fill=(100,100,100))
    draw.line([(CX+40,CY+128),(CX+CW-40,CY+128)],fill=(220,220,220),width=1)
    tf=ImageFont.truetype(FONT_REG,30); tbf=ImageFont.truetype(FONT_BOLD,30); MTW2=CW-80
    lines=tweet_text.split("\n"); ty=CY+148; line_h=draw.textbbox((0,0),"Ag",font=tf)[3]+10
    for i,line in enumerate(lines):
        if not line.strip(): ty+=line_h//2; continue
        font=tbf if i==0 else tf
        for wl in wrap_text(draw,line,font,MTW2):
            if ty>CY+CH-120: break
            draw.text((CX+40,ty),wl,font=font,fill=BLACK); ty+=line_h
    tif=ImageFont.truetype(FONT_REG,20); ts=datetime.now().strftime("%-I:%M %p \u00b7 %b %-d, %Y")
    draw.text((CX+40,CY+CH-80),ts,font=tif,fill=(100,100,100))
    draw.line([(CX+40,CY+CH-52),(CX+CW-40,CY+CH-52)],fill=(220,220,220),width=1)
    stbf=ImageFont.truetype(FONT_BOLD,20); strf=ImageFont.truetype(FONT_REG,20); sx,sy=CX+40,CY+CH-36
    for bold_t,reg_t in [("344"," Replies"),("1.2K"," Reposts"),("6.7K"," Likes")]:
        draw.text((sx,sy),bold_t,font=stbf,fill=BLACK); bw=draw.textbbox((0,0),bold_t,font=stbf)[2]
        draw.text((sx+bw,sy),reg_t,font=strf,fill=(100,100,100)); rw=draw.textbbox((0,0),reg_t,font=strf)[2]; sx+=bw+rw+40
    lbf=ImageFont.truetype(FONT_BOLD,22); ubf=ImageFont.truetype(FONT_REG,22)
    draw.text((72,CY+CH+28),label,font=lbf,fill=GOLD)
    utb=draw.textbbox((0,0),"theledgerwire.com",font=ubf)
    draw.text((W-72-(utb[2]-utb[0]),CY+CH+28),"theledgerwire.com",font=ubf,fill=WHITE)
    img.save("card.png","PNG"); print("Card saved (tweet screenshot)")

# ── PDF CAROUSEL ──────────────────────────────────────────────────
def generate_carousel_pdf(output_path, h1, h2, hook, stat_number, stat_label, stat_context, compare_a_label, compare_a_value, compare_b_label, compare_b_value, fact1, fact2, fact3, takeaway):
    try:
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.colors import HexColor, white
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        print("ERROR: reportlab not installed"); return False
    _W=_H=1080; _NAVY=HexColor('#0A1628'); _GOLD=HexColor('#F5C518'); _UABLUE=HexColor('#3A65B9')
    _PURPLE=HexColor('#534AB7'); _TEAL=HexColor('#1D9E75'); _WHITE=white; _MGREY=HexColor('#999999'); _DGREY=HexColor('#333333')
    _BOLD="/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"; _REG="/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
    try: pdfmetrics.registerFont(TTFont('TLW-Bold',_BOLD)); pdfmetrics.registerFont(TTFont('TLW-Reg',_REG))
    except: pass
    def _wrap(text, wc):
        words=text.split(); lines=[]; line=""
        for w in words:
            test=(line+" "+w).strip()
            if len(test)<=wc: line=test
            else:
                if line: lines.append(line)
                line=w
        if line: lines.append(line)
        return lines
    def _footer(c,sn,total=5):
        c.setFillColor(_GOLD); c.rect(0,0,_W,56,fill=1,stroke=0)
        c.setFillColor(_NAVY); c.setFont('TLW-Bold',18); c.drawString(40,18,"THE LEDGER WIRE")
        c.setFont('TLW-Reg',16); c.drawRightString(_W-40,18,"theledgerwire.com")
    c=rl_canvas.Canvas(output_path,pagesize=(_W,_H))
    # Slide 1
    c.setFillColor(_NAVY); c.rect(0,0,_W,_H,fill=1,stroke=0)
    c.setFillColor(_GOLD); c.rect(0,56,8,_H-56,fill=1,stroke=0)
    c.setFont('TLW-Bold',20); c.drawString(52,_H-52,"THE LEDGER WIRE")
    c.setFillColor(HexColor('#8892A4')); c.setFont('TLW-Reg',14); c.drawString(52,_H-76,"AI & FINANCE \u00b7 DECODED")
    c.setFillColor(_GOLD); c.rect(52,_H-104,60,3,fill=1,stroke=0)
    c.setFont('TLW-Bold',130); sw=c.stringWidth(stat_number,'TLW-Bold',130); fs=90 if sw>_W-104 else 130
    c.setFont('TLW-Bold',fs); c.drawString(52,_H-290,stat_number)
    c.setFillColor(_WHITE); c.setFont('TLW-Bold',52); y=_H-360
    for line in _wrap(h1,22)[:3]: c.drawString(52,y,line); y-=62
    c.setFillColor(_GOLD); c.setFont('TLW-Bold',36)
    for line in _wrap(h2,30)[:2]: c.drawString(52,y,line); y-=44
    if hook: c.setFillColor(_WHITE); c.setFont('TLW-Bold',30); c.drawString(52,y-14,hook)
    c.setFillColor(HexColor('#8892A4')); c.setFont('TLW-Reg',18); c.drawRightString(_W-40,72,"Swipe for the data \u2192")
    _footer(c,0); c.showPage()
    # Slide 2
    c.setFillColor(_WHITE); c.rect(0,0,_W,_H,fill=1,stroke=0)
    c.setFillColor(_UABLUE); c.rect(0,_H-18,_W,18,fill=1,stroke=0)
    c.setFillColor(_GOLD); c.rect(0,_H-32,_W,14,fill=1,stroke=0)
    c.setFillColor(_UABLUE); c.rect(0,0,_W,56,fill=1,stroke=0)
    c.setFont('TLW-Bold',20); c.drawString(52,_H-66,"THE LEDGER WIRE")
    c.setFillColor(_MGREY); c.setFont('TLW-Reg',14); c.drawString(52,_H-86,"BY THE NUMBERS")
    c.setFillColor(_NAVY); c.setFont('TLW-Bold',54); y=_H-148
    for line in _wrap(stat_label.upper(),20)[:2]: c.drawString(52,y,line); y-=64
    c.setFillColor(_MGREY); c.setFont('TLW-Reg',17); c.drawString(52,y-8,f"SOURCE: THE LEDGER WIRE  \u00b7  {stat_context[:32].upper()}"); y-=52
    def _pval(v):
        v=str(v).replace(',','').replace('$','').replace('%',''); m=re.search(r'[\d.]+([BMK])?',v,re.I)
        if not m: return 1.0
        n=float(m.group(0).rstrip('BMKbmk')); suf=(m.group(1) or '').upper()
        if suf=='B': n*=1000
        return max(n,0.01)
    va=_pval(compare_a_value); vb=_pval(compare_b_value); mv=max(va,vb)*1.18
    cl=100; cr=_W-60; cw=cr-cl; cbot=140; ctop=y-20; ch=ctop-cbot
    c.setStrokeColor(HexColor('#E5E5E5')); c.setLineWidth(0.8); c.setFillColor(_MGREY); c.setFont('TLW-Reg',15)
    for pct in [0,25,50,75,100]: gy=cbot+int(ch*pct/100); c.line(cl,gy,cr,gy); c.drawRightString(cl-8,gy-5,f"{int(mv*pct/100)}B")
    gw=cw//2; bw=int(gw*0.52); bcols=[_GOLD,_UABLUE]; vcols=[HexColor('#A07800'),_UABLUE]
    vals=[va,vb]; lbls=[compare_a_label or "Before",compare_b_label or "Now"]; raws=[compare_a_value,compare_b_value]
    for i,(val,bc,vc,lbl,raw) in enumerate(zip(vals,bcols,vcols,lbls,raws)):
        bx=cl+i*gw+(gw-bw)//2; bh2=int(ch*min(val/mv,1.0))
        c.setFillColor(bc); c.rect(bx,cbot,bw,bh2,fill=1,stroke=0)
        c.setFillColor(vc); c.setFont('TLW-Bold',24); c.drawCentredString(bx+bw/2,cbot+bh2+10,raw)
        c.setFillColor(_NAVY); c.setFont('TLW-Bold',18); c.drawCentredString(bx+bw/2,cbot-26,lbl)
    c.setFillColor(_UABLUE); c.setFont('TLW-Bold',38); c.drawString(52,66,stat_number)
    _footer(c,1); c.showPage()
    # Slide 3
    c.setFillColor(_WHITE); c.rect(0,0,_W,_H,fill=1,stroke=0)
    c.setFillColor(_GOLD); c.rect(0,56,10,_H-56,fill=1,stroke=0)
    c.setFont('TLW-Bold',20); c.drawString(52,_H-52,"THE LEDGER WIRE")
    c.setFillColor(_MGREY); c.setFont('TLW-Reg',14); c.drawString(52,_H-76,"WHY IT MATTERS")
    c.setFillColor(_NAVY); c.setFont('TLW-Bold',42); y=_H-148
    for line in _wrap(f"{h1} \u2014 {h2}",26)[:2]: c.drawString(52,y,line); y-=52
    c.setFillColor(_GOLD); c.rect(52,y-10,140,4,fill=1,stroke=0); y-=52
    fact_cols=[_GOLD,_PURPLE,_TEAL]; facts=[f for f in [fact1,fact2,fact3] if f]; c.setFont('TLW-Reg',28)
    for fact,col in zip(facts[:3],fact_cols):
        c.setFillColor(col); c.rect(52,y+4,7,28,fill=1,stroke=0); c.setFillColor(_DGREY)
        for fl in _wrap(fact,40)[:2]: c.drawString(76,y,fl); y-=34
        y-=42
    _footer(c,2); c.save()
    print(f"PDF carousel saved: {output_path}"); return True

# ── GENERATE CARD ─────────────────────────────────────────────────
def generate_news_card(h1,h2,keyword,support_lines=None,hook="",story_context="",used_images=None,story_title="",story_summary=""):
    if used_images is None: used_images={}
    company = extract_company(h2, story_title); source = get_source_label(story_title)
    photo, img_url = get_photo(keyword, story_context, used_images)
    if photo: card_with_photo(apply_gradient(photo), h1, h2, hook, company_name=company, source=source, support_lines=support_lines)
    else: card_no_photo(h1,h2,support_lines,hook); img_url=None
    return "card.png", img_url

# ── GITHUB ────────────────────────────────────────────────────────
def push_to_github(image_path, token, repo, file_path):
    print(f"Pushing to GitHub: {file_path}")
    with open(image_path,"rb") as f: content=base64.b64encode(f.read()).decode("utf-8")
    headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github.v3+json"}
    get_r=requests.get(f"https://api.github.com/repos/{repo}/contents/{file_path}",headers=headers)
    sha=get_r.json().get("sha") if get_r.status_code==200 else None
    payload={"message":"Add card image","content":content,"branch":"main"}
    if sha: payload["sha"]=sha
    put_r=requests.put(f"https://api.github.com/repos/{repo}/contents/{file_path}",headers=headers,json=payload,timeout=30)
    print(f"GitHub push: {put_r.status_code}"); return put_r.status_code in [200,201]

# ── BUFFER ────────────────────────────────────────────────────────
def post_to_buffer_carousel(post_text, image_urls, channel_id, api_key, platform="", retries=2):
    print(f"Posting carousel to Buffer {platform} ({len(image_urls)} slides)...")
    time.sleep(3)
    def esc(s): return s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','')
    safe_text = esc(post_text); cid = channel_id.strip()
    imgs_gql = ", ".join([f'{{ url: "{u}" }}' for u in image_urls])
    query = ('mutation CreatePost {\n  createPost(input: {\n    text: "%s",\n    channelId: "%s",\n    schedulingType: automatic,\n    mode: addToQueue,\n    assets: { images: [%s] }\n  }) {\n    ... on PostActionSuccess { post { id text } }\n    ... on MutationError { message }\n  }\n}') % (safe_text, cid, imgs_gql)
    for attempt in range(retries + 1):
        try:
            r = requests.post("https://api.buffer.com", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"query": query}, timeout=30)
            data = r.json(); post_data = data.get("data",{}).get("createPost",{})
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

def post_to_buffer_document(post_text, doc_url, channel_id, api_key, thumbnail_url=None, retries=2):
    print(f"Posting LinkedIn PDF document...")
    time.sleep(3)
    def esc(s): return s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','')
    safe_text = esc(post_text); cid = channel_id.strip()
    thumb = thumbnail_url or doc_url
    query = ('mutation CreatePost {\n  createPost(input: {\n    text: "%s",\n    channelId: "%s",\n    schedulingType: automatic,\n    mode: addToQueue,\n    assets: { documents: [{ url: "%s", title: "The Ledger Wire", thumbnailUrl: "%s" }] }\n  }) {\n    ... on PostActionSuccess { post { id text } }\n    ... on MutationError { message }\n  }\n}') % (safe_text, cid, doc_url, thumb)
    for attempt in range(retries + 1):
        try:
            r = requests.post("https://api.buffer.com", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"query": query}, timeout=30)
            data = r.json(); post_data = data.get("data",{}).get("createPost",{})
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
    print(f"Posting to Buffer Instagram..."); time.sleep(3)
    def esc(s): return s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','')
    safe_text = esc(post_text); cid = channel_id.strip()
    query = 'mutation CreatePost {\n  createPost(input: {\n    text: "%s",\n    channelId: "%s",\n    schedulingType: reminder,\n    mode: addToQueue,\n    assets: { images: [{ url: "%s" }] }\n  }) {\n    ... on PostActionSuccess { post { id text } }\n    ... on MutationError { message }\n  }\n}' % (safe_text, cid, image_url)
    for attempt in range(retries + 1):
        try:
            r = requests.post("https://api.buffer.com", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"query": query}, timeout=30)
            data = r.json(); post_data = data.get("data",{}).get("createPost",{})
            if "errors" in data:
                if attempt < retries: time.sleep(5); continue
                return False
            if "message" in post_data and "post" not in post_data:
                if attempt < retries: time.sleep(5); continue
                return False
            if post_data.get("post",{}).get("id"): return True
            return False
        except Exception as e:
            print(f"Buffer Instagram exception: {e}")
            if attempt < retries: time.sleep(5)
    return False

def post_to_buffer(post_text, image_url, channel_id, api_key, platform="", retries=2):
    print(f"Posting to Buffer {platform}..."); time.sleep(3)
    def esc(s): return s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','')
    safe_text = esc(post_text); cid = channel_id.strip()
    query = 'mutation CreatePost {\n  createPost(input: {\n    text: "%s",\n    channelId: "%s",\n    schedulingType: automatic,\n    mode: addToQueue,\n    assets: { images: [{ url: "%s" }] }\n  }) {\n    ... on PostActionSuccess { post { id text } }\n    ... on MutationError { message }\n  }\n}' % (safe_text, cid, image_url)
    for attempt in range(retries+1):
        try:
            r = requests.post("https://api.buffer.com", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"query": query}, timeout=30)
            data = r.json(); post_data = data.get("data",{}).get("createPost",{})
            if "errors" in data:
                if attempt < retries: time.sleep(5); continue
                return False
            if "message" in post_data and "post" not in post_data:
                if attempt < retries: time.sleep(5); continue
                return False
            return r.status_code == 200
        except Exception as e:
            print(f"Buffer {platform} exception: {e}")
            if attempt < retries: time.sleep(5)
    return False

# ── WEEKLY FLOW ───────────────────────────────────────────────────
if CARD_TYPE in ["weekly_tuesday","weekly_friday"]:
    if not WEEKLY_HEADLINES: print("No weekly headlines \u2014 exiting"); exit(0)
    label = "THIS WEEK" if CARD_TYPE=="weekly_friday" else "THIS MONDAY"
    weekly_result = call_claude_weekly(WEEKLY_HEADLINES, CARD_TYPE)
    if not weekly_result: print("Claude weekly failed \u2014 exiting"); exit(0)
    tweet_screenshot = weekly_result.get("tweet_screenshot","")
    x_post = weekly_result.get("x_post",""); linkedin_text = weekly_result.get("linkedin","")
    if not tweet_screenshot: print("No screenshot text \u2014 exiting"); exit(0)
    card_tweet_screenshot(tweet_screenshot, label)
    if BUFFER_API_KEY and GITHUB_TOKEN:
        pushed = push_to_github("card.png", GITHUB_TOKEN, REPO, IMAGE_PATH)
        if pushed:
            time.sleep(5)
            if BUFFER_PROFILE_X and x_post: post_to_buffer(x_post, RAW_URL, BUFFER_PROFILE_X, BUFFER_API_KEY, "X")
            if BUFFER_PROFILE_LI and linkedin_text: time.sleep(3); post_to_buffer(linkedin_text, RAW_URL, BUFFER_PROFILE_LI, BUFFER_API_KEY, "LinkedIn")
            if BUFFER_PROFILE_IG: time.sleep(3); post_to_buffer_instagram(linkedin_text, RAW_URL, BUFFER_PROFILE_IG, BUFFER_API_KEY)
    exit(0)

# ── NEWS FLOW ─────────────────────────────────────────────────────
if not STORY_TITLE: print("No story title \u2014 exiting"); exit(0)
used_stories = load_used_stories()
if story_already_used(STORY_TITLE, used_stories):
    print(f"DUPLICATE: Story already processed \u2014 skipping: {STORY_TITLE[:60]}"); exit(0)

if TLW_STORY:
    print("Using enriched TLW story blob (skipping call_claude_news)")
    claude_result = {
        "tier": str(TLW_STORY.get("tier", 1)),
        "tweet": f"{TLW_STORY.get('stat_hook','')} \u2014 {TLW_STORY.get('sub_headline','')} {TLW_STORY.get('tagline','')}  theledgerwire.com  #AI #Finance".strip(),
        "linkedin": _build_linkedin_from_blob(TLW_STORY),
        "h1": TLW_STORY.get("stat_hook", STORY_TITLE[:20]),
        "h2": TLW_STORY.get("sub_headline", "Read Full Story"),
        "hook": TLW_STORY.get("tagline", ""),
        "lines": f"{TLW_STORY.get('body_line_1','')}|{TLW_STORY.get('body_line_2','')}",
        "keyword": TLW_STORY.get("keyword_fallback", "finance technology"),
        "stat_number": TLW_STORY.get("stat_hook", ""),
        "stat_label": TLW_STORY.get("sub_headline", ""),
        "stat_context": TLW_STORY.get("body_line_1", ""),
        "compare_a_label": TLW_STORY.get("compare_a_label", "Before"),
        "compare_a_value": TLW_STORY.get("compare_a_value", _estimate_baseline(TLW_STORY.get("stat_hook", ""))),
        "compare_b_label": TLW_STORY.get("compare_b_label", "Now"),
        "compare_b_value": TLW_STORY.get("stat_hook", ""),
        "fact1": TLW_STORY.get("body_line_1", ""),
        "fact2": TLW_STORY.get("body_line_2", ""),
        "fact3": TLW_STORY.get("tagline", ""),
    }
    if x_char_count(claude_result["tweet"]) > 280:
        t = claude_result["tweet"]
        while x_char_count(t) > 278 and len(t) > 40: t = t.rsplit(" ", 1)[0]
        claude_result["tweet"] = t.strip()
else:
    claude_result = call_claude_news(STORY_TITLE, STORY_SUMMARY)
    if claude_result == "SKIP" or claude_result is None: print("Story skipped \u2014 exiting"); exit(0)

tweet_text = claude_result.get("tweet", STORY_TITLE)
linkedin_text = claude_result.get("linkedin", STORY_TITLE)
headline1 = claude_result.get("h1", "Breaking Now")
headline2 = claude_result.get("h2", "Read Full Story")
hook_text = claude_result.get("hook", "")
lines_raw = claude_result.get("lines", "")
img_keyword = claude_result.get("keyword", IMAGE_KEYWORD)
story_tier = str(claude_result.get("tier", "1")).strip()
support_lines = [l.strip() for l in lines_raw.split("|") if l.strip()][:3]
stat_number = claude_result.get("stat_number", headline1)
stat_label = claude_result.get("stat_label", headline2)
stat_context = claude_result.get("stat_context", "")
compare_a_label = claude_result.get("compare_a_label", "")
compare_a_value = claude_result.get("compare_a_value", "")
compare_b_label = claude_result.get("compare_b_label", "")
compare_b_value = claude_result.get("compare_b_value", "")
fact1 = claude_result.get("fact1", "")
fact2 = claude_result.get("fact2", "")
fact3 = claude_result.get("fact3", "")

def has_real_stat(val): return bool(re.search(r'[$%\d]', val)) if val else False
stat_is_real = has_real_stat(stat_number)
do_carousel = (story_tier == "1") and stat_is_real and carousel_allowed()

print(f"Tier:{story_tier} | Stat:'{stat_number}' | RealStat:{stat_is_real} | Carousel:{do_carousel} | Tweet:{x_char_count(tweet_text)} chars")
print(f"DEBUG carousel \u2014 stat_label:'{stat_label}' | fact1:'{fact1}' | fact2:'{fact2}'")
print(f"DEBUG compare \u2014 A:'{compare_a_label}'='{compare_a_value}' | B:'{compare_b_label}'='{compare_b_value}'")

linkedin_text = strip_urls(linkedin_text)
ig_caption = f"{headline1}\n\n{headline2}\n\n{hook_text}\n\nFollow @theledgerwire.ai for daily AI & Finance intel.\n\n#AI #Finance #Tech #Investing #Markets #ArtificialIntelligence #StockMarket #Crypto"

if x_char_count(tweet_text) > 280: print("ERROR: Tweet over 280 \u2014 exiting"); exit(1)
used_images = load_used_images()

_, used_img_url = generate_news_card(
    headline1, headline2, img_keyword, support_lines, hook_text,
    story_context=f"{STORY_TITLE} {STORY_SUMMARY}",
    used_images=used_images, story_title=STORY_TITLE, story_summary=STORY_SUMMARY
)

if BUFFER_API_KEY and GITHUB_TOKEN:
    pushed = push_to_github("card.png", GITHUB_TOKEN, REPO, IMAGE_PATH)
    if pushed:
        if used_img_url: save_used_image(used_img_url, used_images)
        time.sleep(5)

        # X
        if BUFFER_PROFILE_X:
            time.sleep(3)
            ok_x = post_to_buffer(tweet_text, RAW_URL, BUFFER_PROFILE_X, BUFFER_API_KEY, "X")
            print("X: SUCCESS" if ok_x else "X: FAILED")

        # LinkedIn
        if BUFFER_PROFILE_LI:
            time.sleep(3)
            pdf_posted = False
            if do_carousel and stat_number:
                print("--- Building LinkedIn PDF carousel ---")
                ts = int(time.time())
                pdf_path = f"cards/carousel_{ts}.pdf"
                pdf_url = f"https://raw.githubusercontent.com/{REPO}/main/{pdf_path}"
                takeaway_text = fact3 if fact3 else "AI is landing on your P&L right now."
                pdf_ok = generate_carousel_pdf("carousel.pdf", h1=headline1, h2=headline2, hook=hook_text,
                    stat_number=stat_number, stat_label=stat_label, stat_context=stat_context,
                    compare_a_label=compare_a_label, compare_a_value=compare_a_value,
                    compare_b_label=compare_b_label, compare_b_value=compare_b_value,
                    fact1=fact1, fact2=fact2, fact3=fact3, takeaway=takeaway_text)
                if pdf_ok:
                    pushed_pdf = push_to_github("carousel.pdf", GITHUB_TOKEN, REPO, pdf_path)
                    if pushed_pdf:
                        print("Waiting 20s for GitHub raw URL propagation...")
                        time.sleep(20)
                        ok_li = post_to_buffer_document(linkedin_text, pdf_url, BUFFER_PROFILE_LI, BUFFER_API_KEY, thumbnail_url=RAW_URL)
                        print("LinkedIn PDF carousel: SUCCESS" if ok_li else "LinkedIn PDF carousel: FAILED")
                        if ok_li:
                            pdf_posted = True
                            _, current_count = load_carousel_count()
                            save_carousel_count(current_count + 1)
            if not pdf_posted:
                ok_li = post_to_buffer(linkedin_text, RAW_URL, BUFFER_PROFILE_LI, BUFFER_API_KEY, "LinkedIn")
                print("LinkedIn: SUCCESS" if ok_li else "LinkedIn: FAILED")

        # Instagram
        if BUFFER_PROFILE_IG:
            time.sleep(3)
            ok_ig = post_to_buffer_instagram(ig_caption, RAW_URL, BUFFER_PROFILE_IG, BUFFER_API_KEY)
            print("Instagram: SUCCESS" if ok_ig else "Instagram: FAILED")
        else:
            print("Instagram: skipped \u2014 add BUFFER_PROFILE_IG to GitHub secrets")

        save_used_story(story_hash(STORY_TITLE), STORY_TITLE)
        print(f"Story hash + title saved: {story_hash(STORY_TITLE)}")
    else:
        print("FAILED: GitHub push failed")
else:
    missing = [k for k,v in {"BUFFER_API_KEY":BUFFER_API_KEY,"GITHUB_TOKEN":GITHUB_TOKEN}.items() if not v]
    print(f"Missing: {', '.join(missing)}")
