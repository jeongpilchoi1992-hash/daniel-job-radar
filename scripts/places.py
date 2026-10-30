"""Approximate coordinates for places around Northern Virginia, DC and Maryland.

Used to estimate commute distance for postings that only give a city name
(state and local sources). Federal postings carry their own coordinates.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

# Hand-checked names around home, by state: name -> (lat, lon). Keys are lowercase, without state suffix.
# These win over the gazetteer, so a bare "Vienna" or "Springfield" means the Northern Virginia one.
CURATED: dict[str, dict[str, tuple[float, float]]] = {"VA": {
    # Prince William / Manassas area
    "manassas": (38.7509, -77.4753),
    "manassas park": (38.7840, -77.4697),
    "prince william": (38.7018, -77.4785),
    "prince william county": (38.7018, -77.4785),
    "gainesville": (38.7957, -77.6141),
    "haymarket": (38.8126, -77.6364),
    "bristow": (38.7226, -77.5372),
    "nokesville": (38.6987, -77.5797),
    "woodbridge": (38.6582, -77.2497),
    "dale city": (38.6371, -77.3111),
    "lake ridge": (38.6879, -77.2978),
    "occoquan": (38.6837, -77.2603),
    "montclair": (38.6110, -77.3397),
    "dumfries": (38.5676, -77.3280),
    "triangle": (38.5468, -77.3203),
    "quantico": (38.5223, -77.2936),
    # Fairfax County and cities
    "fairfax": (38.8462, -77.3064),
    "fairfax county": (38.8536, -77.3576),
    "city of fairfax": (38.8462, -77.3064),
    "centreville": (38.8404, -77.4289),
    "chantilly": (38.8943, -77.4311),
    "clifton": (38.7804, -77.3866),
    "burke": (38.7935, -77.2717),
    "springfield": (38.7893, -77.1872),
    "lorton": (38.7043, -77.2278),
    "annandale": (38.8304, -77.1964),
    "falls church": (38.8823, -77.1711),
    "vienna": (38.9012, -77.2653),
    "oakton": (38.8809, -77.3008),
    "mclean": (38.9339, -77.1773),
    "tysons": (38.9187, -77.2311),
    "tysons corner": (38.9187, -77.2311),
    "reston": (38.9586, -77.3570),
    "herndon": (38.9696, -77.3861),
    "great falls": (38.9982, -77.2883),
    "fort belvoir": (38.7119, -77.1459),
    "mount vernon": (38.7293, -77.1075),
    "alexandria": (38.8048, -77.0469),
    "arlington": (38.8816, -77.0910),
    "arlington county": (38.8816, -77.0910),
    "pentagon": (38.8719, -77.0563),
    "crystal city": (38.8565, -77.0517),
    "national landing": (38.8565, -77.0517),
    "rosslyn": (38.8966, -77.0716),
    "ballston": (38.8822, -77.1110),
    "dulles": (38.9531, -77.4565),
    # Loudoun
    "loudoun": (39.1157, -77.5636),
    "loudoun county": (39.1157, -77.5636),
    "leesburg": (39.1157, -77.5636),
    "sterling": (39.0062, -77.4286),
    "ashburn": (39.0438, -77.4874),
    "purcellville": (39.1368, -77.7147),
    "middleburg": (38.9687, -77.7355),
    "lansdowne": (39.0815, -77.4875),
    # Fauquier / Culpeper / Stafford / Fredericksburg / west
    "warrenton": (38.7135, -77.7953),
    "fauquier": (38.7135, -77.7953),
    "fauquier county": (38.7135, -77.7953),
    "culpeper": (38.4732, -77.9967),
    "front royal": (38.9182, -78.1944),
    "stafford": (38.4221, -77.4083),
    "stafford county": (38.4221, -77.4083),
    "fredericksburg": (38.3032, -77.4605),
    "spotsylvania": (38.2010, -77.5886),
    "king george": (38.2682, -77.1847),
    "dahlgren": (38.3318, -77.0372),
    "winchester": (39.1857, -78.1633),
    "berryville": (39.1518, -77.9822),
}, "DC": {
    "washington": (38.9072, -77.0369),
    "washington dc": (38.9072, -77.0369),
    "district of columbia": (38.9072, -77.0369),
}, "MD": {
    "bethesda": (38.9847, -77.0947),
    "chevy chase": (38.9943, -77.0737),
    "silver spring": (38.9907, -77.0261),
    "rockville": (39.0840, -77.1528),
    "gaithersburg": (39.1434, -77.2014),
    "germantown": (39.1732, -77.2717),
    "college park": (38.9897, -76.9378),
    "greenbelt": (39.0046, -76.8755),
    "hyattsville": (38.9559, -76.9455),
    "largo": (38.8976, -76.8303),
    "upper marlboro": (38.8159, -76.7497),
    "suitland": (38.8487, -76.9239),
    "oxon hill": (38.8034, -76.9897),
    "national harbor": (38.7826, -77.0172),
    "joint base andrews": (38.8108, -76.8669),
    "andrews afb": (38.8108, -76.8669),
    "lanham": (38.9687, -76.8633),
    "beltsville": (39.0348, -76.9075),
    "adelphi": (39.0032, -76.9719),
    "laurel": (39.0993, -76.8483),
    "fort meade": (39.1086, -76.7433),
    "fort george g. meade": (39.1086, -76.7433),
    "columbia": (39.2037, -76.8610),
    "frederick": (39.4143, -77.4105),
    "fort detrick": (39.4359, -77.4258),
    "waldorf": (38.6246, -76.9391),
    "la plata": (38.5293, -76.9753),
    "indian head": (38.6001, -77.1622),
    "annapolis": (38.9784, -76.4922),
    "baltimore": (39.2904, -76.6122),
    "woodlawn": (39.3229, -76.7280),
}, "WV": {
    "harpers ferry": (39.3254, -77.7389),
    "kearneysville": (39.3876, -77.8858),
    "martinsburg": (39.4562, -77.9639),
}}

# Every town, postal city, county and independent city in VA, MD, DC and WV, built once from the MIT-licensed
# ZIP code table of the "zipcodes" package (state -> name -> [lat, lon]; see README).
GAZETTEER: dict[str, dict[str, list[float]]] = json.loads((Path(__file__).with_name("gazetteer.json")).read_text())

PLACES: dict[str, tuple[float, float]] = {name: xy for names in reversed(CURATED.values()) for name, xy in names.items()}

STATE_CODES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "district of columbia": "DC", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "puerto rico": "PR", "guam": "GU", "u.s. virgin islands": "VI",
    # "washington" is left out on purpose: alone it means the city, not the state.
}
_ABBREVIATIONS = set(STATE_CODES.values()) | {"WA"}
_COUNTRY = re.compile(r"[\s,]*\b(united states( of america)?|usa|u\.s\.a?\.?|us)\s*$", re.I)
_ABBR_AT_END = re.compile(r"(?:,|\s)\s*([A-Za-z]{2})\.?(?:\s+\d{5}(?:-\d{4})?)?\s*$")
_DC_AT_END = re.compile(r"(?:^|[\s,])(d\.\s?c\.?|district of columbia)\s*$", re.I)
_STATE_SUFFIX = re.compile(
    r",?\s*\b(" + "|".join(sorted([re.escape(n) for n in STATE_CODES] + list(_ABBREVIATIONS), key=len, reverse=True))
    + r"|d\.c)\.?(\s+\d{5}(-\d{4})?)?\s*$",
    re.I,
)
# Words that may sit next to a one-word town name ("Manassas Campus", "Front Royal Office").
_GENERIC = {"campus", "office", "offices", "center", "centre", "county", "city", "town", "area", "region", "district",
            "headquarters", "hq", "site", "building", "location", "branch", "facility", "satellite"}


def haversine_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def state_of(name: str) -> str | None:
    """The U.S. state a location string names at its end ('Springfield, IL' -> 'IL'), if any."""
    text = _COUNTRY.sub("", (name or "").strip()).strip(" ,.")
    text = re.sub(r"\s+\d{5}(-\d{4})?$", "", text).strip(" ,.")
    if _DC_AT_END.search(text):
        return "DC"
    low = text.lower()
    for state, code in sorted(STATE_CODES.items(), key=lambda kv: -len(kv[0])):
        if low.endswith(state) and (len(low) == len(state) or low[-len(state) - 1] in ", "):
            return code
    m = _ABBR_AT_END.search(text)
    if m and m.group(1).upper() in _ABBREVIATIONS and (m.group(1).isupper() or "," in text):
        return m.group(1).upper()
    return None


def normalize_place(name: str) -> str:
    text = re.sub(r"\s+", " ", (name or "").strip().lower())
    text = _COUNTRY.sub("", text).strip(" ,")
    text = text.replace("st.", "saint")
    text = re.sub(r"\bft\.? ", "fort ", text)
    text = re.sub(r"\bmt\.? ", "mount ", text)
    text = re.sub(r"\bmc ", "mc", text)
    prev = None
    while prev != text:
        prev = text
        text = _STATE_SUFFIX.sub("", text).strip(" ,")
    text = re.sub(r"^(city|town|county) of ", "", text)
    return text


def _find(name: str, state: str | None, anywhere: bool) -> tuple[float, float] | None:
    """One candidate name: hand-checked names first, then the gazetteer (only when the name is a whole part)."""
    if state:
        if state not in CURATED and state not in GAZETTEER:
            return None
        hit = CURATED.get(state, {}).get(name) or (None if anywhere else GAZETTEER.get(state, {}).get(name))
        return tuple(hit) if hit else None
    if name in PLACES:
        return PLACES[name]
    if anywhere:
        return None
    for code in ("VA", "DC", "MD", "WV"):
        if name in GAZETTEER.get(code, {}):
            return tuple(GAZETTEER[code][name])
    return None


def lookup(name: str, state: str | None = None) -> tuple[float, float] | None:
    """Best-effort coordinates for a free-text location like 'Fairfax, VA' or 'NOVA - Annandale Campus'.

    A state named in the text ('Springfield, IL') wins over the caller's default `state`; places in states other
    than VA, MD, DC and WV return None, since none of them is within commuting range.
    """
    state = state_of(name) or state
    key = normalize_place(name)
    if not key:
        if state == "DC" or re.search(r"district of columbia|\bd\.?c\.?\b", name or "", re.I):
            return PLACES["washington"]
        return None
    parts = [p.strip() for p in re.split(r"[,/;()]| - ", key) if p.strip()]
    for whole in [key] + parts:
        hit = _find(whole, state, anywhere=False)
        if hit:
            return hit
    # Then the longest run of words inside a part that names a place ("Clifton Forge" before "Clifton").
    words = [re.findall(r"[a-z0-9.'-]+", part) for part in parts]
    for n in range(min(5, max((len(w) for w in words), default=0)), 0, -1):
        for part_words in words:
            for i in range(len(part_words) - n + 1):
                gram = " ".join(part_words[i:i + n])
                rest = set(part_words[:i] + part_words[i + n:])
                hit = _find(gram, state, anywhere=not rest <= _GENERIC)
                if hit:
                    return hit
    return None
