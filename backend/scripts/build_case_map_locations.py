from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.request import Request, urlopen
from zipfile import ZipFile


BACKEND_DIR = Path(__file__).resolve().parents[1]
CASES_PATH = BACKEND_DIR / "data" / "cases.json"
OUTPUT_PATH = BACKEND_DIR / "data" / "case_map_locations.json"
GEONAMES_URL = "https://download.geonames.org/export/dump/cities500.zip"
GENERATOR_VERSION = "case-map-v2"


US_ADMIN_CODES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Puerto Rico": "PR", "Rhode Island": "RI",
    "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
    "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}

CA_ADMIN_CODES = {
    "Alberta": "AB", "British Columbia": "BC", "Manitoba": "MB",
    "New Brunswick": "NB", "Newfoundland and Labrador": "NL", "Nova Scotia": "NS",
    "Northwest Territories": "NT", "Nunavut": "NU", "Ontario": "ON",
    "Prince Edward Island": "PE", "Quebec": "QC", "Saskatchewan": "SK",
    "Yukon": "YT",
}

CA_GEONAMES_ADMIN_CODES = {
    "AB": "01", "BC": "02", "MB": "03", "NB": "04", "NL": "05",
    "NS": "07", "ON": "08", "PE": "09", "QC": "10", "SK": "11",
    "YT": "12", "NT": "13", "NU": "14",
}

# Broad-region coordinates are used only when an official notice names no city.
# They are explicitly marked approximate and are not presented as a person's location.
REGION_CENTERS = {
    ("US", "AL"): (32.8067, -86.7911), ("US", "AK"): (61.3707, -152.4044),
    ("US", "AZ"): (33.7298, -111.4312), ("US", "AR"): (34.9697, -92.3731),
    ("US", "CA"): (36.1162, -119.6816), ("US", "CO"): (39.0598, -105.3111),
    ("US", "CT"): (41.5978, -72.7554), ("US", "DE"): (39.3185, -75.5071),
    ("US", "DC"): (38.9072, -77.0369), ("US", "FL"): (27.7663, -81.6868),
    ("US", "GA"): (33.0406, -83.6431), ("US", "HI"): (21.0943, -157.4983),
    ("US", "ID"): (44.2405, -114.4788), ("US", "IL"): (40.3495, -88.9861),
    ("US", "IN"): (39.8494, -86.2583), ("US", "IA"): (42.0115, -93.2105),
    ("US", "KS"): (38.5266, -96.7265), ("US", "KY"): (37.6681, -84.6701),
    ("US", "LA"): (31.1695, -91.8678), ("US", "ME"): (44.6939, -69.3819),
    ("US", "MD"): (39.0639, -76.8021), ("US", "MA"): (42.2302, -71.5301),
    ("US", "MI"): (43.3266, -84.5361), ("US", "MN"): (45.6945, -93.9002),
    ("US", "MS"): (32.7416, -89.6787), ("US", "MO"): (38.4561, -92.2884),
    ("US", "MT"): (46.9219, -110.4544), ("US", "NE"): (41.1254, -98.2681),
    ("US", "NV"): (38.3135, -117.0554), ("US", "NH"): (43.4525, -71.5639),
    ("US", "NJ"): (40.2989, -74.5210), ("US", "NM"): (34.8405, -106.2485),
    ("US", "NY"): (42.1657, -74.9481), ("US", "NC"): (35.6301, -79.8064),
    ("US", "ND"): (47.5289, -99.7840), ("US", "OH"): (40.3888, -82.7649),
    ("US", "OK"): (35.5653, -96.9289), ("US", "OR"): (44.5720, -122.0709),
    ("US", "PA"): (40.5908, -77.2098), ("US", "PR"): (18.2208, -66.5901),
    ("US", "RI"): (41.6809, -71.5118), ("US", "SC"): (33.8569, -80.9450),
    ("US", "SD"): (44.2998, -99.4388), ("US", "TN"): (35.7478, -86.6923),
    ("US", "TX"): (31.0545, -97.5635), ("US", "UT"): (40.1500, -111.8624),
    ("US", "VT"): (44.0459, -72.7107), ("US", "VA"): (37.7693, -78.1700),
    ("US", "WA"): (47.4009, -121.4905), ("US", "WV"): (38.4912, -80.9545),
    ("US", "WI"): (44.2685, -89.6165), ("US", "WY"): (42.7560, -107.3025),
    ("CA", "AB"): (53.9333, -116.5765), ("CA", "BC"): (53.7267, -127.6476),
    ("CA", "MB"): (53.7609, -98.8139), ("CA", "NB"): (46.5653, -66.4619),
    ("CA", "NL"): (53.1355, -57.6604), ("CA", "NS"): (44.6820, -63.7443),
    ("CA", "NT"): (64.8255, -124.8457), ("CA", "NU"): (70.2998, -83.1076),
    ("CA", "ON"): (51.2538, -85.3232), ("CA", "PE"): (46.5107, -63.4168),
    ("CA", "QC"): (52.9399, -73.5491), ("CA", "SK"): (52.9399, -106.4509),
    ("CA", "YT"): (64.2823, -135.0000),
}

SPECIAL_LOCATIONS = {
    "the comox valley area of vancouver island": ("Comox Valley, British Columbia", 49.6841, -124.9904),
    "west shore, british columbia": ("West Shore, British Columbia", 48.4456, -123.5048),
}


@dataclass(frozen=True)
class Candidate:
    label: str
    city: str | None
    country_code: str
    admin_code: str | None
    location_type: str
    broad_region: bool = False


@dataclass(frozen=True)
class Place:
    name: str
    latitude: float
    longitude: float
    population: int


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(character for character in value if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def admin_maps(country_code: str) -> tuple[dict[str, str], dict[str, str]]:
    names = US_ADMIN_CODES if country_code == "US" else CA_ADMIN_CODES
    aliases = {normalize(name): code for name, code in names.items()}
    aliases.update({code.casefold(): code for code in names.values()})
    display = {code: name for name, code in names.items()}
    return aliases, display


def parse_city_phrase(
    phrase: str,
    *,
    country_code: str,
    fallback_admin_code: str | None,
    location_type: str,
) -> list[Candidate]:
    phrase = re.sub(r"^city of\s+", "", phrase.strip(), flags=re.IGNORECASE)
    phrase = re.sub(r"\s+RCMP(?=,|$)", "", phrase, flags=re.IGNORECASE)
    phrase = re.sub(r"^the district of\s+", "", phrase, flags=re.IGNORECASE)
    phrase = re.sub(r"^district of\s+", "", phrase, flags=re.IGNORECASE)
    if not phrase or len(phrase) > 120 or "contrary to" in phrase.casefold():
        return []

    special = SPECIAL_LOCATIONS.get(normalize(phrase))
    if special:
        label, latitude, longitude = special
        return [
            Candidate(
                label=f"{label}|{latitude}|{longitude}",
                city=None,
                country_code=country_code,
                admin_code=fallback_admin_code,
                location_type=location_type,
            )
        ]

    aliases, display = admin_maps(country_code)
    normalized_phrase = normalize(phrase)
    if normalized_phrase in aliases:
        admin_code = aliases[normalized_phrase]
        return [
            Candidate(
                label=display[admin_code],
                city=None,
                country_code=country_code,
                admin_code=admin_code,
                location_type="broad_region",
                broad_region=True,
            )
        ]

    # Handle two broad regions such as "Tennessee, Mississippi".
    comma_parts = [part.strip() for part in phrase.split(",") if part.strip()]
    if len(comma_parts) == 2 and all(normalize(part) in aliases for part in comma_parts):
        return [
            Candidate(
                label=display[aliases[normalize(part)]],
                city=None,
                country_code=country_code,
                admin_code=aliases[normalize(part)],
                location_type="broad_region",
                broad_region=True,
            )
            for part in comma_parts
        ]

    admin_code = fallback_admin_code
    admin_position = None
    for index in range(len(comma_parts) - 1, 0, -1):
        possible_code = aliases.get(normalize(comma_parts[index]))
        if possible_code:
            admin_code = possible_code
            admin_position = index
            break

    city = comma_parts[0] if comma_parts else phrase
    if admin_position is not None and admin_position > 1:
        # "Hope, BC, British Columbia" and similar duplicated suffixes.
        city = comma_parts[0]

    city = re.sub(r"\b(county|parish|district)\b", "", city, flags=re.IGNORECASE).strip(" ,")
    if not city or normalize(city) in aliases:
        return []

    label = f"{city}, {display.get(admin_code, admin_code)}" if admin_code else city
    return [
        Candidate(
            label=label,
            city=city,
            country_code=country_code,
            admin_code=admin_code,
            location_type=location_type,
        )
    ]


def split_official_locations(raw_value: str) -> list[str]:
    values: list[str] = []
    for semicolon_part in raw_value.split(";"):
        parts = re.split(
            r"\s+and\s+(?=[A-Z][^,;]{1,45},\s*[A-Z]{2}\b)",
            semicolon_part,
            flags=re.IGNORECASE,
        )
        values.extend(part.strip() for part in parts if part.strip())
    return values


def title_candidates(case: dict) -> list[Candidate]:
    if not str(case.get("id", "")).startswith("uspis-"):
        return []
    prefix = str(case.get("title", "")).split(":", 1)[0].strip()
    match = re.match(r"^(.+?)(?:,\s*|\s+)([A-Z]{2})$", prefix)
    if not match:
        return []

    city_group, admin_code = match.groups()
    if admin_code not in US_ADMIN_CODES.values():
        return []
    if any(
        word in normalize(city_group).split()
        for word in ("missing", "reward", "northern", "southern", "statewide")
    ):
        return []

    _, display = admin_maps("US")
    candidates = []
    for city in re.split(r"\s*(?:/|&)\s*", city_group):
        city = city.strip(" ,")
        if not city:
            continue
        candidates.append(
            Candidate(
                label=f"{city}, {display[admin_code]}",
                city=city,
                country_code="US",
                admin_code=admin_code,
                location_type="title_location",
            )
        )
    return candidates


def case_candidates(case: dict) -> list[Candidate]:
    country_code = {"US": "US", "Canada": "CA"}.get(case.get("country"))
    if country_code is None:
        return []
    aliases, _ = admin_maps(country_code)
    fallback_admin_code = next(
        (
            aliases[normalize(region)]
            for region in case.get("regions", [])
            if normalize(str(region)) in aliases
        ),
        None,
    )

    candidates = []
    raw_locations = str(case.get("locations") or "").strip()
    if raw_locations and normalize(raw_locations) != "federal":
        for phrase in split_official_locations(raw_locations):
            candidates.extend(
                parse_city_phrase(
                    phrase,
                    country_code=country_code,
                    fallback_admin_code=fallback_admin_code,
                    location_type="official_location",
                )
            )

    # Postal notices often put the precise incident city in the title while
    # their location field contains only the state. Prefer the title city.
    precise_title_candidates = title_candidates(case)
    if precise_title_candidates:
        candidates = [candidate for candidate in candidates if not candidate.broad_region]
        candidates.extend(precise_title_candidates)
    return candidates


def load_places(zip_path: Path, candidates: list[Candidate]) -> dict[tuple[str, str, str], Place]:
    targets = {
        (
            candidate.country_code,
            CA_GEONAMES_ADMIN_CODES.get(candidate.admin_code, candidate.admin_code)
            if candidate.country_code == "CA"
            else candidate.admin_code,
            normalize(candidate.city),
        ): (candidate.country_code, candidate.admin_code, normalize(candidate.city))
        for candidate in candidates
        if candidate.city and candidate.admin_code
    }
    places: dict[tuple[str, str, str], Place] = {}
    with ZipFile(zip_path) as archive, archive.open("cities500.txt") as input_file:
        for raw_line in input_file:
            fields = raw_line.decode("utf-8").rstrip("\n").split("\t")
            if len(fields) < 15:
                continue
            country_code, admin_code = fields[8], fields[10]
            if country_code not in {"US", "CA"}:
                continue
            names = {fields[1], fields[2], *fields[3].split(",")}
            population = int(fields[14] or 0)
            place = Place(fields[1], float(fields[4]), float(fields[5]), population)
            for name in names:
                source_key = (country_code, admin_code, normalize(name))
                target_key = targets.get(source_key)
                if target_key is None:
                    continue
                existing = places.get(target_key)
                if existing is None or place.population > existing.population:
                    places[target_key] = place
    return places


def ensure_geonames_zip(zip_path: Path) -> None:
    if zip_path.exists() and zip_path.stat().st_size > 1_000_000:
        return
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(GEONAMES_URL, headers={"User-Agent": "Reward-Watch-map-index/1.0"})
    with urlopen(request, timeout=90) as response, zip_path.open("wb") as output_file:
        while chunk := response.read(1024 * 1024):
            output_file.write(chunk)


def source_fingerprint(cases: list[dict]) -> str:
    relevant = [
        {
            "id": case.get("id"),
            "country": case.get("country"),
            "regions": case.get("regions", []),
            "locations": case.get("locations"),
            "title": case.get("title"),
        }
        for case in cases
    ]
    serialized = json.dumps(relevant, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return sha256(f"{GENERATOR_VERSION}\n{serialized}".encode("utf-8")).hexdigest()


def build_map_locations(cases: list[dict], places: dict[tuple[str, str, str], Place]):
    locations_by_case: dict[str, list[dict]] = {}
    precision_counts = {"city": 0, "region": 0}
    unresolved: set[str] = set()

    for case in cases:
        resolved = []
        seen = set()
        for candidate in case_candidates(case):
            latitude = longitude = None
            label = candidate.label
            precision = "region" if candidate.broad_region else "city"
            approximate = candidate.broad_region

            special_parts = candidate.label.rsplit("|", 2)
            if len(special_parts) == 3:
                label, latitude_text, longitude_text = special_parts
                latitude, longitude = float(latitude_text), float(longitude_text)
                approximate = True
            elif candidate.broad_region and candidate.admin_code:
                center = REGION_CENTERS.get((candidate.country_code, candidate.admin_code))
                if center:
                    latitude, longitude = center
            elif candidate.city and candidate.admin_code:
                place = places.get(
                    (candidate.country_code, candidate.admin_code, normalize(candidate.city))
                )
                if place:
                    latitude, longitude = place.latitude, place.longitude

            if latitude is None or longitude is None:
                unresolved.add(candidate.label)
                continue
            location_key = (round(latitude, 4), round(longitude, 4), candidate.location_type)
            if location_key in seen:
                continue
            seen.add(location_key)
            resolved.append(
                {
                    "label": label,
                    "latitude": round(latitude, 6),
                    "longitude": round(longitude, 6),
                    "precision": precision,
                    "locationType": candidate.location_type,
                    "approximate": approximate,
                }
            )

        if resolved:
            locations_by_case[str(case["id"])] = resolved
            precision_counts["city" if any(item["precision"] == "city" for item in resolved) else "region"] += 1

    return locations_by_case, precision_counts, sorted(unresolved)


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the compact public case map location index.")
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument(
        "--geonames-zip",
        type=Path,
        default=Path(tempfile.gettempdir()) / "reward-watch-cities500.zip",
    )
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    fingerprint = source_fingerprint(cases)
    if args.output.exists():
        existing = json.loads(args.output.read_text(encoding="utf-8"))
        if existing.get("sourceFingerprint") == fingerprint:
            print(f"Map locations are current ({len(existing.get('cases', {}))} cases).")
            return 0

    candidates = [candidate for case in cases for candidate in case_candidates(case)]
    ensure_geonames_zip(args.geonames_zip)
    places = load_places(args.geonames_zip, candidates)
    locations_by_case, precision_counts, unresolved = build_map_locations(cases, places)
    payload = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "sourceFingerprint": fingerprint,
        "attribution": "GeoNames (CC BY 4.0) and official notice location labels",
        "precisionCounts": precision_counts,
        "unresolved": unresolved,
        "cases": locations_by_case,
    }
    write_json_atomic(args.output, payload)
    print(
        f"Wrote map locations for {len(locations_by_case)} cases "
        f"({precision_counts['city']} city-level, {precision_counts['region']} broad-region)."
    )
    print(f"Unresolved labels: {len(unresolved)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
