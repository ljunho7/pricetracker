import re
from fuzzywuzzy import fuzz

SIZE_ALIASES = {
    # with spaces (checked first)
    "extra small": "XS",
    "extra large": "XL",
    "one size":    "OS",
    # collapsed (no spaces)
    "xsmall": "XS", "extrasmall": "XS",
    "xlarge": "XL", "extralarge": "XL",
    "onesize": "OS",
    "xxs": "XXS", "xs": "XS", "s": "S", "m": "M",
    "l": "L", "xl": "XL", "xxl": "XXL",
    "small":  "S",
    "medium": "M",
    "large":  "L",
    "os": "OS",
}

def normalize_size(raw: str) -> str:
    """Normalize size strings to standard abbreviations."""
    stripped = raw.strip().lower().replace("-", "")
    # Try with spaces first, then collapsed
    if stripped in SIZE_ALIASES:
        return SIZE_ALIASES[stripped]
    collapsed = stripped.replace(" ", "")
    return SIZE_ALIASES.get(collapsed, raw.strip().upper())

def normalize_brand(brand: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", brand.lower()).strip()

def normalize_name(name: str) -> str:
    # Remove brand name repetition, color/size qualifiers, punctuation
    name = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    return " ".join(name.split())

def match_confidence(source_brand: str, source_name: str,
                     result_brand: str, result_name: str) -> float:
    """
    Return 0.0–1.0 confidence that result is the same product as source.
    Uses brand exact match + fuzzy name match.
    """
    sb = normalize_brand(source_brand)
    rb = normalize_brand(result_brand)

    # Brand must match (allow partial — "cinq sept" vs "cinq a sept")
    brand_score = fuzz.partial_ratio(sb, rb) / 100.0
    if brand_score < 0.7:
        return 0.0  # Different brand — hard reject

    sn = normalize_name(source_name)
    rn = normalize_name(result_name)
    name_score = fuzz.token_sort_ratio(sn, rn) / 100.0

    # Weighted: brand matters more as a gate, name drives confidence
    return round(brand_score * 0.4 + name_score * 0.6, 3)

MATCH_THRESHOLD = 0.55  # Minimum confidence to accept a result

def is_match(source_brand, source_name, result_brand, result_name) -> bool:
    return match_confidence(
        source_brand, source_name, result_brand, result_name
    ) >= MATCH_THRESHOLD
