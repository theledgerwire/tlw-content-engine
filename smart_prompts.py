"""
smart_prompts.py — TLW Entity-Aware Image Prompt Generator
Detects people/companies in stories, generates entity-specific image_angle prompts.

Usage in generate_image.py:
    from smart_prompts import maybe_enhance_image_angle
    
    # Before generating image, check if entity override is better:
    enhanced_angle = maybe_enhance_image_angle(TLW_STORY)
    if enhanced_angle:
        flux_prompt = enhanced_angle  # use entity-aware prompt instead of Claude's
"""
import json, os, random

REGISTRY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'entity_registry.json')
SUFFIX = "shallow depth of field, cinematic editorial photograph, deep navy and gold color palette, photorealistic, no text, no logos, no watermarks"

def load_registry():
    for p in [REGISTRY_PATH, 'data/entity_registry.json']:
        if os.path.exists(p):
            with open(p, 'r') as f: return json.load(f)
    print("[ENTITY] Registry not found"); return {'people': {}, 'companies': {}}

def _detect_mood(story):
    text = ' '.join([story.get(k,'') for k in ['stat_hook','sub_headline','body_line_1','body_line_2','title','summary']]).lower()
    neg = sum(1 for w in ['crash','kill','fire','sink','drop','fall','cut','ban','hack','breach','fail','dead','block','split','war','bankrupt','trial','sued','broke','layoff','sinks','plunge'] if w in text)
    pos = sum(1 for w in ['record','beat','smash','surge','soar','win','launch','grow','profit','boom','unlock','gain','rise','milestone','deal'] if w in text)
    if neg > pos: return 'negative'
    if pos > neg: return 'positive'
    return 'neutral'

def _classify(story):
    """Returns (type, entities). type = VERSUS/PORTRAIT/BRAND/SCENE"""
    registry = load_registry()
    text = ' '.join([story.get(k,'') for k in ['stat_hook','sub_headline','body_line_1','body_line_2','title','summary','keyword_fallback']]).lower()
    
    people = []
    for key, data in registry.get('people', {}).items():
        names = data.get('names', [key.replace('_',' ')])
        if any(n.lower() in text for n in names):
            people.append((key, data))
    
    companies = []
    for key, data in registry.get('companies', {}).items():
        names = data.get('names', [key])
        if any(n.lower() in text for n in names):
            companies.append((key, data))
    
    if len(people) >= 2: return 'VERSUS', people[:2]
    if len(people) == 1: return 'PORTRAIT', people
    if companies: return 'BRAND', companies[:1]
    return 'SCENE', []

def _versus_prompt(entities, mood):
    p1k, p1 = entities[0]
    p2k, p2 = entities[1]
    templates = [
        f"Extreme close-up split frame, {p1['appearance']} on the left with {p1.get('mood_negative','intense expression')}, {p2['appearance']} on the right with {p2.get('mood_negative','cold stare')}, a thin crack of golden light splitting the frame between them, {p1.get('lighting','dramatic side lighting')} on left, cool blue light on right, extreme {SUFFIX}",
        f"{p1['appearance']} in {p1.get('default_outfit','dark navy suit')} and {p2['appearance']} in {p2.get('default_outfit','dark navy suit')} standing on opposite sides of a dark marble conference table, not looking at each other, tense body language, dramatic golden window light between them, {SUFFIX}",
        f"{p1['appearance']} and {p2['appearance']} standing back to back in a dark corridor, arms crossed, looking away from each other, golden spotlight from above, {SUFFIX}",
    ]
    return random.choice(templates)

def _portrait_prompt(entities, mood):
    pk, p = entities[0]
    expr = p.get(f'mood_{mood}', p.get('mood_neutral', 'serious expression'))
    templates = [
        f"{p['appearance']}, {p.get('default_outfit','dark navy suit')}, {expr}, {p.get('default_setting','dark office')}, {p.get('lighting','dramatic side lighting')}, {SUFFIX}",
        f"Close-up portrait of {p['appearance']}, {expr}, dramatic golden side lighting casting deep shadows, dark blurred background, {SUFFIX}",
        f"{p['appearance']}, {p.get('default_outfit','dark navy suit')}, {expr}, standing alone in {p.get('default_setting','a dark room')}, {p.get('lighting','dramatic lighting')}, low-angle cinematic shot, {SUFFIX}",
    ]
    return random.choice(templates)

def _brand_prompt(entities, story):
    ck, c = entities[0]
    colors = c.get('color_code', 'gold and navy')
    style = c.get('visual_style', 'dramatic corporate imagery')
    alt_visuals = c.get('alt_visuals', [])
    
    if alt_visuals:
        chosen_alt = random.choice(alt_visuals)
        return f"{chosen_alt}, {colors}, dramatic golden side lighting, dark background, {SUFFIX}"
    return f"{style}, {colors}, dramatic golden lighting, {SUFFIX}"

def maybe_enhance_image_angle(story):
    """
    Check if story features a known entity. If yes, return an entity-aware
    image prompt. If no, return None (use Claude's original image_angle).
    """
    if not story: return None
    
    img_type, entities = _classify(story)
    mood = _detect_mood(story)
    
    if img_type == 'SCENE':
        print("[ENTITY] No known entity detected — using Claude's image_angle")
        return None
    
    print(f"[ENTITY] Detected: {img_type} | Entities: {[e[0] for e in entities]} | Mood: {mood}")
    
    if img_type == 'VERSUS':
        prompt = _versus_prompt(entities, mood)
    elif img_type == 'PORTRAIT':
        prompt = _portrait_prompt(entities, mood)
    elif img_type == 'BRAND':
        prompt = _brand_prompt(entities, story)
    else:
        return None
    
    print(f"[ENTITY] Generated prompt: {prompt[:100]}...")
    return prompt
