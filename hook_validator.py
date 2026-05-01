"""
hook_validator.py — TLW Hook Rules Enforcement
Import into research_agent.py to enforce character limits + hook mode variety.
"""
import json, os, hashlib
from collections import Counter

LIMITS = {'stat_hook': 7, 'sub_headline': 30, 'body_line_1': 35, 'body_line_2': 35}
HOOK_MODES = ['STAT', 'POWER', 'TENSION', 'NAME']

def detect_hook_mode(stat_hook):
    hook = stat_hook.strip().upper()
    if any(hook.startswith(c) for c in ['$', '+', '-']): return 'STAT'
    if sum(1 for c in hook if c.isdigit()) > len(hook) * 0.4: return 'STAT'
    if '?' in hook: return 'TENSION'
    words = hook.replace('.', '').split()
    if len(words) == 1 and hook.endswith('.'): return 'POWER'
    power_words = ['FIRED','BANNED','OPEN','DEAD','GONE','HACKED','SOLD','TRIAL',
                   'BLOCKED','KILLED','CRASHED','REPLACED','SPLIT','LOCKED','BROKE']
    if any(w in hook.replace('.','') for w in power_words): return 'POWER'
    if hook.replace(' ','').isalpha() and hook == hook.upper(): return 'NAME'
    return 'STAT'

def get_recent_modes(used_stories_path, lookback=5):
    if not os.path.exists(used_stories_path): return []
    try:
        with open(used_stories_path, 'r') as f:
            data = json.load(f)
        titles = data.get("titles", [])[-lookback:]
        # We can't detect mode from titles alone, so we track modes separately
        return data.get("recent_modes", [])[-lookback:]
    except: return []

def get_required_mode(used_stories_path):
    modes = get_recent_modes(used_stories_path)
    if len(modes) < 3: return None
    consecutive_stat = 0
    for m in reversed(modes):
        if m == 'STAT': consecutive_stat += 1
        else: break
    if consecutive_stat >= 3:
        for mode in ['POWER', 'TENSION', 'NAME']:
            if mode not in modes[-5:]: return mode
        return 'POWER'
    return None

def validate_character_limits(story):
    for field, limit in LIMITS.items():
        val = story.get(field, '')
        if len(val) > limit:
            print(f"[HOOK] Truncating {field}: '{val}' ({len(val)} > {limit})")
            truncated = val[:limit]
            last_space = truncated.rfind(' ')
            if last_space > limit * 0.5: truncated = truncated[:last_space]
            if field != 'stat_hook' and not truncated.endswith('.'): truncated += '.'
            story[field] = truncated
    return story

def validate_and_fix_story(story, used_stories_path='data/used_stories.json'):
    story = validate_character_limits(story)
    if 'stat_hook' in story:
        story['hook_mode'] = detect_hook_mode(story['stat_hook'])
        print(f"[HOOK] Mode: {story['hook_mode']} | Hook: '{story['stat_hook']}'")
    required = get_required_mode(used_stories_path)
    if required and story.get('hook_mode') != required:
        print(f"[HOOK] WARNING: Variety wants {required}, got {story.get('hook_mode')}")
    return story

def get_hook_variety_prompt_injection(used_stories_path='data/used_stories.json'):
    modes = get_recent_modes(used_stories_path)
    required = get_required_mode(used_stories_path)
    injection = ""
    if modes:
        injection += f"\nRecent hook modes (oldest->newest): {', '.join(modes[-5:])}"
    if required:
        injection += f"\nREQUIRED: Next story MUST use {required} mode. Do NOT use STAT."
    return injection
