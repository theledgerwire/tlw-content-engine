#!/usr/bin/env python3
"""
TLW Research Agent v2.1
- Hook validation + character limit enforcement
- Hook variety tracking (STAT/POWER/TENSION/NAME rotation)
- Strict 48-hour recency filter
- 12 web searches across categories
- Richer JSON schema for generate_image.py
"""

import os, json, time, base64, hashlib, requests
from datetime import datetime, timezone

# ── Hook Validator ──
try:
    from hook_validator import validate_and_fix_story, get_hook_variety_prompt_injection
    HOOK_VALIDATOR_AVAILABLE = True
    print("Hook validator loaded")
except ImportError:
    HOOK_VALIDATOR_AVAILABLE = False
    print("Hook validator not available — running without validation")

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
REPO          = os.environ.get("GITHUB_REPO", "")
WORKFLOW_FILE = os.environ.get("WORKFLOW_FILE", "generate.yml")

MAX_STORIES       = 9
USED_STORIES_PATH = "data/used_stories.json"


# ── Load already-used story hashes AND recent titles ──────────────
def load_used_stories():
    """Returns (set of hashes, list of recent title strings)."""
    try:
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}",
                   "Accept": "application/vnd.github.v3+json"}
        r = requests.get(
            f"https://api.github.com/repos/{REPO}/contents/{USED_STORIES_PATH}",
            headers=headers, timeout=10
        )
        if r.status_code == 200:
            data = base64.b64decode(r.json()["content"]).decode("utf-8")
            parsed = json.loads(data)
            hashes = set(parsed.get("hashes", []))
            titles = parsed.get("titles", [])
            return hashes, titles
    except Exception as e:
        print(f"Could not load used stories: {e}")
    return set(), []


def story_hash(title):
    return hashlib.md5(title.lower().strip()[:80].encode()).hexdigest()[:12]


# ── Claude web search — upgraded research prompt ──────────────────
def research_todays_stories(used_hashes, recent_titles=None):
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    print(f"Researching top stories for {today}...")

    # Build "already covered" block from recent titles
    already_covered = ""
    if recent_titles:
        titles_block = "\n".join(f"- {t}" for t in recent_titles[-30:])
        already_covered = f"""
ALREADY COVERED — DO NOT REPEAT THESE TOPICS (posted in last 48 hours):
{titles_block}

CRITICAL: If a story covers the SAME COMPANY + SAME EVENT as any title above, SKIP IT.
Even if published today, even if from a different source, even if the angle is slightly different.
Examples of what counts as a repeat:
- "Tim Cook stepping down" and "Cook exits Apple CEO role" = SAME STORY, skip
- "Kelp DAO hacked for $292M" and "Biggest DeFi hack of 2026" = SAME STORY, skip
- "Tesla earnings preview" and "Tesla Q1 results" = SAME STORY, skip
- "Tesla robotaxi update" ≠ "Tesla earnings" = DIFFERENT STORY, OK to include
"""
        print(f"Injecting {len(recent_titles)} recent titles for topic dedup")

    # Hook variety injection
    hook_variety_note = ""
    if HOOK_VALIDATOR_AVAILABLE:
        try:
            hook_variety_note = get_hook_variety_prompt_injection(USED_STORIES_PATH)
            if hook_variety_note:
                print(f"Hook variety rule: {hook_variety_note.strip()}")
        except Exception as e:
            print(f"Hook variety injection failed: {e}")

    prompt = f"""You are the research editor for The Ledger Wire (TLW) — an AI & finance intelligence newsletter for operators, founders, and capital allocators. Today: {today}.
{already_covered}
YOUR JOB
Find the 9 strongest AI, finance, tech, crypto, and markets stories from the LAST 48 HOURS. Do thorough multi-category searches across at least these buckets:
1. AI (model releases, labs, enterprise AI, revenue milestones)
2. Markets (S&P, Nasdaq, major index moves, sector rotation)
3. Crypto (BTC, ETH, DeFi exploits, major protocol news)
4. Big Tech (Apple, Microsoft, Google, Meta, Nvidia — earnings, leadership, product)
5. M&A / Funding (major deals, IPOs, valuations, price targets)

HARD RULES
- Every story must be published within 48 hours of {today}. Reject older stories even if they seem major.
- If fewer than 9 stories qualify, return fewer — do not pad with stale news. A 6-story day of fresh, sharp stories beats a 9-story day with filler.
- Prefer stories with hard numbers: $ amounts, %, headcount changes, price targets.
- Exclude: celebrity, sports, lifestyle, political horse-race coverage without market angle.
- Do NOT return any story from a date prior to 48 hours ago.

TLW VOICE — STRICT FORMAT
TLW is not a wire desk. Every card follows this EXACT structure.

stat_hook (goes in GOLD, huge): 2-7 characters MAX. Must be one of:
- Dollar amount: "$292M" / "$30B" / "$245" / "$1.4T"
- Percentage: "+20%" / "-95%" / "74%"
- Count: "13 DAYS" / "10,000" / "$606M"
- Threshold: "< $75K" / "> 22%"
- Date: "SEPT 1" / "Q3 2026"
- Power word (RARE, only when no number fits): "BANNED" / "OVER" / "ZERO"
NEVER use full sentences. NEVER exceed 7 characters. Must be readable at 150pt font.

sub_headline (goes in WHITE, medium): 3-6 words MAX. MUST end with a period. MUST fit on ONE line — if it wraps, it's too long.

THE TWO-LINE STORY TEST — CRITICAL:
A reader scrolling their feed will ONLY see stat_hook + sub_headline.
Together, these two lines MUST answer: "What happened?" and "To whom?"

RULE: If the stat_hook is a dollar amount or percentage, it's self-explanatory.
The sub can be punchy/atmospheric.
  "$292M" + "Biggest hack of 2026." → ✅ Dollar explains itself
  "$2.4B" + "ChatGPT sells clicks now." → ✅ Dollar + what changed
  "+20%" + "Apple in China." → ✅ Percentage + where

RULE: If the stat_hook is a COUNT, DATE, or POWER WORD, it's ambiguous.
The sub MUST explain what the number means.
  "13 DAYS" + "Nasdaq's streak ends." → ❌ What 13 days? What streak? Not clear enough
  "13 DAYS" + "Longest Nasdaq rally since '92, snapped." → ✅ Full story in two lines
  "SEPT 1" + "Apple bet on hardware. Again." → ❌ What's Sept 1? Who?
  "SEPT 1" + "Cook steps down. Ternus takes Apple." → ✅ Full story in two lines
  "BANNED" + "Deepfakes go dark." → ❌ Who banned what?
  "BANNED" + "EU outlaws all AI deepfakes." → ✅ Full story

Good sub_headlines:
- "Cook steps down. Ternus takes Apple."
- "Longest Nasdaq rally since '92, snapped."
- "Amazon locks in Anthropic."
- "Biggest DeFi hack of 2026."
- "Dell re-rated on AI server demand."
- "Stolen from crypto in April alone."

tagline (closing line in caption): 5-8 words. Sharp, contrarian.
Good: "Only one of those pays the bills." / "The flip nobody was modeling." / "Risk-off is back."

body_line_1 & body_line_2 (grey body text, STRICTLY ≤ 6 words each):
HARD LIMIT: Each line must be 6 words or fewer. Count the words. If it's 7+, rewrite shorter.
Line 1 = the key fact. Line 2 = the consequence or context.
Good (6 words or under):
- "Kelp DAO drained via bridge." (5)
- "18% of rsETH supply — gone." (6)
- "Longest positive run since 1992." (5)
- "S&P -0.24% on Iran tensions." (5)
- "Earnings tonight. AI or cars?" (5)
- "Q1 deliveries missed by 7,600." (5)
Bad (too long — NEVER do this):
- "Q1 deliveries missed by 7,600 units; 50K inventory overhang." ❌ (9 words)
- "Wall St. watching auto gross margins above 17% threshold." ❌ (9 words)

IMAGE ANGLE — TLW VISUAL DNA (THIS IS CRITICAL FOR IMAGE QUALITY)
Every image_angle MUST be 40-70 words. Short prompts produce generic images. Match the reference angles below EXACTLY in specificity and length.

MANDATORY STRUCTURE — every image_angle must include ALL 6 elements in this order:
1. SUBJECT: One specific physical object with material detail (e.g. "cracked navy vault door with molten gold bleeding through fractures" NOT "vault" or "broken door")
2. SETTING: Where it sits (e.g. "on wet cobblestone street" / "in polished marble room" / "against deep navy sky")
3. GOLD ELEMENT: How gold appears (e.g. "molten gold bleeding through", "warm gold light rays from the left", "gold sunset glow on glass")
4. CAMERA: Angle and lens (e.g. "cinematic low-angle shot" / "macro lens shallow DOF" / "wide-angle aerial perspective")
5. LIGHTING: Direction and quality (e.g. "dramatic side lighting from the right" / "volumetric gold light rays" / "warm backlight with lens flare")
6. SUFFIX: Always end with "photorealistic editorial photograph, deep navy and gold palette"

Rules:
- Subject is ONE specific physical object/scene — never abstract cursors, never floating shapes, never patterns, never collages
- Think REAL WORLD objects: vault doors, bronze statues, glass buildings, gold coins, server racks, cargo ships, marble columns — not digital concepts
- Dominant colors: deep navy (#0A1628) background + gold (#F5C518) accents
- Subject positioned right-of-center or upper-half so text on left/bottom has breathing room
- NO text in image. NO logos. NO copyrighted characters.
- NO abstract art, NO digital wireframes, NO floating geometric shapes, NO cursor icons

ENTITY-AWARE IMAGES — for stories about specific people or companies:
- If the story is about a SPECIFIC CEO/leader (Musk, Altman, Powell, Zuckerberg, etc.), the image_angle should describe that person in a cinematic setting. AI-generated portraits of public figures are allowed.
- If two people are in conflict (Musk vs Altman, Altman vs Nadella), describe both in a tense composition — split frame, facing off, opposite sides of a table.
- If the story is about a COMPANY (Google, Meta, etc.), use the company's brand colors creatively — NOT the actual logo. Example: Google = "four swirling colors red blue yellow green in an AI eye iris"
- Person prompts: include appearance, outfit, expression, setting, lighting. Be specific about mood (angry, defiant, calm, victorious).

Reference angles that scored perfectly — MATCH THIS LENGTH AND SPECIFICITY:
- Kelp hack: "Cracked navy vault door with molten gold bleeding through fractures, crystal shards scattered on the polished floor below, dramatic side lighting from the right, volumetric gold light rays, deep navy and gold palette, photorealistic editorial photograph, shallow depth of field"
- Nasdaq streak: "Bronze Wall Street charging bull on wet cobblestone street at dusk, subtle hairline crack on its bronze flank, warm gold light rays streaming from the left, blurred financial district buildings in background, cinematic low-angle shot, deep navy sky, photorealistic"
- Anthropic ARR: "Two modern glass skyscrapers at dusk against deep navy sky, the taller tower bathed in warm golden sunset light and glowing from within, the shorter tower muted and cool in shadow, volumetric gold light rays between them, cinematic editorial photograph, shallow depth of field"
- Bitcoin drop: "Single gold Bitcoin coin falling diagonally through deep navy space, motion blur trail of gold light behind it, subtle downward arrow formed by light rays, dramatic volumetric lighting, photorealistic, editorial magazine style"
- Dell servers: "Long data center aisle with rows of dark server racks on both sides, warm gold LED indicators glowing through glass panels, volumetric light rays streaming down the corridor, cinematic wide-angle perspective, deep navy and gold palette, photorealistic editorial photograph"

COMMON MISTAKES TO AVOID:
- "Digital cursor floating in space" → Too abstract. Use: "Illuminated computer mouse on dark marble desk with gold light reflecting off its surface"
- "AI neural network visualization" → Too abstract. Use: "Single GPU chip on dark surface with gold circuit traces glowing, macro lens extreme close-up"
- "Financial charts and graphs" → Too generic. Use: "Stack of gold bars on a dark marble trading desk, NYSE screens blurred in background"

HOOK VARIETY — do NOT default to numbers every time:
- STAT mode ($60B, +71%, $344M): use for money/data stories where the NUMBER is the story
- POWER mode (FIRED., BANNED., OPEN., WAR.): use for conflict/disruption/crisis — single word + period
- TENSION mode (TOO LATE?, WHO WINS?, RISK ON.): use for uncertain/two-sided stories
- NAME mode (TESLA, OPENAI, META, NVIDIA): use when the COMPANY is the headline — all caps, no period
Rule: if 3+ recent stories used STAT mode, the next story MUST use POWER, TENSION, or NAME mode.
Never use STAT mode for stories where a power word or company name hits harder.
{hook_variety_note}
Examples: "Meta fires 8000" → "META" not "8,000". "Tesla sales collapse" → "TESLA" not "-24.3%". "OpenAI ships GPT-5.5" → "OPENAI" not "2X".

CARD TEXT HARD LIMITS — these are rendering constraints, not suggestions:
- stat_hook: MAX 7 characters including $/%/+. Examples: "$82K", "+71%", "4X", "FIRED.", "$1.75T", "TESLA", "OPENAI"
- sub_headline: MAX 30 characters (5 words max, end with period). Must fit 1 line at 52pt on a 1080px card.
- body_line_1: MAX 35 characters (6 words max)
- body_line_2: MAX 35 characters (6 words max)
- tagline: MAX 40 characters
If your text exceeds these limits, REWRITE IT SHORTER. Never exceed.

OUTPUT FORMAT — CRITICAL
Your ENTIRE response must be a valid JSON array and nothing else.
- Do NOT write any explanatory text before the JSON
- Do NOT write phrases like "Here is the JSON" or "I now have the data"
- Do NOT summarize what you found
- Do NOT use markdown code fences (```)
- The FIRST character of your response MUST be [
- The LAST character of your response MUST be ]

If you start typing anything other than [, stop and restart with [.

Format:

[{{
  "title": "12 word max wire headline",
  "summary": "2 sentences with the hard numbers",
  "source": "Bloomberg / Reuters / CoinDesk / etc",
  "published_hours_ago": 12,
  "stat_hook": "$30B",
  "sub_headline": "Anthropic ARR overtakes OpenAI.",
  "tagline": "Only one of those pays the bills.",
  "body_line_1": "ARR now possibly ahead of OpenAI.",
  "body_line_2": "Money-loser to leader — in months.",
  "source_tag": "THE DECODER",
  "category": "ai",
  "tier": 1,
  "image_angle": "Two modern glass skyscrapers at dusk against deep navy sky, the taller bathed in warm gold sunset light and glowing from within, the shorter muted in cool shadow, volumetric gold light rays between them, cinematic editorial photograph, shallow depth of field, photorealistic",
  "keyword_fallback": "corporate skyscraper night"
}}]"""

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
                "max_tokens": 6000,
                "tools": [{"type": "web_search_20250305",
                           "name": "web_search",
                           "max_uses": 12}],
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=180
        )

        if r.status_code != 200:
            print(f"Claude error: {r.status_code} — {r.text[:200]}")
            return []

        data = r.json()
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        text = text.strip()
        print(f"Response preview (first 200 chars): {text[:200]}")

        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        # Robust JSON array extraction
        stories = None
        try:
            stories = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            end   = text.rfind("]")
            if start >= 0 and end > start:
                json_slice = text[start:end + 1]
                print(f"Found JSON slice at chars {start}-{end}, extracting...")
                try:
                    stories = json.loads(json_slice)
                except json.JSONDecodeError as e2:
                    print(f"Secondary JSON parse failed: {e2}")
                    print(f"Slice preview: {json_slice[:300]}")
                    return []
            else:
                print(f"No JSON array found in response")
                print(f"Raw response: {text[:500]}")
                return []

        if not isinstance(stories, list):
            print(f"Parsed JSON is not a list: {type(stories)}")
            return []

        print(f"Claude returned {len(stories)} stories")

        # Strict recency filter — hard 48hr cutoff
        fresh_by_age = []
        for s in stories:
            age = s.get("published_hours_ago", 999)
            if isinstance(age, (int, float)) and age <= 48:
                fresh_by_age.append(s)
            else:
                print(f"Rejected (age={age}h): {s.get('title', '')[:60]}")

        print(f"{len(fresh_by_age)} stories passed 48hr filter")

        # Dedup against historical
        fresh = []
        for s in fresh_by_age:
            h = story_hash(s.get("title", ""))
            if h not in used_hashes:
                fresh.append(s)
            else:
                print(f"Skipping duplicate: {s.get('title', '')[:50]}")

        print(f"{len(fresh)} fresh stories after dedup")

        # Validate hooks on each story
        if HOOK_VALIDATOR_AVAILABLE:
            for s in fresh:
                try:
                    validate_and_fix_story(s, USED_STORIES_PATH)
                except Exception as e:
                    print(f"Hook validation error: {e}")

        return fresh[:MAX_STORIES]

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Raw response: {text[:500]}")
        return []
    except Exception as e:
        print(f"Research error: {e}")
        return []


# ── Trigger GitHub Actions workflow for each story ────────────────
def trigger_workflow(story):
    story_json  = json.dumps(story, ensure_ascii=False)
    encoded_blob = base64.b64encode(story_json.encode()).decode()

    title   = story.get("title", "")
    summary = story.get("summary", "")
    keyword = story.get("keyword_fallback", "finance technology")
    encoded_title   = base64.b64encode(title.encode()).decode()
    encoded_summary = base64.b64encode(summary.encode()).decode()

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }

    payload = {
        "ref": "main",
        "inputs": {
            "story_title":     encoded_title,
            "story_summary":   encoded_summary,
            "image_keyword":   keyword,
            "card_type":       "news",
            "weekly_headlines": "",
            "story_blob":      encoded_blob,
        }
    }

    r = requests.post(
        f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches",
        headers=headers,
        json=payload,
        timeout=30
    )

    if r.status_code == 204:
        print(f"\u2705 Triggered: {title[:60]}")
        return True
    else:
        print(f"\u274c Failed ({r.status_code}): {title[:60]} — {r.text[:100]}")
        return False


# ── Main ──────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print(f"TLW Research Agent v2.1 — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    if not ANTHROPIC_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set"); return
    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN not set"); return
    if not REPO:
        print("ERROR: GITHUB_REPO not set"); return

    used_hashes, recent_titles = load_used_stories()
    print(f"Loaded {len(used_hashes)} used story hashes, {len(recent_titles)} recent titles")

    stories = research_todays_stories(used_hashes, recent_titles)

    if not stories:
        print("No fresh stories found — exiting")
        return

    print(f"\nTriggering {len(stories)} workflow runs...")
    print("-" * 60)

    triggered = 0
    for i, story in enumerate(stories):
        print(f"\n[{i+1}/{len(stories)}] {story.get('title', '')[:70]}")
        print(f"  Source: {story.get('source', '')} | "
              f"Hook: {story.get('stat_hook', 'N/A')} | "
              f"Mode: {story.get('hook_mode', '?')} | "
              f"Age: {story.get('published_hours_ago', '?')}h")

        ok = trigger_workflow(story)
        if ok:
            triggered += 1

        if i < len(stories) - 1:
            print(f"  Waiting 60s before next trigger...")
            time.sleep(60)

    print("\n" + "=" * 60)
    print(f"Done — {triggered}/{len(stories)} workflows triggered")
    print("=" * 60)


if __name__ == "__main__":
    main()
