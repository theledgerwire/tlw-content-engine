# visual_identity.py — TLW Visual Identity Router
# v1.0 — Ensures every card is instantly recognizable without reading text
#
# Purpose: Maps known companies, entities, and story types to their most
# recognizable visual elements (logos, products, faces, buildings).
# Plugs into generate_image.py's prompt generation pipeline.
#
# Usage in generate_image.py:
#   from visual_identity import get_visual_anchor, enrich_prompt
#
# The visual anchor is prepended to the AI image prompt so the generated
# image features the recognizable element prominently.

import re

# ── VISUAL IDENTITY REGISTRY ──────────────────────────────────────
# Each entry maps a trigger keyword to:
#   - "visual": The specific visual element to include in the prompt
#   - "type": LOGO | PERSON | PRODUCT | BUILDING | SCENE
#   - "model": Preferred generation model (nano_banana for people, grok for objects)
#
# RULE: If someone can't identify the story from the image alone,
# the visual anchor is wrong.

VISUAL_REGISTRY = {

    # ── BIG TECH ──────────────────────────────────────────────────
    "nvidia": {
        "visual": "Dramatic closeup portrait of Jensen Huang, silver-gray hair, glasses, black leather jacket, confident intense expression, Nvidia green logo glowing subtly in dark background behind him, cinematic editorial photography, dark moody lighting",
        "type": "PERSON",
        "model": "nano_banana",
        "triggers": ["nvidia", "nvda", "jensen huang", "jensen", "gpu", "blackwell", "vera rubin", "grace"],
    },
    "apple": {
        "visual": "Apple logo glowing on a dark stage, Apple Park headquarters circular building aerial view",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["apple", "aapl", "tim cook", "iphone", "wwdc", "siri", "vision pro"],
    },
    "google": {
        "visual": "Dramatic closeup portrait of Sundar Pichai, dark hair, glasses, calm composed expression, dark blazer, Google colored G logo glowing subtly in dark background behind him, cinematic editorial photography, dark moody lighting",
        "type": "PERSON",
        "model": "nano_banana",
        "triggers": ["google", "googl", "alphabet", "sundar pichai", "sundar", "gemini", "deepmind", "android", "antigravity"],
    },
    "microsoft": {
        "visual": "Dramatic closeup portrait of Satya Nadella, bald head, glasses, warm determined expression, dark suit, Microsoft four-square logo glowing subtly in dark background behind him, cinematic editorial photography, dark moody lighting",
        "type": "PERSON",
        "model": "nano_banana",
        "triggers": ["microsoft", "msft", "satya nadella", "nadella", "azure", "copilot", "windows"],
    },
    "meta": {
        "visual": "Dramatic closeup portrait of Mark Zuckerberg, short brown hair, intense focused expression, gray t-shirt, Meta infinity loop logo glowing subtly in dark background behind him, cinematic editorial photography, dark moody lighting",
        "type": "PERSON",
        "model": "nano_banana",
        "triggers": ["meta", "zuckerberg", "facebook", "instagram", "whatsapp", "threads", "reality labs"],
    },
    "amazon": {
        "visual": "Dramatic closeup portrait of Andy Jassy, curly dark hair, intense expression, button-down shirt, Amazon smile logo glowing subtly in dark background behind him, cinematic editorial photography, dark moody lighting",
        "type": "PERSON",
        "model": "nano_banana",
        "triggers": ["amazon", "amzn", "aws", "andy jassy", "bezos", "prime"],
    },
    "tesla": {
        "visual": "Tesla Model S or Cybertruck with Tesla T logo prominently visible, dramatic lighting",
        "type": "PRODUCT",
        "model": "grok",
        "triggers": ["tesla", "tsla", "cybertruck", "model s", "model 3", "model y", "fsd"],
    },

    # ── AI COMPANIES ──────────────────────────────────────────────
    "openai": {
        "visual": "Dramatic closeup portrait of Sam Altman, brown curly hair, calm determined expression, dark blazer, OpenAI hexagonal logo glowing subtly in dark background behind him, cinematic editorial photography, dark moody lighting",
        "type": "PERSON",
        "model": "nano_banana",
        "triggers": ["openai", "sam altman", "altman", "chatgpt", "gpt-5", "gpt-6", "dall-e"],
    },
    "anthropic": {
        "visual": "Dramatic closeup portrait of Dario Amodei, dark curly hair, thoughtful expression, casual shirt, Anthropic logo glowing subtly in dark background behind him, cinematic editorial photography, dark moody lighting",
        "type": "PERSON",
        "model": "nano_banana",
        "triggers": ["anthropic", "dario amodei", "amodei", "claude", "claude mythos"],
    },
    "xai": {
        "visual": "Dramatic closeup portrait of Elon Musk, short dark hair, stern intense expression, dark crew neck, xAI logo glowing subtly in dark background behind him, cinematic editorial photography, dark moody lighting",
        "type": "PERSON",
        "model": "nano_banana",
        "triggers": ["xai", "grok ai", "elon musk ai"],
    },

    # ── SEMICONDUCTORS ────────────────────────────────────────────
    "amd": {
        "visual": "AMD Ryzen or EPYC processor chip closeup with AMD red logo visible on the chip, dramatic macro photography",
        "type": "PRODUCT",
        "model": "grok",
        "triggers": ["amd", "lisa su", "ryzen", "epyc", "radeon", "venice"],
    },
    "tsmc": {
        "visual": "TSMC semiconductor fabrication facility, clean room with workers in white bunny suits, TSMC logo on building",
        "type": "BUILDING",
        "model": "grok",
        "triggers": ["tsmc", "taiwan semiconductor"],
    },
    "intel": {
        "visual": "Intel processor chip with Intel blue logo visible, or Intel headquarters building with logo",
        "type": "PRODUCT",
        "model": "grok",
        "triggers": ["intel", "intc", "pat gelsinger"],
    },
    "arm": {
        "visual": "Dramatic closeup portrait of Rene Haas, professional expression, dark blazer, Arm logo glowing subtly in dark background behind him, cinematic editorial photography, dark moody lighting",
        "type": "PERSON",
        "model": "nano_banana",
        "triggers": ["arm holdings", "arm ipo", "rene haas"],
    },
    "qualcomm": {
        "visual": "Qualcomm Snapdragon chip closeup with Qualcomm logo, or mobile devices powered by Snapdragon",
        "type": "PRODUCT",
        "model": "grok",
        "triggers": ["qualcomm", "snapdragon", "qcom"],
    },
    "sk_hynix": {
        "visual": "SK Hynix HBM memory chips stacked in a row with SK Hynix blue branding visible, macro semiconductor photography",
        "type": "PRODUCT",
        "model": "grok",
        "triggers": ["sk hynix", "hynix", "hbm", "memory chip"],
    },
    "samsung_semi": {
        "visual": "Samsung semiconductor factory floor with Samsung blue logo visible, workers in clean room suits",
        "type": "BUILDING",
        "model": "grok",
        "triggers": ["samsung chip", "samsung semiconductor", "samsung foundry", "samsung factory", "samsung workers"],
    },
    "marvell": {
        "visual": "Dramatic closeup portrait of Matt Murphy, confident expression, dark suit, Marvell Technology logo glowing subtly in dark background behind him, cinematic editorial photography, dark moody lighting",
        "type": "PERSON",
        "model": "nano_banana",
        "triggers": ["marvell", "matt murphy"],
    },
    "cerebras": {
        "visual": "Cerebras wafer-scale chip held in two hands showing its massive size compared to a dinner plate, dramatic lighting",
        "type": "PRODUCT",
        "model": "grok",
        "triggers": ["cerebras", "wafer scale", "dinner plate chip"],
    },

    # ── FINANCE / BANKING ─────────────────────────────────────────
    "jpmorgan": {
        "visual": "Dramatic closeup portrait of Jamie Dimon, silver hair, strong jaw, commanding expression, power suit with tie, JPMorgan Chase blue logo glowing subtly in dark background behind him, cinematic editorial photography, dark moody lighting",
        "type": "PERSON",
        "model": "nano_banana",
        "triggers": ["jpmorgan", "jp morgan", "jamie dimon", "dimon", "chase"],
    },
    "goldman": {
        "visual": "Goldman Sachs headquarters building in New York, Goldman Sachs blue logo on stone facade, corporate power",
        "type": "BUILDING",
        "model": "grok",
        "triggers": ["goldman sachs", "goldman", "david solomon"],
    },
    "blackrock": {
        "visual": "Dramatic closeup portrait of Larry Fink, gray hair, glasses, serious expression, dark suit, BlackRock logo glowing subtly in dark background behind him, cinematic editorial photography, dark moody lighting",
        "type": "PERSON",
        "model": "nano_banana",
        "triggers": ["blackrock", "larry fink", "fink"],
    },
    "morgan_stanley": {
        "visual": "Morgan Stanley headquarters building with Morgan Stanley logo in Times Square, corporate finance setting",
        "type": "BUILDING",
        "model": "grok",
        "triggers": ["morgan stanley"],
    },

    # ── ENTERPRISE / SAAS ─────────────────────────────────────────
    "salesforce": {
        "visual": "Dramatic closeup portrait of Marc Benioff, gray beard, glasses, confident expression, blazer, Salesforce cloud logo glowing subtly in dark background behind him, cinematic editorial photography, dark moody lighting",
        "type": "PERSON",
        "model": "nano_banana",
        "triggers": ["salesforce", "marc benioff", "benioff", "agentforce", "dreamforce"],
    },
    "snowflake": {
        "visual": "Snowflake logo prominently displayed on a cloud computing data center backdrop, blue and white tones",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["snowflake", "snow"],
    },
    "oracle": {
        "visual": "Dramatic closeup portrait of Larry Ellison, gray hair, intense expression, dark blazer, Oracle red logo glowing subtly in dark background behind him, cinematic editorial photography, dark moody lighting",
        "type": "PERSON",
        "model": "nano_banana",
        "triggers": ["oracle", "orcl", "larry ellison", "ellison"],
    },
    "workday": {
        "visual": "Workday logo on a modern glass office building, enterprise software campus, blue sky",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["workday", "wday"],
    },
    "intuit": {
        "visual": "TurboTax logo on a computer screen with tax documents, or Intuit headquarters",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["intuit", "turbotax", "quickbooks"],
    },
    "kpmg": {
        "visual": "KPMG blue logo on a modern glass office tower, suited consultants in a corporate boardroom",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["kpmg"],
    },

    # ── SPACE / DEFENSE ───────────────────────────────────────────
    "spacex": {
        "visual": "SpaceX Falcon rocket on launch pad at Cape Canaveral, SpaceX logo on the rocket body, dramatic sky",
        "type": "PRODUCT",
        "model": "grok",
        "triggers": ["spacex", "starlink", "starship", "falcon"],
    },
    "anduril": {
        "visual": "Anduril autonomous defense drone in flight over a military testing ground, modern defense technology",
        "type": "PRODUCT",
        "model": "grok",
        "triggers": ["anduril", "palmer luckey"],
    },
    "boeing": {
        "visual": "Boeing 737 or 787 Dreamliner with Boeing blue logo visible on fuselage, on a runway at golden hour",
        "type": "PRODUCT",
        "model": "grok",
        "triggers": ["boeing", "737", "787", "dreamliner"],
    },

    # ── SOCIAL / CONSUMER ─────────────────────────────────────────
    "reddit": {
        "visual": "Reddit orange alien Snoo logo on a smartphone screen, social media community forum aesthetic",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["reddit", "rddt"],
    },
    "tiktok": {
        "visual": "TikTok logo glowing on a dark smartphone screen, or TikTok neon sign, vibrant colors",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["tiktok", "bytedance"],
    },
    "netflix": {
        "visual": "Netflix red N logo glowing on a dark screen, home entertainment streaming setup",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["netflix", "nflx"],
    },
    "spotify": {
        "visual": "Spotify green logo on a dark background, headphones and music streaming interface",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["spotify", "spot"],
    },

    # ── CRYPTO ────────────────────────────────────────────────────
    "bitcoin": {
        "visual": "Physical gold Bitcoin coin closeup, reflective surface, dramatic lighting, cryptocurrency",
        "type": "PRODUCT",
        "model": "grok",
        "triggers": ["bitcoin", "btc"],
    },
    "ethereum": {
        "visual": "Ethereum diamond logo glowing in purple and blue, digital blockchain visualization",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["ethereum", "eth"],
    },
    "solana": {
        "visual": "Solana gradient logo glowing in purple-green-teal, blockchain network visualization, fast and modern",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["solana", "sol"],
    },
    "coinbase": {
        "visual": "Coinbase blue circle logo on a trading terminal screen, cryptocurrency exchange",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["coinbase", "coin"],
    },
    "binance": {
        "visual": "Binance yellow diamond logo on a dark crypto trading terminal, BNB coin, exchange interface",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["binance", "bnb", "cz binance"],
    },
    "grayscale": {
        "visual": "Grayscale Investments logo on a dark financial terminal, Bitcoin ETF trading screen, institutional crypto",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["grayscale", "gbtc", "crypto etf", "bitcoin etf", "spot etf"],
    },

    # ── MARKET INDICES ────────────────────────────────────────────
    "nasdaq": {
        "visual": "Nasdaq tower in Times Square New York City lit up at night, massive digital stock ticker display, iconic market landmark",
        "type": "BUILDING",
        "model": "grok",
        "triggers": ["nasdaq", "qqq", "nasdaq composite", "nasdaq all-time"],
    },
    "sp500": {
        "visual": "Wall Street stock exchange trading floor with traders and green screens, bull statue, financial district",
        "type": "SCENE",
        "model": "grok",
        "triggers": ["s&p 500", "s&p", "sp500", "spx", "wall street rally"],
    },
    "dow": {
        "visual": "New York Stock Exchange building exterior with American flags, Wall Street sign, financial district",
        "type": "BUILDING",
        "model": "grok",
        "triggers": ["dow jones", "djia", "dow industrials"],
    },

    # ── ECONOMIC INDICATORS ───────────────────────────────────────
    "inflation": {
        "visual": "Grocery store aisle with price tags showing high prices, shopping cart, consumer inflation, everyday life impact",
        "type": "SCENE",
        "model": "grok",
        "triggers": ["cpi", "pce", "inflation", "consumer prices", "price index"],
    },
    "gdp": {
        "visual": "US Capitol Building with economic data charts overlaid, GDP growth indicator, American economy",
        "type": "BUILDING",
        "model": "grok",
        "triggers": ["gdp ", "economic growth", "gdp cut", "gdp revised"],
    },
    "jobs": {
        "visual": "Long line of job seekers outside a career fair or unemployment office, diverse professionals waiting",
        "type": "SCENE",
        "model": "grok",
        "triggers": ["jobs report", "unemployment", "payrolls", "jobless claims", "hiring freeze"],
    },

    # ── ADDITIONAL TECH ───────────────────────────────────────────
    "wix": {
        "visual": "Wix logo on a modern office building, website builder interface on screen, tech layoffs empty desks",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["wix"],
    },
    "uber": {
        "visual": "Uber logo on a smartphone screen in a car, rideshare app interface, urban night setting",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["uber"],
    },
    "airbnb": {
        "visual": "Airbnb belo logo on a smartphone, beautiful vacation rental in background, travel",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["airbnb", "abnb"],
    },
    "palantir": {
        "visual": "Palantir logo on dark screens with data visualization dashboards, defense intelligence analytics",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["palantir", "pltr"],
    },
    "databricks": {
        "visual": "Databricks orange logo on a data engineering dashboard screen, modern cloud office",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["databricks"],
    },
    "stripe": {
        "visual": "Stripe purple gradient logo on a payment processing terminal, fintech, developer-first",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["stripe"],
    },
    "robinhood": {
        "visual": "Robinhood green feather logo on a trading app screen, retail investor, mobile trading",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["robinhood", "hood"],
    },

    # ── GOVERNMENT / INSTITUTIONS ─────────────────────────────────
    "fed": {
        "visual": "Federal Reserve building in Washington DC, neoclassical columns, American flag, institutional power",
        "type": "BUILDING",
        "model": "grok",
        "triggers": ["federal reserve", "the fed", "fomc", "rate cut", "rate hike", "rate hold"],
    },
    "fed_chair": {
        "visual": "Dramatic closeup portrait of Federal Reserve Chair at microphones, serious measured expression, dark suit, Federal Reserve seal glowing subtly in dark background behind them, cinematic editorial photography, dark moody lighting",
        "type": "PERSON",
        "model": "nano_banana",
        "triggers": ["warsh", "powell", "fed chair"],
    },
    "sec": {
        "visual": "SEC headquarters building in Washington DC with SEC seal, regulatory authority, government building",
        "type": "BUILDING",
        "model": "grok",
        "triggers": ["sec ", "securities and exchange", "gary gensler", "sec chair"],
    },
    "congress": {
        "visual": "US Capitol Building dome in Washington DC, dramatic sky, American governance",
        "type": "BUILDING",
        "model": "grok",
        "triggers": ["congress", "senate", "house bill", "legislation", "clarity act"],
    },

    # ── AUTOMOTIVE ────────────────────────────────────────────────
    "rivian": {
        "visual": "Rivian R1T electric truck on a rugged outdoor road, Rivian compass logo visible",
        "type": "PRODUCT",
        "model": "grok",
        "triggers": ["rivian", "rivn"],
    },

    # ── CONSULTING / BIG 4 ────────────────────────────────────────
    "deloitte": {
        "visual": "Deloitte green dot logo on a modern glass office tower, consulting firm headquarters",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["deloitte"],
    },
    "mckinsey": {
        "visual": "McKinsey & Company logo on a corporate office entrance, blue and white, consulting",
        "type": "LOGO",
        "model": "grok",
        "triggers": ["mckinsey"],
    },
}


# ── FACE REGISTRY ─────────────────────────────────────────────────
# Closeup face descriptions for split-screen versus compositions.
# These describe the PERSON only — composition/lighting added by get_versus_prompt().

FACE_REGISTRY = {
    # Tech CEOs
    "elon_musk":      {"face": "Elon Musk closeup portrait, short dark hair, stern intense expression, dark crew neck", "side": "left"},
    "sam_altman":     {"face": "Sam Altman closeup portrait, brown curly hair, calm determined expression, dark sweater", "side": "right"},
    "jensen_huang":   {"face": "Jensen Huang closeup portrait, silver-gray hair, glasses, black leather jacket, confident", "side": "left"},
    "sundar_pichai":  {"face": "Sundar Pichai closeup portrait, dark hair, glasses, calm composed expression, dark blazer", "side": "left"},
    "satya_nadella":  {"face": "Satya Nadella closeup portrait, bald, glasses, warm expression, dark suit", "side": "left"},
    "mark_zuckerberg":{"face": "Mark Zuckerberg closeup portrait, short brown hair, intense focused expression, gray t-shirt", "side": "left"},
    "tim_cook":       {"face": "Tim Cook closeup portrait, silver hair, glasses, calm serious expression, dark blazer", "side": "left"},
    "lisa_su":        {"face": "Lisa Su closeup portrait, dark hair, confident expression, professional blazer", "side": "left"},
    "dario_amodei":   {"face": "Dario Amodei closeup portrait, dark curly hair, thoughtful expression, casual shirt", "side": "left"},
    "andy_jassy":     {"face": "Andy Jassy closeup portrait, curly dark hair, bald top, intense expression, button-down shirt", "side": "left"},
    
    # Finance
    "jamie_dimon":    {"face": "Jamie Dimon closeup portrait, silver hair, strong jaw, power suit with tie, commanding", "side": "left"},
    "larry_fink":     {"face": "Larry Fink closeup portrait, gray hair, glasses, serious expression, dark suit", "side": "left"},
    "david_solomon":  {"face": "David Solomon closeup portrait, bald, confident expression, dark suit with tie", "side": "left"},
    "warren_buffett": {"face": "Warren Buffett closeup portrait, white hair, glasses, warm knowing smile, suit", "side": "left"},
    
    # Government
    "trump":          {"face": "Donald Trump closeup portrait, blonde hair, red tie, stern powerful expression, dark suit", "side": "left"},
    "powell":         {"face": "Jerome Powell closeup portrait, gray hair, serious measured expression, dark suit with tie", "side": "right"},
    "warsh":          {"face": "Kevin Warsh closeup portrait, dark hair, clean-cut, serious expression, dark suit", "side": "right"},
    "gensler":        {"face": "Gary Gensler closeup portrait, balding gray hair, stern regulatory expression, suit", "side": "left"},
    
    # Other
    "palmer_luckey":  {"face": "Palmer Luckey closeup portrait, curly brown hair, Hawaiian shirt, energetic expression", "side": "left"},
}


# ── VERSUS PAIR REGISTRY ──────────────────────────────────────────
# Known conflict/comparison pairs. Each entry defines the two faces
# and the visual divider style.
#
# "divider": lightning | fire | crack | vs_badge | light_beam

VERSUS_PAIRS = {
    "musk_altman": {
        "left": "elon_musk",
        "right": "sam_altman",
        "divider": "lightning",
        "tint_left": "dark navy blue",
        "tint_right": "dark teal green",
        "triggers": [
            ("musk", "altman"), ("musk", "openai"), ("elon", "sam altman"),
            ("xai", "openai"), ("musk", "chatgpt"), ("tesla", "openai"),
        ],
    },
    "musk_zuckerberg": {
        "left": "elon_musk",
        "right": "mark_zuckerberg",
        "divider": "fire",
        "tint_left": "dark navy",
        "tint_right": "dark blue",
        "triggers": [
            ("musk", "zuckerberg"), ("musk", "meta"), ("tesla", "meta"),
            ("x ", "threads"), ("twitter", "meta"),
        ],
    },
    "trump_powell": {
        "left": "trump",
        "right": "powell",
        "divider": "fire",
        "tint_left": "warm red-orange",
        "tint_right": "cold steel blue",
        "triggers": [
            ("trump", "powell"), ("trump", "fed"), ("president", "fed chair"),
            ("white house", "federal reserve"),
        ],
    },
    "trump_warsh": {
        "left": "trump",
        "right": "warsh",
        "divider": "light_beam",
        "tint_left": "warm gold",
        "tint_right": "cool navy",
        "triggers": [
            ("trump", "warsh"), ("president", "warsh"),
        ],
    },
    "openai_anthropic": {
        "left": "sam_altman",
        "right": "dario_amodei",
        "divider": "lightning",
        "tint_left": "dark green",
        "tint_right": "dark purple",
        "triggers": [
            ("openai", "anthropic"), ("altman", "amodei"),
            ("chatgpt", "claude"), ("gpt", "claude"),
        ],
    },
    "openai_google": {
        "left": "sam_altman",
        "right": "sundar_pichai",
        "divider": "lightning",
        "tint_left": "dark green",
        "tint_right": "dark blue",
        "triggers": [
            ("openai", "google"), ("chatgpt", "gemini"),
            ("altman", "pichai"), ("gpt", "gemini"),
        ],
    },
    "nvidia_amd": {
        "left": "jensen_huang",
        "right": "lisa_su",
        "divider": "lightning",
        "tint_left": "nvidia green tint",
        "tint_right": "amd red tint",
        "triggers": [
            ("nvidia", "amd"), ("jensen", "lisa su"),
            ("nvda", "amd"), ("blackwell", "epyc"),
        ],
    },
    "microsoft_google": {
        "left": "satya_nadella",
        "right": "sundar_pichai",
        "divider": "lightning",
        "tint_left": "azure blue",
        "tint_right": "google blue-green",
        "triggers": [
            ("microsoft", "google"), ("nadella", "pichai"),
            ("copilot", "gemini"), ("azure", "google cloud"),
            ("bing", "google search"),
        ],
    },
    "apple_google": {
        "left": "tim_cook",
        "right": "sundar_pichai",
        "divider": "light_beam",
        "tint_left": "silver white",
        "tint_right": "dark blue",
        "triggers": [
            ("apple", "google"), ("cook", "pichai"),
            ("siri", "gemini"), ("ios", "android"),
        ],
    },
    "dimon_fink": {
        "left": "jamie_dimon",
        "right": "larry_fink",
        "divider": "crack",
        "tint_left": "jpmorgan blue",
        "tint_right": "blackrock dark",
        "triggers": [
            ("jpmorgan", "blackrock"), ("dimon", "fink"),
            ("chase", "blackrock"),
        ],
    },
    "musk_pichai": {
        "left": "elon_musk",
        "right": "sundar_pichai",
        "divider": "lightning",
        "tint_left": "dark navy",
        "tint_right": "dark teal",
        "triggers": [
            ("musk", "google"), ("musk", "pichai"),
            ("xai", "gemini"), ("grok", "gemini"),
        ],
    },
    "spacex_openai_ipo": {
        "left": "elon_musk",
        "right": "sam_altman",
        "divider": "vs_badge",
        "tint_left": "dark navy",
        "tint_right": "dark green",
        "triggers": [
            ("spacex ipo", "openai ipo"), ("spacex", "openai ipo"),
        ],
    },
}


# ── VERSUS DETECTION ──────────────────────────────────────────────

def detect_versus(story_data):
    """
    Detect if a story involves two opposing/compared entities.
    Returns (pair_key, pair_entry) or (None, None).
    
    Checks all text fields for co-occurrence of trigger pairs.
    """
    fields = []
    if isinstance(story_data, dict):
        for key in ["stat_hook", "sub_headline", "title", "summary",
                     "body_line_1", "body_line_2", "tagline", "keyword_fallback"]:
            val = story_data.get(key, "")
            if val:
                fields.append(val)
    search_text = _normalize(" ".join(fields))
    
    # Check each versus pair — longer trigger pairs first
    for pair_key, pair in VERSUS_PAIRS.items():
        for trigger_a, trigger_b in pair["triggers"]:
            ta = trigger_a.lower()
            tb = trigger_b.lower()
            
            # Both triggers must appear in the story text
            a_found = ta in search_text
            b_found = tb in search_text
            
            if a_found and b_found:
                print(f"[VERSUS] Matched: {pair_key} ('{trigger_a}' + '{trigger_b}')")
                return pair_key, pair
    
    return None, None


def get_versus_prompt(story_data):
    """
    Build a split-screen face-off image prompt for a versus story.
    Returns the full prompt string, or empty string if not a versus story.
    """
    pair_key, pair = detect_versus(story_data)
    if not pair:
        return ""
    
    left_key = pair["left"]
    right_key = pair["right"]
    divider = pair.get("divider", "lightning")
    tint_left = pair.get("tint_left", "dark navy blue")
    tint_right = pair.get("tint_right", "dark teal")
    
    left_face = FACE_REGISTRY.get(left_key, {}).get("face", "man in dark suit, serious expression")
    right_face = FACE_REGISTRY.get(right_key, {}).get("face", "man in dark suit, determined expression")
    
    # Divider style descriptions
    divider_styles = {
        "lightning":  "electric blue-white lightning bolt crackling vertically between them, energy sparks",
        "fire":       "vertical line of fire and glowing embers between them, orange-red sparks rising",
        "crack":      "jagged golden crack splitting between them, fractured glass effect",
        "vs_badge":   "glowing 'VS' text between them, competitive energy, bright white divider line",
        "light_beam": "sharp vertical beam of white light between them, clean dramatic separation",
    }
    divider_desc = divider_styles.get(divider, divider_styles["lightning"])
    
    prompt = (
        f"Dramatic split-screen portrait, "
        f"left side: {left_face}, {tint_left} background tone, "
        f"right side: {right_face}, {tint_right} background tone, "
        f"{divider_desc} dividing the frame vertically down the center, "
        f"both faces in sharp dramatic closeup filling their half of the frame, "
        f"cinematic editorial photography, high contrast, intense mood, "
        f"dark atmospheric background, photorealistic faces, "
        f"shallow depth of field, 1:1 square format"
    )
    
    print(f"[VERSUS] Built split-screen prompt: {prompt[:100]}...")
    return prompt


def get_versus_prompt_portrait(story_data):
    """
    Same as get_versus_prompt but for 4:5 portrait (Instagram) format.
    """
    pair_key, pair = detect_versus(story_data)
    if not pair:
        return ""
    
    left_key = pair["left"]
    right_key = pair["right"]
    divider = pair.get("divider", "lightning")
    tint_left = pair.get("tint_left", "dark navy blue")
    tint_right = pair.get("tint_right", "dark teal")
    
    left_face = FACE_REGISTRY.get(left_key, {}).get("face", "man in dark suit, serious expression")
    right_face = FACE_REGISTRY.get(right_key, {}).get("face", "man in dark suit, determined expression")
    
    divider_styles = {
        "lightning":  "electric blue-white lightning bolt crackling vertically between them, energy sparks",
        "fire":       "vertical line of fire and glowing embers between them, orange-red sparks rising",
        "crack":      "jagged golden crack splitting between them, fractured glass effect",
        "vs_badge":   "glowing 'VS' text between them, competitive energy, bright white divider line",
        "light_beam": "sharp vertical beam of white light between them, clean dramatic separation",
    }
    divider_desc = divider_styles.get(divider, divider_styles["lightning"])
    
    prompt = (
        f"Dramatic split-screen portrait, vertical 4:5 format, "
        f"left side: {left_face}, {tint_left} background tone, "
        f"right side: {right_face}, {tint_right} background tone, "
        f"{divider_desc} dividing the frame vertically down the center, "
        f"both faces in dramatic closeup from forehead to chin filling their half, "
        f"faces positioned in upper two-thirds leaving bottom third dark for text overlay, "
        f"cinematic editorial photography, high contrast, intense mood, "
        f"dark atmospheric background, photorealistic faces, "
        f"shallow depth of field, 4:5 portrait format"
    )
    
    return prompt

def _normalize(text):
    """Lowercase and clean text for matching."""
    return re.sub(r'[^\w\s]', ' ', text.lower())


def detect_entity(story_data):
    """
    Detect the primary entity in a story for visual routing.
    Returns the registry key and entry, or (None, None) if no match.
    
    Checks: stat_hook, sub_headline, title, summary, body lines.
    Priority: first match wins, longer triggers checked first.
    """
    # Build search text from all available story fields
    fields = []
    if isinstance(story_data, dict):
        for key in ["stat_hook", "sub_headline", "title", "summary", 
                     "body_line_1", "body_line_2", "tagline", "keyword_fallback"]:
            val = story_data.get(key, "")
            if val:
                fields.append(val)
    search_text = _normalize(" ".join(fields))
    
    # Build flat list of (trigger, registry_key, entry) sorted by trigger length DESC
    # Longer triggers match first to avoid false positives (e.g., "arm" matching "farmer")
    all_triggers = []
    for reg_key, entry in VISUAL_REGISTRY.items():
        for trigger in entry["triggers"]:
            all_triggers.append((trigger.lower(), reg_key, entry))
    
    all_triggers.sort(key=lambda x: len(x[0]), reverse=True)
    
    for trigger, reg_key, entry in all_triggers:
        # Word boundary check for short triggers (≤4 chars) to avoid false matches
        if len(trigger) <= 4:
            pattern = r'\b' + re.escape(trigger) + r'\b'
            if re.search(pattern, search_text):
                return reg_key, entry
        else:
            if trigger in search_text:
                return reg_key, entry
    
    return None, None


def detect_entity_from_text(title, summary=""):
    """Convenience wrapper for when you only have title + summary strings."""
    return detect_entity({
        "title": title,
        "summary": summary,
        "stat_hook": "",
        "sub_headline": title,
    })


# ── PROMPT ENRICHMENT ─────────────────────────────────────────────

def get_visual_anchor(story_data):
    """
    Returns the visual anchor string to prepend to image prompts.
    Checks VERSUS first (split-screen), then single entity.
    Returns empty string if nothing detected.
    """
    # Check versus first — split-screen face-offs take priority
    versus_prompt = get_versus_prompt(story_data)
    if versus_prompt:
        return versus_prompt
    
    # Fall through to single entity
    reg_key, entry = detect_entity(story_data)
    if entry:
        print(f"[VISUAL ID] Matched: {reg_key} → {entry['type']} → {entry['visual'][:60]}...")
        return entry["visual"]
    return ""


def get_preferred_model(story_data):
    """
    Returns the preferred image model for this story's entity.
    'nano_banana' for people/faces, 'grok' for objects/logos/buildings.
    Returns None if no entity detected (use default routing).
    """
    reg_key, entry = detect_entity(story_data)
    if entry:
        return entry.get("model", "grok")
    return None


def enrich_prompt(base_prompt, story_data):
    """
    Prepend visual anchor to an existing image prompt.
    If the base prompt already mentions the entity's key visual, skip.
    """
    anchor = get_visual_anchor(story_data)
    if not anchor:
        return base_prompt
    
    # Don't duplicate if the prompt already has the key visual
    anchor_words = set(_normalize(anchor).split())
    prompt_words = set(_normalize(base_prompt).split())
    overlap = len(anchor_words & prompt_words)
    
    if overlap > len(anchor_words) * 0.5:
        print(f"[VISUAL ID] Prompt already contains entity visual, skipping enrichment")
        return base_prompt
    
    enriched = f"{anchor}, {base_prompt}"
    print(f"[VISUAL ID] Enriched prompt: {enriched[:100]}...")
    return enriched


def get_model_override(story_data):
    """
    Returns image type override for generate_image.py model routing.
    VERSUS → always PORTRAIT (Nano Banana for faces).
    Maps visual identity types to the _CURRENT_IMAGE_TYPE values.
    """
    # Versus stories always need Nano Banana for face quality
    pair_key, pair = detect_versus(story_data)
    if pair:
        print(f"[VERSUS] Model override: PORTRAIT (split-screen face-off)")
        return "PORTRAIT"
    
    reg_key, entry = detect_entity(story_data)
    if not entry:
        return None
    
    vtype = entry.get("type", "")
    if vtype == "PERSON":
        return "PORTRAIT"  # Routes to Nano Banana
    else:
        return "SCENE"  # Routes to Grok
    

# ── INTEGRATION GUIDE ─────────────────────────────────────────────
# 
# In generate_image.py, update generate_flux_prompt():
#
#   from visual_identity import get_visual_anchor, enrich_prompt, get_model_override
#
#   def generate_flux_prompt(title, summary, style=None, force_people=False):
#       # NEW: Check visual identity first
#       if TLW_STORY:
#           anchor = get_visual_anchor(TLW_STORY)
#           if anchor:
#               # Use the visual anchor as the primary prompt
#               avoid = ""
#               if IMAGE_DEDUP_AVAILABLE:
#                   try: avoid = get_avoidance_prompt()
#                   except: pass
#               return f"{anchor}, {style['flux_style']}{avoid}"
#
#       # ... rest of existing logic ...
#
# In get_photo(), update model routing:
#
#       # NEW: Check visual identity for model routing
#       if TLW_STORY:
#           from visual_identity import get_model_override
#           override = get_model_override(TLW_STORY)
#           if override:
#               _CURRENT_IMAGE_TYPE = override
#               print(f"[VISUAL ID] Model override: {override}")


# ── TESTING ───────────────────────────────────────────────────────
if __name__ == "__main__":
    
    # ── Single entity tests ──
    test_stories = [
        {"title": "SK Hynix joins trillion club", "stat_hook": "+250%", "sub_headline": "SK Hynix joins trillion club", "summary": "Memory is the new oil"},
        {"title": "Jamie Dimon goes hunting again", "stat_hook": "$20B", "sub_headline": "Dimon goes hunting. Again.", "summary": "JPMorgan Chase acquisition"},
        {"title": "Snowflake bets $6B on AWS", "stat_hook": "+37%", "sub_headline": "Snowflake doubles AI bet", "summary": "The cloud was never going to sit still"},
        {"title": "Samsung workers end standoff", "stat_hook": "+7%", "sub_headline": "Samsung workers end standoff", "summary": "The AI supply chain needed that"},
        {"title": "Nvidia reports record revenue", "stat_hook": "$81.6B", "sub_headline": "Nvidia shatters record", "summary": "Jensen Huang announces $80B buyback"},
        {"title": "Iran strikes snap Asia rally", "stat_hook": "-2.1%", "sub_headline": "Iran strikes snap Asia rally", "summary": "Risk-off is back. Again."},
    ]
    
    print("=" * 60)
    print("VISUAL IDENTITY — SINGLE ENTITY TEST")
    print("=" * 60)
    for story in test_stories:
        reg_key, entry = detect_entity(story)
        title = story.get("title", "")[:40]
        if entry:
            print(f"\n✓ {title}")
            print(f"  Entity: {reg_key} | Type: {entry['type']} | Model: {entry['model']}")
            print(f"  Visual: {entry['visual'][:70]}...")
        else:
            print(f"\n✗ {title}")
            print(f"  No entity match — default prompt")

    # ── Versus detection tests ──
    versus_stories = [
        {"title": "Musk loses lawsuit against OpenAI and Altman", "sub_headline": "Musk loses. Altman walks free.", "summary": "The $150B trial is over"},
        {"title": "Trump swears in Warsh as new Fed Chair", "sub_headline": "Trump holds the Bible. Warsh takes the oath.", "summary": "Most divisive Fed confirmation in history"},
        {"title": "OpenAI vs Anthropic: the IPO race begins", "sub_headline": "OpenAI files S-1. Anthropic closes $900B round.", "summary": "Both targeting 2026 IPO"},
        {"title": "Nvidia vs AMD: the chip war heats up", "sub_headline": "Jensen's $81B quarter vs Lisa Su's Venice launch", "summary": "Two chip giants, one AI market"},
        {"title": "Microsoft Copilot takes on Google Gemini", "sub_headline": "Nadella and Pichai both claim the agent future", "summary": "Enterprise AI showdown"},
        {"title": "Google I/O launches Antigravity", "sub_headline": "Sundar Pichai announces agent platform", "summary": "100+ announcements in 2 days"},
        {"title": "SpaceX IPO vs OpenAI IPO", "sub_headline": "Musk and Altman race to public markets", "summary": "SpaceX June, OpenAI September"},
    ]
    
    print("\n" + "=" * 60)
    print("VERSUS DETECTION TEST")
    print("=" * 60)
    for story in versus_stories:
        pair_key, pair = detect_versus(story)
        title = story.get("title", "")[:50]
        if pair:
            left = FACE_REGISTRY.get(pair["left"], {}).get("face", "?")[:30]
            right = FACE_REGISTRY.get(pair["right"], {}).get("face", "?")[:30]
            print(f"\n⚡ {title}")
            print(f"   Pair: {pair_key}")
            print(f"   Left:  {left}...")
            print(f"   Right: {right}...")
            print(f"   Divider: {pair.get('divider', 'lightning')}")
        else:
            print(f"\n○ {title}")
            print(f"   No versus match — single entity or default")
            # Check if single entity matches
            anchor = get_visual_anchor(story)
            if anchor:
                print(f"   → Single entity fallback: {anchor[:60]}...")

    # ── Full pipeline test ──
    print("\n" + "=" * 60)
    print("FULL PIPELINE TEST (get_visual_anchor)")
    print("=" * 60)
    all_stories = test_stories + versus_stories
    for story in all_stories:
        title = story.get("title", "")[:45]
        anchor = get_visual_anchor(story)
        model = get_model_override(story)
        if anchor:
            is_versus = "⚡VERSUS" if "split-screen" in anchor.lower() else "● SINGLE"
            print(f"\n{is_versus} {title}")
            print(f"  Model: {model}")
            print(f"  Prompt: {anchor[:80]}...")
        else:
            print(f"\n○ {title} — no visual anchor")
