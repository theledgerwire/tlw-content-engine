#!/usr/bin/env python3
"""
TLW Research Agent
Runs daily to find top 9 AI/finance/tech stories and trigger GitHub Actions.
Replaces Make.com RSS pipeline entirely.
"""

import os, json, time, base64, hashlib, requests
from datetime import datetime, timezone

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
REPO          = os.environ.get("GITHUB_REPO", "")   # e.g. "username/tlw-content-engine"
WORKFLOW_FILE = os.environ.get("WORKFLOW_FILE", "generate.yml")

MAX_STORIES   = 9
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

# ── Claude web search for today's top stories ─────────────────────
def research_todays_stories(used_hashes):
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    print(f"Researching top stories for {today}...")

    prompt = f"""Research editor for The Ledger Wire (AI & Finance newsletter). Today: {today}.

Search for TOP 9 AI/finance/tech stories from the LAST 24 HOURS only.

Audience: finance professionals, investors, founders.
Must include: 1 crypto story + 1 markets/S&P story.
Prefer stories with dollar amounts, percentages, or job numbers.
Exclude: sports, celebrity, lifestyle.

Reply ONLY with a valid JSON array of 9 objects. No markdown, no explanation:
[{{"title":"12 word max headline","summary":"2 sentences with key numbers","source":"Bloomberg","keyword":"specific 4-word image search","stat":"$Xbn"}}]"""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1500,
                "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=120
        )

        if r.status_code != 200:
            print(f"Claude error: {r.status_code} — {r.text[:200]}")
            return []

        data = r.json()
        # Extract text from response (may include tool_use blocks)
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        # Parse JSON
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        stories = json.loads(text)
        print(f"Claude found {len(stories)} stories")

        # Filter out already-used stories
        fresh = []
        for s in stories:
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
    title   = story.get("title", "")
    summary = story.get("summary", "")
    keyword = story.get("keyword", "finance technology")

    # Base64 encode title and summary (matches existing pipeline)
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
            "story_title":   encoded_title,
            "story_summary": encoded_summary,
            "image_keyword": keyword,
            "card_type":     "news",
            "weekly_headlines": ""
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
    print(f"TLW Research Agent — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    if not ANTHROPIC_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set"); return
    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN not set"); return
    if not REPO:
        print("ERROR: GITHUB_REPO not set"); return

    # Load used stories for dedup
    used_hashes = load_used_stories()
    print(f"Loaded {len(used_hashes)} used story hashes")

    # Research today's stories
    stories = research_todays_stories(used_hashes)

    if not stories:
        print("No fresh stories found — exiting")
        return

    print(f"\nTriggering {len(stories)} workflow runs...")
    print("-" * 60)

    triggered = 0
    for i, story in enumerate(stories):
        print(f"\n[{i+1}/{len(stories)}] {story.get('title', '')[:70]}")
        print(f"  Source: {story.get('source', '')} | Stat: {story.get('stat', 'N/A')}")

        ok = trigger_workflow(story)
        if ok:
            triggered += 1

        # Stagger triggers — 90 seconds between each
        # This spreads 9 posts across ~13 minutes matching Buffer queue slots
        if i < len(stories) - 1:
            print(f"  Waiting 60s before next trigger...")
            time.sleep(60)

    print("\n" + "=" * 60)
    print(f"Done — {triggered}/{len(stories)} workflows triggered")
    print("=" * 60)

if __name__ == "__main__":
    main()
