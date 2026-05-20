#!/usr/bin/env python3
"""
TLW Instagram Manual Poster
Posts a single image+caption to Instagram via Buffer GraphQL API.
Includes the `type: post` fix that v18.4 is missing.

Usage:
  python post_ig.py --image-url "https://raw.githubusercontent.com/..." --caption "Your caption here"

Or set environment variables:
  BUFFER_API_KEY=xxx BUFFER_PROFILE_IG=xxx python post_ig.py --image-url "..." --caption "..."
"""

import os, sys, json, time, requests, argparse

BUFFER_API_KEY = os.environ.get("BUFFER_API_KEY", "")
BUFFER_PROFILE_IG = os.environ.get("BUFFER_PROFILE_IG", "")

def post_to_instagram(caption, image_url, channel_id, api_key, retries=2):
    """Post to Instagram via Buffer with type: post field (the fix)."""
    print(f"Posting to Instagram...")
    print(f"  Image: {image_url[:80]}...")
    print(f"  Caption: {caption[:80]}...")

    def esc(s):
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '')

    safe_text = esc(caption)
    cid = channel_id.strip()

    # KEY FIX: type: post is required for Instagram
    query = '''mutation CreatePost {
  createPost(input: {
    text: "%s",
    channelId: "%s",
    schedulingType: automatic,
    mode: addToQueue,
    type: post,
    assets: [{ image: { url: "%s" } }]
  }) {
    ... on PostActionSuccess { post { id text } }
    ... on MutationError { message }
  }
}''' % (safe_text, cid, image_url)

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
            data = r.json()
            print(f"  Response: {json.dumps(data)[:500]}")

            post_data = data.get("data", {}).get("createPost", {})

            if "errors" in data:
                print(f"  GraphQL errors: {data['errors']}")
                if attempt < retries:
                    print(f"  Retrying ({attempt+1}/{retries})...")
                    time.sleep(5)
                    continue
                return False

            if "message" in post_data and "post" not in post_data:
                print(f"  Mutation error: {post_data.get('message', 'unknown')}")
                if attempt < retries:
                    print(f"  Retrying ({attempt+1}/{retries})...")
                    time.sleep(5)
                    continue
                return False

            if post_data.get("post", {}).get("id"):
                print(f"  SUCCESS: Post ID {post_data['post']['id']}")
                return True

            print(f"  Posted (no ID returned — may be reminder mode)")
            return True

        except Exception as e:
            print(f"  Exception: {e}")
            if attempt < retries:
                print(f"  Retrying ({attempt+1}/{retries})...")
                time.sleep(5)

    print("  FAILED after all retries")
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Post to Instagram via Buffer")
    parser.add_argument("--image-url", required=True, help="Public URL of the image (GitHub raw URL)")
    parser.add_argument("--caption", required=True, help="Instagram caption text")
    parser.add_argument("--buffer-key", default=BUFFER_API_KEY, help="Buffer API key (or set BUFFER_API_KEY env)")
    parser.add_argument("--profile-ig", default=BUFFER_PROFILE_IG, help="Buffer IG profile ID (or set BUFFER_PROFILE_IG env)")
    args = parser.parse_args()

    if not args.buffer_key:
        print("ERROR: No BUFFER_API_KEY. Set env or pass --buffer-key")
        sys.exit(1)
    if not args.profile_ig:
        print("ERROR: No BUFFER_PROFILE_IG. Set env or pass --profile-ig")
        sys.exit(1)

    ok = post_to_instagram(args.caption, args.image_url, args.profile_ig, args.buffer_key)
    sys.exit(0 if ok else 1)
