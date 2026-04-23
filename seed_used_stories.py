#!/usr/bin/env python3
"""
ONE-TIME SCRIPT: Seed used_stories.json with yesterday's manually published stories.
Run once, then delete. Prevents the pipeline from re-posting stories you already covered.

Usage:
  export GITHUB_TOKEN="your_token"
  python seed_used_stories.py
"""
import os, json, base64, hashlib, requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = "theledgerwire/tlw-content-engine"
USED_STORIES_PATH = "data/used_stories.json"

# Yesterday's manually published stories — add the titles here
MANUAL_STORIES = [
    "Tim Cook stepping down as Apple CEO John Ternus takes over September",
    "Tim Cook steps down Apple CEO",
    "iPhone shipments surge 20 percent in China Q1 2026",
    "Apple iPhone China sales surge 20 percent",
    "Kelp DAO drained 292M biggest hack 2026",
    "Kelp DAO 292M hack LayerZero bridge",
    "April crypto hacks hit 606M four times Q1",
    "Crypto hacks April 606 million",
    "Bitcoin falls below 75K support",
    "Bitcoin drops below 75000",
    "Anthropic hits 30B annualized revenue ARR",
    "Anthropic 30B ARR ahead of OpenAI",
    "Nasdaq snaps 13 day winning streak",
    "Nasdaq 13 day streak ends longest since 1992",
    "Dell price target raised 245 Melius Research",
    "Dell target 245 AI server demand",
    "OpenAI launches cost per click ads ChatGPT",
    "Amazon invests 25 billion Anthropic",
    "RaveDAO collapses 95 percent",
]

def story_hash(title):
    return hashlib.md5(title.lower().strip()[:80].encode()).hexdigest()[:12]

def main():
    if not GITHUB_TOKEN:
        print("ERROR: Set GITHUB_TOKEN env var"); return

    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}",
               "Accept": "application/vnd.github.v3+json"}

    # Load existing
    existing = set()
    sha = None
    r = requests.get(
        f"https://api.github.com/repos/{REPO}/contents/{USED_STORIES_PATH}",
        headers=headers, timeout=10
    )
    if r.status_code == 200:
        data = base64.b64decode(r.json()["content"]).decode("utf-8")
        existing = set(json.loads(data).get("hashes", []))
        sha = r.json().get("sha")
        print(f"Loaded {len(existing)} existing hashes")

    # Add manual story hashes
    new_hashes = set()
    for title in MANUAL_STORIES:
        h = story_hash(title)
        new_hashes.add(h)
        print(f"  {h} ← {title[:50]}")

    combined = existing | new_hashes
    print(f"\nAdding {len(new_hashes)} new hashes → {len(combined)} total")

    # Save
    # Save with both hashes and titles
    content_str = json.dumps({
        "hashes": list(combined)[-200:],
        "titles": MANUAL_STORIES[-30:]
    }, indent=2)
    encoded = base64.b64encode(content_str.encode()).decode()
    payload = {"message": "Seed manual story hashes for dedup", "content": encoded, "branch": "main"}
    if sha:
        payload["sha"] = sha

    put_r = requests.put(
        f"https://api.github.com/repos/{REPO}/contents/{USED_STORIES_PATH}",
        headers=headers, json=payload, timeout=15
    )
    print(f"GitHub push: {put_r.status_code}")
    if put_r.status_code in [200, 201]:
        print("Done — yesterday's stories are now in the dedup tracker")
    else:
        print(f"Failed: {put_r.text[:200]}")

if __name__ == "__main__":
    main()
