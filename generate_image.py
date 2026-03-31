# TLW v6
import os
import requests
import base64
import json
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

BUFFER_API_KEY   = os.environ.get("BUFFER_API_KEY", "")
BUFFER_PROFILE_X = os.environ.get("BUFFER_PROFILE_X", "")
GITHUB_TOKEN     = os.environ.get("GITHUB_TOKEN", "")
POST_TEXT        = os.environ.get("POST_TEXT", "")
HEADLINE_LINE1   = os.environ.get("HEADLINE_LINE1", "Breaking news.")
HEADLINE_LINE2   = os.environ.get("HEADLINE_LINE2", "Read the full story.")
UNSPLASH_KEY     = os.environ.get("UNSPLASH_KEY", "")
IMAGE_KEYWORD    = os.environ.get("IMAGE_KEYWORD", "finance technology")

REPO             = "theledgerwire/tlw-content-engine"
IMAGE_PATH       = "cards/latest.png"
RAW_URL          = f"https://raw.githubusercontent.com/{REPO}/main/{IMAGE_PATH}"

W, H      = 1080, 1080
GOLD      = (240, 185, 11)
WHITE     = (255, 255, 255)
NAVY      = (4, 8, 20)
LGREY     = (175, 190, 215)
DGREY     = (100, 115, 148)
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

print("=== TLW Card Generator v6 ===")
print(f"Profile ID: {BUFFER_PROFILE_X[:8] if BUFFER_PROFILE_X else 'MISSING'}...")

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

# Generate card
photo = get_unsplash_photo(IMAGE_KEYWORD)
if photo:
    img = apply_gradient(photo)
    print("Using Unsplash photo")
else:
    img = Image.new("RGB", (W, H), NAVY)
    print("Using navy fallback")

draw = ImageDraw.Draw(img)
PAD = 52

# Logo
logo_f = ImageFont.truetype(FONT_BOLD, 19)
logo_t = "THE LEDGER WIRE"
lb = draw.textbbox((0,0), logo_t, font=logo_f)
lw = lb[2]-lb[0]
draw.text((PAD, 36), logo_t, font=logo_f, fill=WHITE)
draw.rectangle([(PAD, 59),(PAD+lw, 62)], fill=GOLD)

# Headlines bottom up
h1_f  = ImageFont.truetype(FONT_BOLD, 88)
h2_f  = ImageFont.truetype(FONT_BOLD, 80)
src_f = ImageFont.truetype(FONT_REG, 21)

SAFE_BOT = H - 46 - 18
src_h = draw.textbbox((0,0), "theledgerwire.com", font=src_f)[3]
l2_h  = draw.textbbox((0,0), HEADLINE_LINE2, font=h2_f)[3]
l1_h  = draw.textbbox((0,0), HEADLINE_LINE1, font=h1_f)[3]

src_y  = SAFE_BOT - src_h
l2_y   = src_y - 20 - l2_h
l1_y   = l2_y - 10 - l1_h
rule_y = l1_y - 18

draw.rectangle([(PAD, rule_y),(PAD+90, rule_y+4)], fill=GOLD)
draw.text((PAD, l1_y), HEADLINE_LINE1, font=h1_f, fill=WHITE)
draw.text((PAD, l2_y), HEADLINE_LINE2, font=h2_f, fill=GOLD)
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

# Push image to GitHub
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

    payload = {
        "message": "Update card image",
        "content": content,
        "branch": "main"
    }
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

# Post to Buffer using new GraphQL API
def post_to_buffer(post_text, image_url, channel_id, api_key):
    print(f"Posting to Buffer via GraphQL...")
    import time
    time.sleep(5)

    safe_text = post_text.replace('\\', '\\\\').replace('"', '\\"')
    query = '''mutation CreatePost {
      createPost(input: {
        text: "%s",
        channelId: "%s",
        schedulingType: queue,
        mediaUrls: ["%s"]
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
    print(f"Buffer status: {r.status_code}")
    print(f"Buffer response: {r.text[:400]}")
    return r.status_code == 200

if BUFFER_API_KEY and BUFFER_PROFILE_X and GITHUB_TOKEN:
    pushed = push_to_github("card.png", GITHUB_TOKEN, REPO, IMAGE_PATH)
    if pushed:
        success = post_to_buffer(POST_TEXT, RAW_URL, BUFFER_PROFILE_X, BUFFER_API_KEY)
        if success:
            print("SUCCESS: Posted to Buffer with image!")
        else:
            print("FAILED: Buffer posting failed")
    else:
        print("FAILED: GitHub push failed")
else:
    missing = []
    if not BUFFER_API_KEY: missing.append("BUFFER_API_KEY")
    if not BUFFER_PROFILE_X: missing.append("BUFFER_PROFILE_X")
    if not GITHUB_TOKEN: missing.append("GITHUB_TOKEN")
    print(f"Missing credentials: {', '.join(missing)}")
