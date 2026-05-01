"""
image_dedup.py — TLW Image Variety Dedup
Tracks recent visual subjects and injects avoidance rules into prompts.
"""
import json, os, time, re
from datetime import datetime, timedelta
from collections import Counter

DATA_FILE = 'data/used_angles.json'
LOOKBACK_DAYS = 7
MAX_HISTORY = 50

SUBJECT_KEYWORDS = {
    'bull': ['bull', 'charging bull', 'bull statue'],
    'bitcoin_coin': ['bitcoin coin', 'btc coin', 'golden coin', 'crypto coin'],
    'server_rack': ['server rack', 'data center', 'server room'],
    'vault': ['vault', 'vault door', 'bank vault'],
    'chip': ['chip', 'semiconductor', 'gpu', 'processor'],
    'rocket': ['rocket', 'launch', 'spacex'],
    'building_aerial': ['aerial', 'building at night', 'headquarters', 'glass tower', 'skyscraper'],
    'globe': ['globe', 'earth', 'world', 'planet'],
    'podium': ['podium', 'press conference', 'microphones'],
    'boardroom': ['boardroom', 'conference table', 'conference room'],
    'eye': ['eye', 'iris', 'pupil', 'robotic eye'],
    'furnace': ['furnace', 'fire', 'flames', 'burning', 'molten'],
    'airplane': ['airplane', 'aircraft', 'plane', 'airline', 'tarmac'],
    'gas_pump': ['gas pump', 'fuel nozzle', 'gas station'],
    'gavel': ['gavel', 'courtroom', 'judge', 'court'],
    'portrait': ['close-up', 'closeup', 'face', 'portrait', 'expression', 'standing'],
    'versus_split': ['split frame', 'versus', 'face to face', 'opposite sides'],
    'coin_marble': ['coin on marble', 'coin on dark', 'pedestal'],
    'ship': ['ship', 'tanker', 'cargo', 'vessel'],
}

SUBJECT_DESCRIPTIONS = {
    'bull': 'bronze bulls or bull statues',
    'bitcoin_coin': 'bitcoin coins',
    'server_rack': 'server racks or data centers',
    'vault': 'vault doors',
    'chip': 'semiconductor chips or GPUs',
    'rocket': 'rocket launches',
    'building_aerial': 'aerial building shots or skyscrapers',
    'globe': 'globe or earth imagery',
    'podium': 'podium or press conference',
    'boardroom': 'boardroom scenes',
    'eye': 'robotic or AI eyes',
    'furnace': 'furnaces or fire scenes',
    'airplane': 'airplanes or airports',
    'gas_pump': 'gas pumps',
    'gavel': 'gavels or courtrooms',
    'portrait': 'person portraits or close-ups',
    'versus_split': 'split-frame versus shots',
    'coin_marble': 'coins on marble surfaces',
    'ship': 'ships or tankers',
}

def load_used_angles():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r') as f: return json.load(f)
    except: return []

def save_used_angles(angles):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(angles[-MAX_HISTORY:], f, indent=2)

def detect_subjects(prompt):
    prompt_lower = prompt.lower()
    return [subj for subj, keywords in SUBJECT_KEYWORDS.items()
            if any(kw in prompt_lower for kw in keywords)]

def save_used_angle(story_data, image_prompt, image_type='SCENE'):
    angles = load_used_angles()
    angles.append({
        'date': datetime.now().strftime('%Y-%m-%d'),
        'stat_hook': story_data.get('stat_hook', ''),
        'subjects': detect_subjects(image_prompt),
        'image_type': image_type,
        'prompt_snippet': image_prompt[:150],
    })
    save_used_angles(angles)
    print(f"[DEDUP] Saved: {detect_subjects(image_prompt)}")

def get_overused_subjects(days=LOOKBACK_DAYS, threshold=2):
    angles = load_used_angles()
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    recent = [a for a in angles if a.get('date', '') >= cutoff]
    subjects = []
    for a in recent: subjects.extend(a.get('subjects', []))
    counts = Counter(subjects)
    return [s for s, c in counts.items() if c >= threshold]

def get_avoidance_prompt(days=LOOKBACK_DAYS):
    overused = get_overused_subjects(days, threshold=2)
    if not overused: return ""
    descriptions = [SUBJECT_DESCRIPTIONS.get(s, s) for s in overused]
    return f" | AVOID these (used recently): {', '.join(descriptions)}"
