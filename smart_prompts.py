"""
smart_prompts.py — TLW Entity-Aware Image Prompt Generator v2
==============================================================
v2 Changes:
- Story-type classifier BEFORE visual-type routing
- No random AI faces for non-person stories
- PORTRAIT only when a known entity is the subject
- VERSUS only for explicit head-to-head stories
- SCENE/BRAND default for everything else
- Mood detection for portrait expressions

Story Types:
  PERSON   → CEO/leader is the subject → PORTRAIT allowed
  VERSUS   → Two entities competing     → VERSUS allowed
  EARNINGS → Company results            → SCENE (no people)
  MACRO    → Policy/rates/geopolitics   → SCENE (no people)
  CRYPTO   → Chain/token/protocol       → SCENE (no people)
  PRODUCT  → Launch/release             → BRAND/SCENE
  GENERAL  → Default                    → SCENE (no people)
"""

import json, os, re, random
from pathlib import Path

PROMPT_SUFFIX = "editorial photograph, dark navy and gold color palette, photorealistic, no text, no logos, no watermarks, no words"
PROMPT_NO_PEOPLE = "absolutely no people, no faces, no human figures, no hands"

# ─── Entity Registry ───────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
REGISTRY_PATH = DATA_DIR / "entity_registry.json"
USED_ANGLES_PATH = DATA_DIR / "used_angles.json"

def _load_registry():
    if REGISTRY_PATH.exists():
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    return {"people": {}, "companies": {}}

def _load_used_angles():
    if USED_ANGLES_PATH.exists():
        with open(USED_ANGLES_PATH) as f:
            return json.load(f)
    return {}

def _save_used_angles(angles):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(USED_ANGLES_PATH, 'w') as f:
        json.dump(angles, f, indent=2)

# ─── CEO ↔ Company Mapping ─────────────────────────────────────
CEO_MAP = {
    'apple': 'tim_cook', 'microsoft': 'satya_nadella', 'amazon': 'andy_jassy',
    'google': 'sundar_pichai', 'meta': 'mark_zuckerberg', 'nvidia': 'jensen_huang',
    'tesla': 'elon_musk', 'openai': 'sam_altman', 'anthropic': 'dario_amodei',
    'berkshire': 'greg_abel', 'palantir': 'alex_karp',
}

# ─── Word Boundary Matching ────────────────────────────────────
def _word_match(pattern, text):
    """Match whole words only to avoid partial matches."""
    return bool(re.search(rf'\b{re.escape(pattern)}\b', text, re.IGNORECASE))

def _find_entities(title, body_text=""):
    """Find all matching people and companies in the story text."""
    registry = _load_registry()
    text = f"{title} {body_text}".lower()
    
    found_people = []
    found_companies = []
    
    for key, person in registry.get("people", {}).items():
        for name in person.get("names", []):
            if _word_match(name, text):
                found_people.append((key, person))
                break
    
    for key, company in registry.get("companies", {}).items():
        for name in company.get("names", []):
            if _word_match(name, text):
                found_companies.append((key, company))
                break
    
    return found_people, found_companies

# ─── Story Type Classifier ─────────────────────────────────────
MACRO_KEYWORDS = [
    'fed ', 'federal reserve', 'interest rate', 'rate cut', 'rate hike',
    'inflation', 'cpi', 'gdp', 'unemployment', 'treasury', 'bond',
    'tariff', 'trade war', 'sanctions', 'war powers', 'ceasefire',
    'oil', 'brent', 'crude', 'opec', 'commodity', 'gold price',
    'geopolitics', 'nato', 'congress', 'senate', 'legislation',
    'recession', 'debt ceiling', 'fiscal', 'monetary policy',
    'swift', 'currency', 'forex', 'yuan', 'dollar index',
]

EARNINGS_KEYWORDS = [
    'earnings', 'revenue', 'quarterly', 'q1 ', 'q2 ', 'q3 ', 'q4 ',
    'profit', 'eps', 'beat estimates', 'missed estimates', 'guidance',
    'buyback', 'dividend', 'fiscal year', 'annual report', 'results',
]

CRYPTO_KEYWORDS = [
    'bitcoin', 'btc', 'ethereum', 'eth', 'solana', 'sol ',
    'crypto', 'blockchain', 'defi', 'nft', 'token', 'mining',
    'validator', 'mainnet', 'testnet', 'consensus', 'protocol',
    'staking', 'wallet', 'exchange', 'binance', 'coinbase',
    'firedancer', 'layer 2', 'l2', 'bridge', 'dao',
]

VERSUS_KEYWORDS = [
    ' vs ', ' versus ', ' against ', 'compared to', 'rivalry',
    'battle between', 'head to head', 'competing', 'showdown',
]

PRODUCT_KEYWORDS = [
    'launch', 'released', 'unveil', 'announce', 'new model',
    'update', 'upgrade', 'feature', 'rollout', 'beta',
    'iphone', 'pixel', 'galaxy', 'chip', 'processor',
]

def classify_story_type(title, body_text=""):
    """
    Classify story into a type that determines visual routing.
    Returns: 'PERSON', 'VERSUS', 'EARNINGS', 'MACRO', 'CRYPTO', 'PRODUCT', 'GENERAL'
    """
    text = f"{title} {body_text}".lower()
    found_people, found_companies = _find_entities(title, body_text)
    
    # Check VERSUS first — needs two entities and versus language
    if len(found_companies) >= 2 or len(found_people) >= 2:
        for kw in VERSUS_KEYWORDS:
            if kw in text:
                return 'VERSUS'
    
    # Check MACRO — policy/geopolitics/commodities → never show people
    macro_hits = sum(1 for kw in MACRO_KEYWORDS if kw in text)
    if macro_hits >= 2:
        return 'MACRO'
    
    # Check EARNINGS — company results → no random people
    earnings_hits = sum(1 for kw in EARNINGS_KEYWORDS if kw in text)
    if earnings_hits >= 2:
        # If story specifically names a CEO as subject (not just company), allow PERSON
        # e.g. "Cook's last earnings" = PERSON, "Apple Q2 revenue" = EARNINGS
        if found_people:
            for key, person in found_people:
                for name in person.get("names", []):
                    # Check if the person's name appears in the TITLE (not just body)
                    if _word_match(name, title.lower()):
                        return 'PERSON'
        return 'EARNINGS'
    
    # Check CRYPTO
    crypto_hits = sum(1 for kw in CRYPTO_KEYWORDS if kw in text)
    if crypto_hits >= 2:
        return 'CRYPTO'
    
    # Check PRODUCT
    product_hits = sum(1 for kw in PRODUCT_KEYWORDS if kw in text)
    if product_hits >= 2:
        # If a person is the subject of the product story, allow PERSON
        if found_people:
            for key, person in found_people:
                for name in person.get("names", []):
                    if _word_match(name, title.lower()):
                        return 'PERSON'
        return 'PRODUCT'
    
    # Check if a specific PERSON is the subject
    if found_people:
        for key, person in found_people:
            for name in person.get("names", []):
                if _word_match(name, title.lower()):
                    return 'PERSON'
    
    return 'GENERAL'

# ─── Mood Detection ────────────────────────────────────────────
def detect_story_mood(title, body_text=""):
    """Detect story mood for portrait expression selection."""
    text = f"{title} {body_text}".lower()
    
    negative = ['crash', 'fall', 'drop', 'loss', 'lawsuit', 'fraud', 'scandal',
                'fired', 'resign', 'layoff', 'cut', 'crisis', 'warn', 'fear',
                'collapse', 'fail', 'breach', 'hack', 'plunge', 'tank', 'flee',
                'war', 'sanction', 'ban', 'block', 'reject', 'kill', 'death',
                'bankrupt', 'default', 'miss', 'decline', 'worst', 'struggle']
    
    positive = ['surge', 'soar', 'record', 'beat', 'win', 'grow', 'launch',
                'break', 'milestone', 'profit', 'gain', 'rise', 'boom',
                'rally', 'bullish', 'upgrade', 'expand', 'acquire', 'partner',
                'all-time', 'ipo', 'deal', 'success', 'innovation']
    
    neg_count = sum(1 for w in negative if w in text)
    pos_count = sum(1 for w in positive if w in text)
    
    if neg_count > pos_count:
        return 'negative'
    elif pos_count > neg_count:
        return 'positive'
    return 'neutral'

# ─── Prompt Generators by Type ─────────────────────────────────
def _gen_portrait_prompt(person_key, person_data, mood, used_styles=None):
    """Generate a portrait prompt for a known entity."""
    if used_styles is None:
        used_styles = []
    
    if mood == 'negative':
        expression = person_data.get('mood_negative', 'serious intense expression, furrowed brow')
    elif mood == 'positive':
        expression = person_data.get('mood_positive', 'confident slight smile')
    else:
        expression = person_data.get('mood_neutral', 'neutral composed expression')
    
    appearance = person_data.get('appearance', 'a businessman in a dark suit')
    outfit = person_data.get('default_outfit', 'dark navy suit')
    setting = person_data.get('default_setting', 'dark modern office background')
    lighting = person_data.get('lighting', 'dramatic side lighting with warm golden tones')
    
    templates = [
        {
            'style': 'standard_portrait',
            'prompt': f"{appearance}, {outfit}, {expression}, {setting}, {lighting}, shallow depth of field, {PROMPT_SUFFIX}"
        },
        {
            'style': 'dramatic_closeup',
            'prompt': f"Close-up portrait of {appearance}, {expression}, dramatic side lighting casting deep golden shadows across the face, dark blurred background, extreme shallow depth of field, cinematic portrait photograph, {PROMPT_SUFFIX}"
        },
        {
            'style': 'environmental',
            'prompt': f"{appearance}, {outfit}, {expression}, standing in {setting}, {lighting}, medium shot showing upper body, environmental portrait, {PROMPT_SUFFIX}"
        },
    ]
    
    # Filter out recently used styles
    available = [t for t in templates if t['style'] not in used_styles]
    if not available:
        available = templates
    
    chosen = random.choice(available)
    return chosen['prompt'], chosen['style'], 'PORTRAIT'

def _gen_versus_prompt(entities):
    """Generate a versus/split prompt for two competing entities."""
    if len(entities) < 2:
        return None, None, None
    
    e1, e2 = entities[0], entities[1]
    
    # Use visual_style from registry if companies, appearance if people
    left = e1[1].get('visual_style', e1[1].get('appearance', 'a businessman'))
    right = e2[1].get('visual_style', e2[1].get('appearance', 'a businessman'))
    
    prompt = (
        f"Split frame composition with dramatic gold lightning crack dividing the image, "
        f"left side shows {left}, right side shows {right}, "
        f"dark dramatic lighting, cinematic atmosphere, {PROMPT_SUFFIX}"
    )
    return prompt, 'versus_split', 'VERSUS'

def _scene_match(keywords, text):
    """Check if any keyword matches as a whole word in text."""
    for kw in keywords:
        if _word_match(kw.strip(), text):
            return True
    return False

def _gen_scene_prompt(companies, title, body_text=""):
    """Generate a scene/object prompt with NO people."""
    text = f"{title} {body_text}".lower()
    
    # Keyword-based scenes (word-boundary matching, most specific first)
    
    if _scene_match(['war', 'military', 'defense', 'pentagon', 'war powers', 'ceasefire', 'troops'], text):
        prompt = f"A ticking gold clock face on a dark background, dramatic lighting with gold reflections, time running out concept, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        return prompt, 'clock_scene', 'SCENE'
    
    if _scene_match(['oil', 'brent', 'crude', 'opec', 'barrel', 'petroleum'], text):
        prompt = f"Gold oil barrel on dark reflective surface, dark navy background, dramatic golden side lighting, industrial texture, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        return prompt, 'oil_scene', 'SCENE'
    
    if _scene_match(['fed', 'federal reserve', 'interest rate', 'rate cut', 'rate hike', 'monetary policy', 'powell'], text):
        prompt = f"Gold Federal Reserve building facade in dramatic dark navy night sky, golden light emanating from windows, imposing architecture, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        return prompt, 'fed_scene', 'SCENE'
    
    if _scene_match(['congress', 'senate', 'legislation', 'capitol', 'bill passed', 'executive order'], text):
        prompt = f"Capitol building dome silhouette against dark navy sky with gold spotlight from below, dramatic architectural photograph, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        return prompt, 'capitol_scene', 'SCENE'
    
    if _scene_match(['china', 'chinese', 'beijing', 'shanghai'], text):
        prompt = f"Gold dragon ornament on dark navy surface with circuit board traces in gold beneath, east meets tech concept, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        return prompt, 'china_scene', 'SCENE'
    
    if _scene_match(['bitcoin', 'btc'], text):
        prompt = f"Gold Bitcoin coin falling through dark space with light trails, dark navy background, dramatic golden rim lighting, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        return prompt, 'btc_scene', 'SCENE'
    
    if _scene_match(['hack', 'breach', 'security', 'cyber', 'bug bounty', 'vulnerability', 'exploit'], text):
        prompt = f"Gold padlock with crack on dark circuit board surface, gold traces glowing, cybersecurity concept, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        return prompt, 'security_scene', 'SCENE'
    
    if _scene_match(['chip', 'semiconductor', 'silicon', 'processor', 'gpu', 'tpu'], text):
        prompt = f"Gold semiconductor chip on dark circuit board, glowing gold traces and connections, macro photography, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        return prompt, 'chip_scene', 'SCENE'
    
    if _scene_match(['layoff', 'lays off', 'laid off', 'workforce reduction', 'restructuring', 'downsizing'], text):
        prompt = f"Empty dark office chair at a desk with a single golden desk lamp illuminating nothing, abandoned corporate space, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        return prompt, 'layoff_scene', 'SCENE'
    
    if _scene_match(['earnings', 'revenue', 'profit', 'quarterly results', 'buyback', 'dividend'], text):
        prompt = f"Gold bar chart rising on dark glass surface with navy background, golden reflections, financial growth concept, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        return prompt, 'earnings_scene', 'SCENE'
    
    if _scene_match(['artificial intelligence', 'llm', 'neural network', 'machine learning', 'deep learning'], text) or re.search(r'\bai\b', text):
        prompt = f"Abstract golden neural network nodes connected by light traces on dark navy background, glowing synapses, AI concept art, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        return prompt, 'ai_scene', 'SCENE'
    
    if _scene_match(['deal', 'acquire', 'merger', 'buyout', 'acquisition'], text):
        prompt = f"Two gold chess pieces (king and queen) on dark reflective surface, dramatic side lighting, strategic concept, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        return prompt, 'deal_scene', 'SCENE'
    
    # Company visual fallback (no keyword matched but company found)
    if companies:
        company = companies[0][1]
        visuals = company.get('alt_visuals', [company.get('visual_style', '')])
        chosen_visual = random.choice(visuals) if visuals else 'abstract tech visualization'
        prompt = (
            f"{chosen_visual}, dark navy background with gold accent lighting, "
            f"dramatic cinematic composition, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        )
        return prompt, 'company_scene', 'SCENE'
    
    # Fallback — generic dark/gold scene
    prompt = f"Abstract dark navy composition with gold geometric shapes and light rays cutting through darkness, cinematic atmosphere, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
    return prompt, 'abstract_scene', 'SCENE'

# ─── Main Router ───────────────────────────────────────────────
def generate_smart_prompt(title, body_text="", image_angle_from_research=""):
    """
    Main entry point. Classifies story type, routes to correct visual generator.
    
    Returns: (prompt_text, style_name, image_type, model_hint)
        model_hint: 'portrait' → use Nano Banana 2
                    'scene'    → use Grok Imagine
    """
    story_type = classify_story_type(title, body_text)
    found_people, found_companies = _find_entities(title, body_text)
    mood = detect_story_mood(title, body_text)
    
    # Load recently used angles for dedup
    used_angles = _load_used_angles()
    
    print(f"[smart_prompts v2] Story type: {story_type} | People: {[p[0] for p in found_people]} | Companies: {[c[0] for c in found_companies]} | Mood: {mood}")
    
    prompt, style, image_type, model_hint = None, None, None, 'scene'
    
    if story_type == 'PERSON' and found_people:
        person_key, person_data = found_people[0]
        recently_used = used_angles.get(person_key, [])
        prompt, style, image_type = _gen_portrait_prompt(person_key, person_data, mood, recently_used)
        model_hint = 'portrait'
        
        # Track used style
        if person_key not in used_angles:
            used_angles[person_key] = []
        used_angles[person_key].append(style)
        # Keep only last 5
        used_angles[person_key] = used_angles[person_key][-5:]
    
    elif story_type == 'VERSUS':
        # Prefer companies for versus, fall back to people
        entities = found_companies if len(found_companies) >= 2 else found_people
        if len(entities) >= 2:
            prompt, style, image_type = _gen_versus_prompt(entities)
            model_hint = 'scene'  # VERSUS scenes use Grok, not portraits
        else:
            # Not enough entities — fall back to SCENE
            prompt, style, image_type = _gen_scene_prompt(found_companies, title, body_text)
            model_hint = 'scene'
    
    elif story_type in ('EARNINGS', 'MACRO', 'CRYPTO', 'PRODUCT', 'GENERAL'):
        # ALL of these → SCENE, no people
        prompt, style, image_type = _gen_scene_prompt(found_companies, title, body_text)
        model_hint = 'scene'
    
    # Fallback
    if not prompt:
        prompt = f"Abstract dark navy composition with gold geometric light rays, cinematic atmosphere, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        style = 'fallback_abstract'
        image_type = 'SCENE'
        model_hint = 'scene'
    
    _save_used_angles(used_angles)
    
    return prompt, style, image_type, model_hint


# ─── Standalone test ───────────────────────────────────────────
if __name__ == "__main__":
    test_cases = [
        ("Tim Cook reports $111B in Apple revenue", "Services hit $30.98B all-time. $100B buyback approved."),
        ("War Powers clock hits zero", "No authorization; ceasefire claim. Brent holds above $108 barrel."),
        ("Solana launches $1M bug bounty", "Firedancer targets 1M TPS mainnet. Alpenglow consensus due Q3 2026."),
        ("OpenAI vs Anthropic: the race heats up", "Both companies pushing frontier models. Funding war intensifies."),
        ("Jensen Huang unveils Blackwell Ultra", "Nvidia CEO shows next-gen AI chip at GTC keynote."),
        ("Fed holds rates steady at 5.5%", "Powell signals no cuts until inflation data improves."),
        ("Canada pension bets on Bitcoin", "AIMCo re-entered Strategy position. $69M unrealized gain today."),
        ("Snap lays off 20% of workforce", "Restructuring amid declining ad revenue and competition from TikTok."),
    ]
    
    print("=" * 70)
    print("SMART PROMPTS v2 — Story Type Router Test")
    print("=" * 70)
    
    for title, body in test_cases:
        prompt, style, img_type, model = generate_smart_prompt(title, body)
        print(f"\nTitle: {title}")
        print(f"  Type: {img_type} | Style: {style} | Model: {model}")
        print(f"  Prompt: {prompt[:100]}...")
        print(f"  Has 'no people': {'no people' in prompt or 'no faces' in prompt}")
        print("-" * 70)
