#!/usr/bin/env python3
"""
TLW Research Agent v2
- Strict 48-hour recency filter (no stale news escape hatch)
- 12 web searches (up from 5) across categories
- Richer JSON schema: passes image_angle + story_context to generate_image.py
- TLW voice examples baked into the prompt
- Triggers GitHub Actions for each qualifying story
"""

import os, json, time, base64, hashlib, requests
from datetime import datetime, timezone

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
REPO          = os.environ.get("GITHUB_REPO", "")
WORKFLOW_FILE = os.environ.get("WORKFLOW_FILE", "generate.yml")

MAX_STORIES       = 9
USED_STORIES_PATH = "data/used_stories.json"


# ── Load already-used story hashes ────────────────────────────────
def load_used_stories():
    try:
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}",
                   "Accept": "application/vnd.github.v3+json"}
        r = requests.get(
            f"https://api.github.com/repos/{REPO}/contents/{USED_STORIES_PATH}",
            headers=headers, timeout=10
        )
        if r.status_code == 200:
            data = base64.b64decode(r.json()["content"]).decode("utf-8")
            return set(json.loads(data).get("hashes", []))
    except Exception as e:
        print(f"Could not load used stories: {e}")
    return set()


def story_hash(title):
    return hashlib.md5(title.lower().strip()[:80].encode()).hexdigest()[:12]


# ── Claude web search — upgraded research prompt ──────────────────
def research_todays_stories(used_hashes):
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    print(f"Researching top stories for {today}...")

    prompt = f"""You are the research editor for The Ledger Wire (TLW) — an AI & finance intelligence newsletter for operators, founders, and capital allocators. Today: {today}.

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

sub_headline (goes in WHITE, medium): 2-5 words. MUST end with a period. Reveals the 'quiet part.'
Good examples (copy this exact energy):
- "Biggest hack of 2026."
- "Nasdaq's streak ends."
- "Apple bet on hardware. Again."
- "Anthropic leads."
- "Dell, re-rated."
- "Bitcoin breaks support."
- "Stolen in April alone."
Bad examples (do NOT do this):
- "This is important news today" (too long, no edge)
- "Market reacts" (weak verb)
- "Company announces earnings" (pure wire)

tagline (closing line in caption): 5-8 words. Sharp, contrarian.
Good: "Only one of those pays the bills." / "The flip nobody was modeling." / "Risk-off is back."

body_line_1 & body_line_2 (grey body, each ≤ 8 words):
Line 1 = the key fact. Line 2 = the consequence.
Good: "Kelp DAO drained via LayerZero bridge." / "18% of rsETH supply — gone."
Good: "Longest positive run since 1992." / "S&P -0.24% as Iran tensions return."

IMAGE ANGLE — TLW VISUAL DNA
Every image MUST follow this formula:
[single cinematic subject] + [deep navy background] + [gold accent lighting] + [volumetric light / shallow DOF] + [photorealistic editorial style]

Rules:
- Subject is ONE specific object/scene — never abstract, never patterns, never collages
- Dominant colors: deep navy (#0A1628) + gold (#F5C518) accents
- Gold appears as light rays, reflections, highlights, molten metal, or glowing elements
- Shallow depth of field / cinematic low angle / dramatic side lighting preferred
- Subject positioned so text on left/bottom has breathing room (negative space bottom-left)
- NO text in image. NO logos. NO faces. NO people. NO copyrighted characters.

Reference angles that scored perfectly (match this caliber):
- Kelp hack: "Cracked navy vault door with molten gold bleeding through fractures, crystal shards scattered on the polished floor below, dramatic side lighting from the right, volumetric gold light rays, deep navy and gold palette, photorealistic editorial photograph, shallow depth of field"
- Nasdaq streak: "Bronze Wall Street charging bull on wet cobblestone street at dusk, subtle hairline crack on its bronze flank, warm gold light rays streaming from the left, blurred financial district buildings in background, cinematic low-angle shot, deep navy sky, photorealistic"
- Anthropic ARR: "Two modern glass skyscrapers at dusk against deep navy sky, the taller tower bathed in warm golden sunset light and glowing from within, the shorter tower muted and cool in shadow, volumetric gold light rays between them, cinematic editorial photograph, shallow depth of field"
- Bitcoin < $75K: "Single gold Bitcoin coin falling diagonally through deep navy space, motion blur trail of gold light behind it, subtle downward arrow formed by light rays, dramatic volumetric lighting, photorealistic, editorial magazine style"
- Tim Cook: "Solitary silhouetted figure walking down a long dark modern hallway toward a large glowing gold apple-shape of light at the end, dramatic gold light rays emanating from the far end, photorealistic cinematic editorial, deep navy and gold palette"

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
  "sub_headline": "Anthropic leads.",
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
                "max_tokens": 6000,  # ↑ Enough room for full 9-story JSON even with brief preamble
                "tools": [{"type": "web_search_20250305",
                           "name": "web_search",
                           "max_uses": 12}],  # ↑ from 5
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

        # Robust JSON array extraction — Claude sometimes adds preamble text
        # before the JSON despite instructions. Find the first [ and last ].
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
    # Pass the whole enriched story as base64 JSON so generate_image.py
    # gets all TLW voice fields + image_angle, not just title/summary.
    story_json  = json.dumps(story, ensure_ascii=False)
    encoded_blob = base64.b64encode(story_json.encode()).decode()

    # Keep legacy fields populated for backwards compat with the existing workflow
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
            # NEW — full enriched payload for generate_image.py v18
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
        print(f"✅ Triggered: {title[:60]}")
        return True
    else:
        print(f"❌ Failed ({r.status_code}): {title[:60]} — {r.text[:100]}")
        return False


# ── Main ──────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print(f"TLW Research Agent v2 — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    if not ANTHROPIC_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set"); return
    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN not set"); return
    if not REPO:
        print("ERROR: GITHUB_REPO not set"); return

    used_hashes = load_used_stories()
    print(f"Loaded {len(used_hashes)} used story hashes")

    stories = research_todays_stories(used_hashes)

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
