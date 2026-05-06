"""
smart_prompts.py — TLW Entity-Aware Image Prompt Generator v3
==============================================================
v3 Changes (from v2):
- Unknown person detection (names not in registry)
- Dynamic appearance lookup via Claude API + web search
- Auto-add discovered people to registry for future use
- REVIEW_MODE: flag prompts for human approval before generation
- Unknown person with no lookup = SCENE fallback (never random faces)

Modes:
  AUTO     → generate immediately (known people only)
  REVIEW   → flag unknown people for approval, auto-generate known
  MANUAL   → flag everything for approval

Flow for unknown person:
  1. Detect name in title that isn't in registry
  2. Call Claude API + web search for real appearance
  3. If REVIEW_MODE: save to pending_prompts.json for approval
  4. If AUTO + lookup succeeded: generate with dynamic prompt
  5. If lookup failed: fall back to SCENE (no random faces ever)
"""

import json, os, re, random, time
from pathlib import Path

# ─── Configuration ─────────────────────────────────────────────
GENERATION_MODE = os.environ.get("TLW_GEN_MODE", "REVIEW")  # AUTO | REVIEW | MANUAL
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ENABLE_DYNAMIC_LOOKUP = True  # Set False to skip API calls entirely

PROMPT_SUFFIX = "editorial photograph, dark navy and gold color palette, photorealistic, no text, no logos, no watermarks, no words, no letters"
PROMPT_NO_PEOPLE = "absolutely no people, no faces, no human figures, no hands"

# ─── Paths ─────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
REGISTRY_PATH = DATA_DIR / "entity_registry.json"
USED_ANGLES_PATH = DATA_DIR / "used_angles.json"
PENDING_PATH = DATA_DIR / "pending_prompts.json"
LOOKUP_CACHE_PATH = DATA_DIR / "lookup_cache.json"

def _load_json(path, default=None):
    if default is None:
        default = {}
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default

def _save_json(path, data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def _load_registry():
    return _load_json(REGISTRY_PATH, {"people": {}, "companies": {}})

def _load_used_angles():
    return _load_json(USED_ANGLES_PATH)

def _save_used_angles(angles):
    _save_json(USED_ANGLES_PATH, angles)

def _load_pending():
    return _load_json(PENDING_PATH, {"pending": []})

def _save_pending(pending):
    _save_json(PENDING_PATH, pending)

def _load_lookup_cache():
    return _load_json(LOOKUP_CACHE_PATH)

def _save_lookup_cache(cache):
    _save_json(LOOKUP_CACHE_PATH, cache)

# ─── CEO ↔ Company Mapping ─────────────────────────────────────
CEO_MAP = {
    'apple': 'tim_cook', 'microsoft': 'satya_nadella', 'amazon': 'andy_jassy',
    'google': 'sundar_pichai', 'meta': 'mark_zuckerberg', 'nvidia': 'jensen_huang',
    'tesla': 'elon_musk', 'openai': 'sam_altman', 'anthropic': 'dario_amodei',
    'berkshire': 'greg_abel', 'palantir': 'alex_karp',
    'microstrategy': 'michael_saylor', 'strategy': 'michael_saylor',
}

# ─── Word Boundary Matching ────────────────────────────────────
def _word_match(pattern, text):
    return bool(re.search(rf'\b{re.escape(pattern)}\b', text, re.IGNORECASE))

def _scene_match(keywords, text):
    for kw in keywords:
        if _word_match(kw.strip(), text):
            return True
    return False

def _find_entities(title, body_text=""):
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

# ─── Unknown Person Detection ──────────────────────────────────
# Common words that look like names but aren't
FALSE_POSITIVE_NAMES = {
    'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'by',
    'and', 'or', 'but', 'not', 'all', 'no', 'its', 'new', 'old',
    'big', 'top', 'oil', 'war', 'fed', 'gdp', 'cpi', 'ipo', 'sec',
    'powers', 'ultra', 'pro', 'max', 'plus', 'prime', 'delta',
    'ai', 'uk', 'us', 'eu', 'dc', 'nyc', 'btc', 'eth', 'sol',
    'q1', 'q2', 'q3', 'q4', 'amd', 'ibm', 'gme', 'spy', 'qqq',
    'nasdaq', 'dow', 'gold', 'cash', 'dead', 'ever', 'just', 'now',
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
    'january', 'february', 'march', 'april', 'may', 'june', 'july',
    'august', 'september', 'october', 'november', 'december',
}

# Known company/brand names that aren't people
KNOWN_NON_PERSON = {
    'spacex', 'openai', 'anthropic', 'nvidia', 'apple', 'google',
    'microsoft', 'amazon', 'meta', 'tesla', 'berkshire', 'palantir',
    'solana', 'bitcoin', 'ethereum', 'coinbase', 'binance',
    'gamestop', 'ebay', 'oracle', 'snap', 'spirit', 'boeing',
    'starlink', 'firedancer', 'alpenglow', 'blackwell',
}

def _detect_unknown_persons(title, found_people):
    """
    Detect potential person names in title that aren't in the registry.
    Uses simple heuristics: capitalized words that look like names.
    Returns list of potential name strings.
    """
    # Already found known people — no need to detect unknowns
    if found_people:
        return []
    
    # Extract potential names: capitalized words, possessives, multi-word
    potential = []
    
    # Pattern 1: "Name's" possessive (e.g., "Saylor's", "Cook's", "Abel's")
    possessives = re.findall(r"\b([A-Z][a-z]+)'s\b", title)
    for name in possessives:
        if name.lower() not in FALSE_POSITIVE_NAMES and name.lower() not in KNOWN_NON_PERSON:
            potential.append(name)
    
    # Pattern 2: Two consecutive capitalized words (e.g., "Mark Cuban", "Sam Altman")
    two_word = re.findall(r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b', title)
    for name in two_word:
        words = name.lower().split()
        if all(w not in FALSE_POSITIVE_NAMES and w not in KNOWN_NON_PERSON for w in words):
            potential.append(name)
    
    # Pattern 3: Single capitalized word used as subject (before verb or possessive)
    # e.g., "Saylor mulls BTC sales"
    single_caps = re.findall(r'\b([A-Z][a-z]{2,})\b', title)
    for name in single_caps:
        if name.lower() not in FALSE_POSITIVE_NAMES and name.lower() not in KNOWN_NON_PERSON:
            # Check it's not already captured
            if name not in potential and not any(name in p for p in potential):
                potential.append(name)
    
    return list(set(potential))

# ─── Dynamic Appearance Lookup via Claude API ──────────────────
def _dynamic_lookup(person_name):
    """
    Call Claude API with web search to get a person's real appearance.
    Returns a dict matching the registry person schema, or None.
    Caches results to avoid repeated API calls.
    """
    if not ENABLE_DYNAMIC_LOOKUP or not ANTHROPIC_API_KEY:
        return None
    
    # Check cache first
    cache = _load_lookup_cache()
    cache_key = person_name.lower().replace(' ', '_')
    if cache_key in cache:
        print(f"[smart_prompts v3] Cache hit for {person_name}")
        if cache[cache_key] is None:
            return None  # Previously failed lookup
        return cache[cache_key]
    
    print(f"[smart_prompts v3] Dynamic lookup for: {person_name}")
    
    try:
        import requests
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 500,
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                "messages": [{
                    "role": "user",
                    "content": f"""Search for what {person_name} looks like. Then respond with ONLY a JSON object (no markdown, no backticks) with these exact keys:
{{
  "full_name": "their full name",
  "appearance": "physical description for AI image generation: age, hair color/style, facial hair, build, distinguishing features",
  "default_outfit": "what they typically wear in public/professional settings",
  "default_setting": "a setting associated with them or their company",
  "lighting": "dramatic lighting description appropriate for editorial photography",
  "mood_positive": "expression description when conveying good news",
  "mood_negative": "expression description when conveying bad news",
  "mood_neutral": "neutral expression description"
}}

Be specific about physical features. This will be used to generate an AI portrait, so accuracy matters. Do NOT include any company logos or brand names in descriptions."""
                }]
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"[smart_prompts v3] API error: {response.status_code}")
            cache[cache_key] = None
            _save_lookup_cache(cache)
            return None
        
        data = response.json()
        
        # Extract text content from response
        text_content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_content += block.get("text", "")
        
        # Parse JSON from response
        text_content = text_content.strip()
        text_content = re.sub(r'^```json\s*', '', text_content)
        text_content = re.sub(r'\s*```$', '', text_content)
        
        person_data = json.loads(text_content)
        
        # Add names list for registry
        names = [person_name.lower()]
        if ' ' in person_name:
            # Add last name as alias
            names.append(person_name.split()[-1].lower())
        person_data['names'] = names
        person_data['source'] = 'dynamic_lookup'
        person_data['lookup_date'] = time.strftime('%Y-%m-%d')
        
        # Cache the result
        cache[cache_key] = person_data
        _save_lookup_cache(cache)
        
        # Auto-add to registry for future use
        _auto_add_to_registry(cache_key, person_data)
        
        print(f"[smart_prompts v3] Lookup success: {person_data.get('full_name', person_name)}")
        return person_data
        
    except Exception as e:
        print(f"[smart_prompts v3] Lookup failed for {person_name}: {e}")
        cache[cache_key] = None
        _save_lookup_cache(cache)
        return None

def _auto_add_to_registry(key, person_data):
    """Add a dynamically discovered person to the registry."""
    registry = _load_registry()
    if key not in registry.get("people", {}):
        registry.setdefault("people", {})[key] = person_data
        _save_json(REGISTRY_PATH, registry)
        print(f"[smart_prompts v3] Auto-added {key} to entity registry")

# ─── Review Mode ───────────────────────────────────────────────
def _flag_for_review(title, person_name, prompt, style, image_type, model_hint, person_data=None):
    """
    Save prompt to pending_prompts.json for human review.
    Returns a SCENE fallback prompt for now.
    """
    pending = _load_pending()
    
    entry = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "title": title,
        "person_name": person_name,
        "suggested_prompt": prompt,
        "style": style,
        "image_type": image_type,
        "model_hint": model_hint,
        "status": "PENDING",
        "person_data": person_data,
        "options": {
            "approve": "Use suggested prompt as-is",
            "edit": "Modify the prompt before generating",
            "scene": "Skip portrait, use SCENE instead",
            "add_to_registry": "Approve and add person to registry"
        }
    }
    
    pending.setdefault("pending", []).append(entry)
    _save_pending(pending)
    
    print(f"[smart_prompts v3] FLAGGED FOR REVIEW: {person_name} in '{title}'")
    print(f"[smart_prompts v3] Check data/pending_prompts.json to approve/edit/skip")
    
    return entry

# ─── Story Type Keywords ───────────────────────────────────────
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
    'microstrategy', 'strategy', 'saylor',
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

# ─── Story Type Classifier ─────────────────────────────────────
def classify_story_type(title, body_text=""):
    text = f"{title} {body_text}".lower()
    found_people, found_companies = _find_entities(title, body_text)
    
    if len(found_companies) >= 2 or len(found_people) >= 2:
        for kw in VERSUS_KEYWORDS:
            if kw in text:
                return 'VERSUS'
    
    macro_hits = sum(1 for kw in MACRO_KEYWORDS if kw in text)
    if macro_hits >= 2:
        return 'MACRO'
    
    earnings_hits = sum(1 for kw in EARNINGS_KEYWORDS if kw in text)
    if earnings_hits >= 2:
        if found_people:
            for key, person in found_people:
                for name in person.get("names", []):
                    if _word_match(name, title.lower()):
                        return 'PERSON'
        return 'EARNINGS'
    
    crypto_hits = sum(1 for kw in CRYPTO_KEYWORDS if kw in text)
    if crypto_hits >= 2:
        # Allow PERSON if known person is the subject
        if found_people:
            for key, person in found_people:
                for name in person.get("names", []):
                    if _word_match(name, title.lower()):
                        return 'PERSON'
        return 'CRYPTO'
    
    product_hits = sum(1 for kw in PRODUCT_KEYWORDS if kw in text)
    if product_hits >= 2:
        if found_people:
            for key, person in found_people:
                for name in person.get("names", []):
                    if _word_match(name, title.lower()):
                        return 'PERSON'
        return 'PRODUCT'
    
    if found_people:
        for key, person in found_people:
            for name in person.get("names", []):
                if _word_match(name, title.lower()):
                    return 'PERSON'
    
    return 'GENERAL'

# ─── Mood Detection ────────────────────────────────────────────
def detect_story_mood(title, body_text=""):
    text = f"{title} {body_text}".lower()
    
    negative = ['crash', 'fall', 'drop', 'loss', 'lawsuit', 'fraud', 'scandal',
                'fired', 'resign', 'layoff', 'cut', 'crisis', 'warn', 'fear',
                'collapse', 'fail', 'breach', 'hack', 'plunge', 'tank', 'flee',
                'war', 'sanction', 'ban', 'block', 'reject', 'kill', 'death',
                'bankrupt', 'default', 'miss', 'decline', 'worst', 'struggle',
                'dead', 'sank', 'bleed']
    
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

# ─── Prompt Generators ─────────────────────────────────────────
def _gen_portrait_prompt(person_key, person_data, mood, used_styles=None):
    if used_styles is None:
        used_styles = []
    
    if mood == 'negative':
        expression = person_data.get('mood_negative', 'serious intense expression, furrowed brow')
    elif mood == 'positive':
        expression = person_data.get('mood_positive', 'confident slight smile')
    else:
        expression = person_data.get('mood_neutral', 'neutral composed expression')
    
    appearance = person_data.get('appearance', '')
    outfit = person_data.get('default_outfit', 'dark navy suit')
    setting = person_data.get('default_setting', 'dark modern office background')
    lighting = person_data.get('lighting', 'dramatic side lighting with warm golden tones')
    
    # Get full name for the prompt (helps AI models generate accurate likeness)
    full_name = person_data.get('full_name', '')
    name_prefix = f"{full_name}, " if full_name else ""
    
    templates = [
        {
            'style': 'standard_portrait',
            'prompt': f"{name_prefix}{appearance}, {outfit}, {expression}, {setting}, {lighting}, shallow depth of field, {PROMPT_SUFFIX}"
        },
        {
            'style': 'dramatic_closeup',
            'prompt': f"Close-up portrait of {name_prefix}{appearance}, {expression}, dramatic side lighting casting deep golden shadows across the face, dark blurred background, extreme shallow depth of field, cinematic portrait photograph, {PROMPT_SUFFIX}"
        },
        {
            'style': 'environmental',
            'prompt': f"{name_prefix}{appearance}, {outfit}, {expression}, standing in {setting}, {lighting}, medium shot showing upper body, environmental portrait, {PROMPT_SUFFIX}"
        },
    ]
    
    available = [t for t in templates if t['style'] not in used_styles]
    if not available:
        available = templates
    
    chosen = random.choice(available)
    return chosen['prompt'], chosen['style'], 'PORTRAIT'

def _gen_versus_prompt(entities):
    if len(entities) < 2:
        return None, None, None
    
    e1, e2 = entities[0], entities[1]
    left = e1[1].get('visual_style', e1[1].get('appearance', 'a businessman'))
    right = e2[1].get('visual_style', e2[1].get('appearance', 'a businessman'))
    
    prompt = (
        f"Split frame composition with dramatic gold lightning crack dividing the image, "
        f"left side shows {left}, right side shows {right}, "
        f"dark dramatic lighting, cinematic atmosphere, {PROMPT_SUFFIX}"
    )
    return prompt, 'versus_split', 'VERSUS'

def _gen_scene_prompt(companies, title, body_text=""):
    text = f"{title} {body_text}".lower()
    
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
    
    if _scene_match(['deal', 'acquire', 'merger', 'buyout', 'acquisition', 'bid', 'hostile'], text):
        prompt = f"Two gold chess pieces (king and queen) on dark reflective surface, dramatic side lighting, strategic concept, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        return prompt, 'deal_scene', 'SCENE'
    
    if companies:
        company = companies[0][1]
        visuals = company.get('alt_visuals', [company.get('visual_style', '')])
        chosen_visual = random.choice(visuals) if visuals else 'abstract tech visualization'
        prompt = (
            f"{chosen_visual}, dark navy background with gold accent lighting, "
            f"dramatic cinematic composition, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
        )
        return prompt, 'company_scene', 'SCENE'
    
    prompt = f"Abstract dark navy composition with gold geometric shapes and light rays cutting through darkness, cinematic atmosphere, {PROMPT_NO_PEOPLE}, {PROMPT_SUFFIX}"
    return prompt, 'abstract_scene', 'SCENE'

# ─── Main Router ───────────────────────────────────────────────
def generate_smart_prompt(title, body_text="", image_angle_from_research=""):
    """
    Main entry point. Classifies story, routes to correct visual generator.
    
    Returns: dict with keys:
        prompt       - image generation prompt text
        style        - style name for dedup tracking
        image_type   - PORTRAIT | VERSUS | SCENE
        model_hint   - 'portrait' (Nano Banana 2) | 'scene' (Grok Imagine)
        status       - 'READY' | 'PENDING_REVIEW' | 'SCENE_FALLBACK'
        review_entry - dict if flagged for review, else None
        person_name  - detected person name if any
    """
    story_type = classify_story_type(title, body_text)
    found_people, found_companies = _find_entities(title, body_text)
    mood = detect_story_mood(title, body_text)
    used_angles = _load_used_angles()
    
    # Detect unknown persons in title
    unknown_persons = _detect_unknown_persons(title, found_people)
    
    print(f"[smart_prompts v3] Story: {story_type} | Known: {[p[0] for p in found_people]} | Unknown: {unknown_persons} | Companies: {[c[0] for c in found_companies]} | Mood: {mood} | Mode: {GENERATION_MODE}")
    
    result = {
        'prompt': None, 'style': None, 'image_type': None,
        'model_hint': 'scene', 'status': 'READY', 'review_entry': None,
        'person_name': None
    }
    
    # ── KNOWN PERSON ──────────────────────────────────────────
    if story_type == 'PERSON' and found_people:
        person_key, person_data = found_people[0]
        recently_used = used_angles.get(person_key, [])
        prompt, style, image_type = _gen_portrait_prompt(person_key, person_data, mood, recently_used)
        
        result.update({
            'prompt': prompt, 'style': style, 'image_type': image_type,
            'model_hint': 'portrait', 'status': 'READY',
            'person_name': person_data.get('full_name', person_key)
        })
        
        if person_key not in used_angles:
            used_angles[person_key] = []
        used_angles[person_key].append(style)
        used_angles[person_key] = used_angles[person_key][-5:]
        _save_used_angles(used_angles)
        
        if GENERATION_MODE == 'MANUAL':
            entry = _flag_for_review(title, person_key, prompt, style, image_type, 'portrait', person_data)
            result['status'] = 'PENDING_REVIEW'
            result['review_entry'] = entry
        
        return result
    
    # ── UNKNOWN PERSON DETECTED ───────────────────────────────
    if unknown_persons and story_type in ('GENERAL', 'CRYPTO', 'EARNINGS', 'PRODUCT'):
        person_name = unknown_persons[0]  # Take first detected name
        print(f"[smart_prompts v3] Unknown person detected: {person_name}")
        
        # Try dynamic lookup
        person_data = _dynamic_lookup(person_name)
        
        if person_data:
            # Lookup succeeded — build portrait prompt
            prompt, style, image_type = _gen_portrait_prompt(
                person_name.lower().replace(' ', '_'),
                person_data, mood
            )
            
            if GENERATION_MODE in ('REVIEW', 'MANUAL'):
                # Flag for review — don't auto-generate unknown faces
                entry = _flag_for_review(title, person_name, prompt, style, image_type, 'portrait', person_data)
                
                # Generate SCENE as interim fallback
                scene_prompt, scene_style, scene_type = _gen_scene_prompt(found_companies, title, body_text)
                result.update({
                    'prompt': scene_prompt, 'style': scene_style,
                    'image_type': scene_type, 'model_hint': 'scene',
                    'status': 'PENDING_REVIEW', 'review_entry': entry,
                    'person_name': person_name
                })
            else:
                # AUTO mode — use dynamic prompt directly
                result.update({
                    'prompt': prompt, 'style': style, 'image_type': image_type,
                    'model_hint': 'portrait', 'status': 'READY',
                    'person_name': person_name
                })
        else:
            # Lookup failed — fall back to SCENE, never generate random face
            print(f"[smart_prompts v3] Lookup failed for {person_name}, falling back to SCENE")
            scene_prompt, scene_style, scene_type = _gen_scene_prompt(found_companies, title, body_text)
            result.update({
                'prompt': scene_prompt, 'style': scene_style,
                'image_type': scene_type, 'model_hint': 'scene',
                'status': 'SCENE_FALLBACK', 'person_name': person_name
            })
        
        return result
    
    # ── VERSUS ────────────────────────────────────────────────
    if story_type == 'VERSUS':
        entities = found_companies if len(found_companies) >= 2 else found_people
        if len(entities) >= 2:
            prompt, style, image_type = _gen_versus_prompt(entities)
            result.update({
                'prompt': prompt, 'style': style, 'image_type': image_type,
                'model_hint': 'scene', 'status': 'READY'
            })
        else:
            prompt, style, image_type = _gen_scene_prompt(found_companies, title, body_text)
            result.update({
                'prompt': prompt, 'style': style, 'image_type': image_type,
                'model_hint': 'scene', 'status': 'READY'
            })
        return result
    
    # ── ALL OTHER TYPES → SCENE ───────────────────────────────
    prompt, style, image_type = _gen_scene_prompt(found_companies, title, body_text)
    result.update({
        'prompt': prompt, 'style': style, 'image_type': image_type,
        'model_hint': 'scene', 'status': 'READY'
    })
    return result


# ─── CLI: Review pending prompts ───────────────────────────────
def review_pending():
    """Interactive CLI to review pending prompts."""
    pending = _load_pending()
    items = pending.get("pending", [])
    
    if not items:
        print("No pending prompts to review.")
        return
    
    print(f"\n{'='*60}")
    print(f"PENDING PROMPTS: {len(items)} items")
    print(f"{'='*60}")
    
    approved = []
    for i, entry in enumerate(items):
        if entry.get('status') != 'PENDING':
            continue
        
        print(f"\n[{i+1}] {entry['person_name']} — {entry['title']}")
        print(f"    Prompt: {entry['suggested_prompt'][:120]}...")
        if entry.get('person_data'):
            print(f"    Appearance: {entry['person_data'].get('appearance', 'N/A')[:100]}")
        print(f"\n    [A]pprove  [E]dit  [S]kip to SCENE  [Q]uit")
        
        choice = input("    > ").strip().lower()
        
        if choice == 'a':
            entry['status'] = 'APPROVED'
            approved.append(entry)
            print(f"    ✓ Approved")
        elif choice == 'e':
            new_prompt = input("    New prompt: ").strip()
            if new_prompt:
                entry['suggested_prompt'] = new_prompt
                entry['status'] = 'APPROVED'
                approved.append(entry)
                print(f"    ✓ Edited and approved")
        elif choice == 's':
            entry['status'] = 'SKIPPED'
            print(f"    → Skipped (will use SCENE)")
        elif choice == 'q':
            break
    
    _save_pending(pending)
    
    if approved:
        print(f"\n{'='*60}")
        print(f"APPROVED: {len(approved)} prompts ready for generation")
        for entry in approved:
            print(f"  → {entry['person_name']}: {entry['suggested_prompt'][:80]}...")
    
    return approved


# ─── Standalone test ───────────────────────────────────────────
if __name__ == "__main__":
    test_cases = [
        # Known people
        ("Tim Cook reports $111B in Apple revenue", "Services hit $30.98B all-time."),
        ("Jensen Huang unveils Blackwell Ultra", "Nvidia CEO shows next-gen AI chip."),
        # Unknown people (not in registry)
        ("Saylor's never-sell doctrine, dead", "$12.54B Q1 loss on BTC crash. Now mulling BTC sales for divs."),
        ("Mark Cuban warns AI will kill 5 job categories", "Entry-level white collar first."),
        ("Jamie Dimon calls AI bigger than electricity", "JPMorgan deploys 2000 AI use cases."),
        # Non-person stories
        ("War Powers clock hits zero", "No authorization; ceasefire claim. Brent holds $108."),
        ("Solana launches $1M bug bounty", "Firedancer targets 1M TPS mainnet."),
        ("Fed holds rates steady at 5.5%", "Powell signals no cuts."),
    ]
    
    print("=" * 70)
    print("SMART PROMPTS v3 — Unknown Person Detection Test")
    print("=" * 70)
    
    for title, body in test_cases:
        result = generate_smart_prompt(title, body)
        print(f"\nTitle: {title}")
        print(f"  Status: {result['status']} | Type: {result['image_type']} | Model: {result['model_hint']}")
        print(f"  Person: {result.get('person_name', 'None')}")
        if result.get('review_entry'):
            print(f"  ** FLAGGED FOR REVIEW **")
        print(f"  Prompt: {result['prompt'][:100]}...")
        print("-" * 70)
