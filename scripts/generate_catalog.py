"""Generate the synthetic used-commercial-vehicle catalog (data/listings.csv).

Inputs (hand-curated, checked in):
    data/models.csv          real Indian CV variants with public-page specs
    data/aliases.csv         spoken/Hinglish/STT aliases -> canonical values
    data/city_neighbors.csv  nearby listing cities for zero-result relaxation

Output:
    data/listings.csv        180 deterministic synthetic used listings

The generator is fully deterministic (random.Random(SEED)); re-running it
produces a byte-identical listings.csv. After random generation a fixed set of
edge-case listings is planted (exact 5-lakh prices, just-above-5-lakh prices,
near-duplicate Tata Ace models, predictable zero-result combos) and every
edge case is verified. Any failed check exits with status 1.

Usage:
    python scripts/generate_catalog.py

Standard library only.
"""

from __future__ import annotations

import csv
import random
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

SEED = 42
N_LISTINGS = 180

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MODELS_CSV = DATA_DIR / "models.csv"
ALIASES_CSV = DATA_DIR / "aliases.csv"
NEIGHBORS_CSV = DATA_DIR / "city_neighbors.csv"
LISTINGS_CSV = DATA_DIR / "listings.csv"

CURRENT_YEAR = 2026
MIN_YEAR = 2012
MAX_YEAR = 2025
LISTING_START = date(2026, 7, 1)
LISTING_END = date(2026, 10, 15)

PRICE_ROUNDING = 5_000
KM_ROUNDING = 500
FIVE_LAKH = 500_000

BODY_TYPES = ("three_wheeler", "mini_truck", "pickup", "cargo_van", "lcv", "icv", "tipper")
FUELS = ("diesel", "petrol", "cng", "electric")
SELLER_TYPES = ("dealer", "individual")
ALIAS_KINDS = ("make", "model", "body_type", "fuel", "city")

CITY_STATE = {
    "mumbai": "MH",
    "delhi": "DL",
    "bengaluru": "KA",
    "pune": "MH",
    "hyderabad": "TS",
    "chennai": "TN",
    "ahmedabad": "GJ",
    "jaipur": "RJ",
    "lucknow": "UP",
    "kolkata": "WB",
}
CITIES = tuple(CITY_STATE)
MIN_LISTINGS_PER_CITY = 15

# City weights per fuel. A weight of 0 forbids the combination outright, which
# is how the "zero CNG in Kolkata / zero electric in Chennai" demos are kept.
DEFAULT_CITY_WEIGHTS = {city: 1.0 for city in CITIES}
CNG_CITY_WEIGHTS = {
    **{city: 0.5 for city in CITIES},
    "mumbai": 5.0,
    "delhi": 5.0,
    "pune": 5.0,
    "ahmedabad": 4.0,
    "kolkata": 0.0,
}
ELECTRIC_CITY_WEIGHTS = {
    **{city: 0.25 for city in CITIES},
    "delhi": 6.0,
    "bengaluru": 6.0,
    "chennai": 0.0,
}
FUEL_CITY_WEIGHTS = {
    "diesel": DEFAULT_CITY_WEIGHTS,
    "petrol": DEFAULT_CITY_WEIGHTS,
    "cng": CNG_CITY_WEIGHTS,
    "electric": ELECTRIC_CITY_WEIGHTS,
}

# How often each segment shows up in the random part of the catalog.
BODY_TYPE_WEIGHTS = {
    "mini_truck": 3.0,
    "pickup": 3.0,
    "three_wheeler": 2.0,
    "cargo_van": 1.0,
    "lcv": 1.5,
    "icv": 1.2,
    "tipper": 1.0,
}

# Within a segment, electric variants are over-sampled so EV demos have data.
FUEL_MODEL_WEIGHTS = {"diesel": 1.0, "petrol": 1.0, "cng": 1.0, "electric": 2.5}

# Plausible annual running (km/year) per segment: 3W / mini trucks run less.
KM_PER_YEAR = {
    "three_wheeler": (10_000, 22_000),
    "mini_truck": (12_000, 28_000),
    "cargo_van": (10_000, 24_000),
    "pickup": (18_000, 38_000),
    "lcv": (28_000, 50_000),
    "icv": (45_000, 80_000),
    "tipper": (35_000, 65_000),
}

DEPRECIATION_RANGE = (0.10, 0.15)   # per year, compounded
PRICE_NOISE = 0.07                  # +/- uniform multiplicative noise
KM_EFFECT = 0.08                    # price swing per 100% deviation from typical km
KM_FACTOR_BOUNDS = (0.90, 1.10)
MIN_RESIDUAL_FRACTION = 0.18        # used price never below 18% of new price
PAPERS_VERIFIED_PROBABILITY = 0.70
DEALER_PROBABILITY = 0.55

# Rough "mostly" price bands per segment group (reported, softly checked).
PRICE_BANDS = {
    "mini_truck/pickup": (("mini_truck", "pickup"), 150_000, 700_000),
    "lcv": (("lcv",), 600_000, 1_500_000),
    "icv/tipper": (("icv", "tipper"), 1_000_000, 3_500_000),
}
PRICE_BAND_MIN_SHARE = 0.60

ACE_NEAR_DUPLICATES = ("Ace Gold", "Ace HT Plus", "Ace Mega", "Ace CNG")


@dataclass(frozen=True)
class PlantedSpec:
    """A hand-placed listing used to guarantee an edge case."""

    model_id: str
    city: str
    price_inr: int
    reason: str


PLANTED_SPECS: tuple[PlantedSpec, ...] = (
    # (a) exact 5,00,000 prices, incl. a diesel mini truck in Pune
    PlantedSpec("tata_ace_gold_diesel", "pune", 500_000, "a: exact 5 lakh diesel mini_truck pune"),
    PlantedSpec("maruti_super_carry_cng", "mumbai", 500_000, "a: exact 5 lakh"),
    PlantedSpec("mahindra_bolero_pikup_fb_1_3", "delhi", 500_000, "a: exact 5 lakh"),
    PlantedSpec("tata_ace_cng_bifuel", "pune", 500_000, "a/d/e: exact 5 lakh cng pune"),
    # (b) just above 5 lakh, to catch off-by-one budget filters
    PlantedSpec("tata_ace_gold_diesel", "mumbai", 505_000, "b/d: just above 5 lakh"),
    PlantedSpec("tata_intra_v30", "bengaluru", 510_000, "b: just above 5 lakh"),
    PlantedSpec("maruti_super_carry_petrol", "hyderabad", 515_000, "b: just above 5 lakh"),
    PlantedSpec("mahindra_jeeto_diesel", "jaipur", 520_000, "b: just above 5 lakh"),
    PlantedSpec("tata_ace_ht_plus_diesel", "pune", 505_000, "b/d: just above 5 lakh"),
    # (d) Ace near-duplicates in pune and mumbai, (e) small truck <= 5 lakh
    PlantedSpec("tata_ace_mega_diesel", "pune", 380_000, "d/e"),
    PlantedSpec("tata_ace_mega_diesel", "mumbai", 350_000, "d/e"),
    PlantedSpec("tata_ace_ht_plus_diesel", "mumbai", 480_000, "d/e"),
    PlantedSpec("tata_ace_cng_bifuel", "mumbai", 460_000, "d/e: cng mumbai"),
    PlantedSpec("maruti_super_carry_cng", "pune", 420_000, "e: cng pune"),
    PlantedSpec("mahindra_jeeto_diesel", "lucknow", 300_000, "e"),
    PlantedSpec("tata_ace_gold_petrol", "ahmedabad", 275_000, "e: petrol"),
    # (c) Kolkata has diesel pickups / mini trucks (but no CNG)
    PlantedSpec("ashok_leyland_dost_plus", "kolkata", 450_000, "c/e: kolkata diesel pickup"),
    PlantedSpec("tata_ace_gold_diesel", "kolkata", 320_000, "c/e: kolkata diesel mini_truck"),
    PlantedSpec("mahindra_bolero_pikup_fb_1_3", "kolkata", 560_000, "c: kolkata diesel pickup"),
)

LISTING_COLUMNS = (
    "listing_id", "model_id", "make", "model", "variant", "body_type", "fuel",
    "year", "price_inr", "km_driven", "payload_kg", "gvw_kg", "city",
    "registration_state", "owners", "seller_type", "papers_verified",
    "listing_date", "description",
)


# --------------------------------------------------------------------------
# Data classes
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class VehicleModel:
    """One row of data/models.csv."""

    model_id: str
    make: str
    model: str
    variant: str
    body_type: str
    fuel: str
    payload_kg: int
    gvw_kg: int
    engine_cc: int | None
    new_price_inr_min: int
    new_price_inr_max: int
    launch_year: int
    source_url: str

    @property
    def first_listing_year(self) -> int:
        return max(self.launch_year, MIN_YEAR)

    @property
    def new_price_mid(self) -> float:
        return (self.new_price_inr_min + self.new_price_inr_max) / 2


@dataclass
class Listing:
    """A generated used listing (mutable while edge cases are applied)."""

    model: VehicleModel
    year: int
    price_inr: int
    km_driven: int
    city: str
    owners: int
    seller_type: str
    papers_verified: bool
    listing_date: date
    planted: bool = False
    listing_id: str = ""

    def description(self) -> str:
        """Template sentence built ONLY from this row's own columns."""
        owner_word = "owner" if self.owners == 1 else "owners"
        papers = "papers verified" if self.papers_verified else "papers not verified"
        seller = "a dealer" if self.seller_type == "dealer" else "an individual seller"
        name = f"{self.model.make} {self.model.model} {self.model.variant}"
        return (
            f"{self.year} {name}, {self.km_driven:,} km, {self.owners} {owner_word}, "
            f"{papers}, listed in {self.city.title()} by {seller}."
        )

    def to_row(self) -> dict[str, str]:
        m = self.model
        return {
            "listing_id": self.listing_id,
            "model_id": m.model_id,
            "make": m.make,
            "model": m.model,
            "variant": m.variant,
            "body_type": m.body_type,
            "fuel": m.fuel,
            "year": str(self.year),
            "price_inr": str(self.price_inr),
            "km_driven": str(self.km_driven),
            "payload_kg": str(m.payload_kg),
            "gvw_kg": str(m.gvw_kg),
            "city": self.city,
            "registration_state": CITY_STATE[self.city],
            "owners": str(self.owners),
            "seller_type": self.seller_type,
            "papers_verified": "true" if self.papers_verified else "false",
            "listing_date": self.listing_date.isoformat(),
            "description": self.description(),
        }


# --------------------------------------------------------------------------
# Check collection (works even under `python -O`, unlike bare assert)
# --------------------------------------------------------------------------

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    """Record a failed check; the script exits non-zero at the end if any failed."""
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {message}")
    if not condition:
        FAILURES.append(message)


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_models(path: Path) -> dict[str, VehicleModel]:
    models: dict[str, VehicleModel] = {}
    for row in read_csv(path):
        model = VehicleModel(
            model_id=row["model_id"],
            make=row["make"],
            model=row["model"],
            variant=row["variant"],
            body_type=row["body_type"],
            fuel=row["fuel"],
            payload_kg=int(row["payload_kg"]),
            gvw_kg=int(row["gvw_kg"]),
            engine_cc=int(row["engine_cc"]) if row["engine_cc"] else None,
            new_price_inr_min=int(row["new_price_inr_min"]),
            new_price_inr_max=int(row["new_price_inr_max"]),
            launch_year=int(row["launch_year"]),
            source_url=row["source_url"],
        )
        if model.model_id in models:
            raise ValueError(f"duplicate model_id {model.model_id}")
        models[model.model_id] = model
    return models


# --------------------------------------------------------------------------
# Random generation helpers
# --------------------------------------------------------------------------


def pick_model(rng: random.Random, models: list[VehicleModel]) -> VehicleModel:
    """Pick a body type by segment weight, then a model (fuel-weighted) within it."""
    body_types = list(BODY_TYPE_WEIGHTS)
    weights = [BODY_TYPE_WEIGHTS[b] for b in body_types]
    body_type = rng.choices(body_types, weights=weights, k=1)[0]
    candidates = [m for m in models if m.body_type == body_type]
    model_weights = [FUEL_MODEL_WEIGHTS[m.fuel] for m in candidates]
    return rng.choices(candidates, weights=model_weights, k=1)[0]


def pick_city(rng: random.Random, fuel: str) -> str:
    weights_by_city = FUEL_CITY_WEIGHTS[fuel]
    weights = [weights_by_city[c] for c in CITIES]
    return rng.choices(CITIES, weights=weights, k=1)[0]


def age_of(year: int) -> int:
    return max(CURRENT_YEAR - year, 1)


def round_to(value: float, step: int) -> int:
    return int(round(value / step)) * step


def generate_km(rng: random.Random, model: VehicleModel, year: int) -> int:
    low, high = KM_PER_YEAR[model.body_type]
    km = rng.uniform(low, high) * age_of(year)
    return max(round_to(km, KM_ROUNDING), KM_ROUNDING)


def km_factor(model: VehicleModel, year: int, km: int) -> float:
    """Price multiplier: low-km vehicles fetch a bit more, high-km a bit less."""
    low, high = KM_PER_YEAR[model.body_type]
    typical_km = (low + high) / 2 * age_of(year)
    deviation = km / typical_km - 1
    factor = 1 - KM_EFFECT * deviation
    return min(max(factor, KM_FACTOR_BOUNDS[0]), KM_FACTOR_BOUNDS[1])


def generate_price(rng: random.Random, model: VehicleModel, year: int, km: int) -> int:
    new_price = rng.uniform(model.new_price_inr_min, model.new_price_inr_max)
    rate = rng.uniform(*DEPRECIATION_RANGE)
    depreciated = new_price * (1 - rate) ** age_of(year)
    noise = rng.uniform(1 - PRICE_NOISE, 1 + PRICE_NOISE)
    price = depreciated * km_factor(model, year, km) * noise
    price = max(price, new_price * MIN_RESIDUAL_FRACTION)
    return round_to(price, PRICE_ROUNDING)


def generate_owners(rng: random.Random, year: int) -> int:
    if age_of(year) <= 3:
        return rng.choices((1, 2), weights=(8, 2), k=1)[0]
    return rng.choices((1, 2, 3), weights=(5, 3, 2), k=1)[0]


def generate_listing_date(rng: random.Random) -> date:
    span_days = (LISTING_END - LISTING_START).days
    return LISTING_START + timedelta(days=rng.randint(0, span_days))


def year_for_target_price(model: VehicleModel, target_price: int) -> int:
    """Model year whose typical depreciated price is closest to the target."""
    typical_rate = sum(DEPRECIATION_RANGE) / 2
    best_year = model.first_listing_year
    best_gap = float("inf")
    for year in range(model.first_listing_year, MAX_YEAR + 1):
        typical = model.new_price_mid * (1 - typical_rate) ** age_of(year)
        gap = abs(typical - target_price)
        if gap < best_gap:
            best_year, best_gap = year, gap
    return best_year


def build_listing(
    rng: random.Random,
    model: VehicleModel,
    year: int,
    city: str,
    price_inr: int | None = None,
    planted: bool = False,
) -> Listing:
    km = generate_km(rng, model, year)
    price = generate_price(rng, model, year, km)
    if price_inr is not None:
        price = price_inr
    return Listing(
        model=model,
        year=year,
        price_inr=price,
        km_driven=km,
        city=city,
        owners=generate_owners(rng, year),
        seller_type="dealer" if rng.random() < DEALER_PROBABILITY else "individual",
        papers_verified=rng.random() < PAPERS_VERIFIED_PROBABILITY,
        listing_date=generate_listing_date(rng),
        planted=planted,
    )


def generate_random_listings(
    rng: random.Random, models: list[VehicleModel], count: int
) -> list[Listing]:
    listings = []
    for _ in range(count):
        model = pick_model(rng, models)
        year = rng.randint(model.first_listing_year, MAX_YEAR)
        city = pick_city(rng, model.fuel)
        listings.append(build_listing(rng, model, year, city))
    return listings


def generate_planted_listings(
    rng: random.Random, models_by_id: dict[str, VehicleModel]
) -> list[Listing]:
    listings = []
    for spec in PLANTED_SPECS:
        model = models_by_id[spec.model_id]
        year = year_for_target_price(model, spec.price_inr)
        listings.append(
            build_listing(rng, model, year, spec.city, price_inr=spec.price_inr, planted=True)
        )
    return listings


def city_allows_fuel(city: str, fuel: str) -> bool:
    return FUEL_CITY_WEIGHTS[fuel][city] > 0


def balance_cities(listings: list[Listing]) -> None:
    """Move non-planted listings from the fullest city until every city has the minimum."""
    while True:
        counts = Counter(listing.city for listing in listings)
        sparse_city = min(CITIES, key=lambda c: (counts[c], c))
        if counts[sparse_city] >= MIN_LISTINGS_PER_CITY:
            return
        donor_city = max(CITIES, key=lambda c: (counts[c], c))
        candidates = [
            listing
            for listing in listings
            if listing.city == donor_city
            and not listing.planted
            and city_allows_fuel(sparse_city, listing.model.fuel)
        ]
        if not candidates:
            return  # the per-city check will report the failure
        candidates[0].city = sparse_city


def generate_catalog(models_by_id: dict[str, VehicleModel]) -> list[Listing]:
    rng = random.Random(SEED)
    models = list(models_by_id.values())
    n_random = N_LISTINGS - len(PLANTED_SPECS)
    listings = generate_random_listings(rng, models, n_random)
    listings += generate_planted_listings(rng, models_by_id)
    rng.shuffle(listings)
    balance_cities(listings)
    for index, listing in enumerate(listings, start=1):
        listing.listing_id = f"VH-{index:04d}"
    return listings


def write_listings(path: Path, listings: list[Listing]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LISTING_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for listing in listings:
            writer.writerow(listing.to_row())


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def validate_models(models_by_id: dict[str, VehicleModel]) -> None:
    print("models.csv checks")
    models = list(models_by_id.values())
    check(25 <= len(models) <= 35, f"25-35 model variants (got {len(models)})")
    check(all(m.body_type in BODY_TYPES for m in models), "all body_type values in enum")
    check(all(m.fuel in FUELS for m in models), "all fuel values in enum")
    check(all(0 < m.payload_kg < m.gvw_kg for m in models), "0 < payload_kg < gvw_kg for every model")
    check(
        all(0 < m.new_price_inr_min <= m.new_price_inr_max for m in models),
        "new price band is positive and min <= max",
    )
    check(
        all((m.engine_cc is None) == (m.fuel == "electric") for m in models),
        "engine_cc blank exactly for electric models",
    )
    check(all(m.launch_year <= MAX_YEAR for m in models), "launch_year <= 2025")


def validate_reference_files(models_by_id: dict[str, VehicleModel]) -> None:
    print("aliases.csv / city_neighbors.csv checks")
    canonical_sets = {
        "make": {m.make for m in models_by_id.values()},
        "model": {m.model for m in models_by_id.values()},
        "body_type": set(BODY_TYPES),
        "fuel": set(FUELS),
        "city": set(CITIES),
    }
    aliases = read_csv(ALIASES_CSV)
    check(80 <= len(aliases) <= 150, f"80-150 alias rows (got {len(aliases)})")
    check(all(a["kind"] in ALIAS_KINDS for a in aliases), "all alias kinds valid")
    bad = [a for a in aliases if a["canonical"] not in canonical_sets.get(a["kind"], set())]
    check(not bad, f"every alias canonical exists in models.csv / enums / city list (bad: {bad[:3]})")
    keys = [(a["alias"], a["kind"]) for a in aliases]
    check(len(keys) == len(set(keys)), "no duplicate (alias, kind) pairs")
    check(all(len(a["alias"]) > 1 for a in aliases), "no single-character aliases")
    check(all(a["alias"] == a["alias"].lower().strip() for a in aliases), "aliases are lowercase/trimmed")

    neighbors = read_csv(NEIGHBORS_CSV)
    valid = all(
        n["city"] in CITY_STATE and n["neighbor"] in CITY_STATE and n["city"] != n["neighbor"]
        for n in neighbors
    )
    check(valid, "city_neighbors uses only listing cities, no self-loops")
    per_city = Counter(n["city"] for n in neighbors)
    check(
        all(2 <= per_city[c] <= 3 for c in CITIES),
        "every city has 2-3 neighbors",
    )
    check(all(int(n["distance_km"]) > 0 for n in neighbors), "distances positive")


def validate_listing_columns(rows: list[dict[str, str]], models_by_id: dict[str, VehicleModel]) -> None:
    print("listings.csv column checks")
    check(len(rows) == N_LISTINGS, f"{N_LISTINGS} listings (got {len(rows)})")
    ids = [r["listing_id"] for r in rows]
    check(len(set(ids)) == len(ids), "listing_id unique")
    check(all(r["city"] in CITY_STATE for r in rows), "city values canonical")
    check(all(r["registration_state"] == CITY_STATE[r["city"]] for r in rows), "registration_state matches city")
    year_ok = all(
        models_by_id[r["model_id"]].first_listing_year <= int(r["year"]) <= MAX_YEAR for r in rows
    )
    check(year_ok, "year within max(launch_year, 2012)..2025")
    check(all(int(r["price_inr"]) % PRICE_ROUNDING == 0 for r in rows), "price_inr rounded to 5,000")
    check(all(1 <= int(r["owners"]) <= 3 for r in rows), "owners 1-3")
    check(all(r["seller_type"] in SELLER_TYPES for r in rows), "seller_type enum")
    check(all(r["papers_verified"] in ("true", "false") for r in rows), "papers_verified true|false")
    dates_ok = all(
        LISTING_START <= date.fromisoformat(r["listing_date"]) <= LISTING_END for r in rows
    )
    check(dates_ok, "listing_date within 2026-07-01..2026-10-15")
    spec_ok = all(
        r["make"] == models_by_id[r["model_id"]].make
        and r["model"] == models_by_id[r["model_id"]].model
        and r["variant"] == models_by_id[r["model_id"]].variant
        and r["body_type"] == models_by_id[r["model_id"]].body_type
        and r["fuel"] == models_by_id[r["model_id"]].fuel
        and int(r["payload_kg"]) == models_by_id[r["model_id"]].payload_kg
        and int(r["gvw_kg"]) == models_by_id[r["model_id"]].gvw_kg
        for r in rows
    )
    check(spec_ok, "spec columns copied exactly from models.csv")
    verified_share = sum(r["papers_verified"] == "true" for r in rows) / len(rows)
    check(0.6 <= verified_share <= 0.8, f"papers_verified ~70% true (got {verified_share:.0%})")

    for band_name, (body_types, low, high) in PRICE_BANDS.items():
        prices = [int(r["price_inr"]) for r in rows if r["body_type"] in body_types]
        in_band = sum(low <= p <= high for p in prices)
        share = in_band / len(prices) if prices else 0.0
        check(
            share >= PRICE_BAND_MIN_SHARE,
            f"{band_name}: {share:.0%} of {len(prices)} priced in {low:,}-{high:,}",
        )


def validate_descriptions(listings: list[Listing], rows: list[dict[str, str]]) -> None:
    """Description must be exactly the template rendered from the row's own columns."""
    print("description checks")
    by_id = {listing.listing_id: listing for listing in listings}
    exact = all(r["description"] == by_id[r["listing_id"]].description() for r in rows)
    check(exact, "every description equals the column-only template")
    banned = ("excellent", "good condition", "mint", "well maintained", "best", "great")
    clean = all(not any(word in r["description"].lower() for word in banned) for r in rows)
    check(clean, "no subjective adjectives in descriptions")


def is_small_truck_under_5_lakh(row: dict[str, str]) -> bool:
    return row["body_type"] in ("mini_truck", "pickup") and int(row["price_inr"]) <= FIVE_LAKH


def validate_edge_cases(rows: list[dict[str, str]]) -> None:
    print("planted edge-case checks")
    exact = [r for r in rows if int(r["price_inr"]) == FIVE_LAKH]
    check(len(exact) >= 3, f"a. >=3 listings priced exactly 500000 (got {len(exact)})")
    check(
        any(r["fuel"] == "diesel" and r["body_type"] == "mini_truck" and r["city"] == "pune" for r in exact),
        "a. one of them is a diesel mini_truck in pune",
    )

    just_above = [r for r in rows if 505_000 <= int(r["price_inr"]) <= 520_000]
    check(len(just_above) >= 4, f"b. several listings priced 505000-520000 (got {len(just_above)})")

    cng_kolkata = [r for r in rows if r["fuel"] == "cng" and r["city"] == "kolkata"]
    ev_chennai = [r for r in rows if r["fuel"] == "electric" and r["city"] == "chennai"]
    kolkata_small_diesel = [
        r for r in rows
        if r["city"] == "kolkata" and r["fuel"] == "diesel" and r["body_type"] in ("pickup", "mini_truck")
    ]
    check(not cng_kolkata, f"c. zero cng listings in kolkata (got {len(cng_kolkata)})")
    check(not ev_chennai, f"c. zero electric listings in chennai (got {len(ev_chennai)})")
    check(
        len(kolkata_small_diesel) >= 2,
        f"c. kolkata has diesel pickups/mini trucks (got {len(kolkata_small_diesel)})",
    )

    for city in ("pune", "mumbai"):
        present = {r["model"] for r in rows if r["city"] == city and r["model"] in ACE_NEAR_DUPLICATES}
        check(len(present) >= 2, f"d. {city} has >=2 Ace near-duplicates ({sorted(present)})")

    demo = [r for r in rows if is_small_truck_under_5_lakh(r)]
    demo_cities = {r["city"] for r in demo}
    demo_fuels = {r["fuel"] for r in demo}
    check(len(demo) >= 8, f"e. >=8 'small truck under 5 lakh' matches (got {len(demo)})")
    check(len(demo_cities) >= 3, f"e. spread across >=3 cities (got {len(demo_cities)})")
    check(len(demo_fuels) >= 2, f"e. mix of fuels ({sorted(demo_fuels)})")
    for city in ("pune", "mumbai"):
        check(
            any(r["city"] == city and r["fuel"] == "cng" for r in demo),
            f"e. includes a cng match in {city}",
        )

    city_counts = Counter(r["city"] for r in rows)
    check(
        all(city_counts[c] >= MIN_LISTINGS_PER_CITY for c in CITIES),
        f"f. >= {MIN_LISTINGS_PER_CITY} listings per city (min {min(city_counts[c] for c in CITIES)})",
    )


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------


def print_counter(title: str, counter: Counter[str]) -> None:
    print(f"{title}:")
    for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {key:<14} {count}")


def print_summary(rows: list[dict[str, str]]) -> None:
    print(f"Wrote {len(rows)} listings to {LISTINGS_CSV.relative_to(ROOT)} (seed {SEED})")
    print_counter("By city", Counter(r["city"] for r in rows))
    print_counter("By body_type", Counter(r["body_type"] for r in rows))
    print_counter("By fuel", Counter(r["fuel"] for r in rows))
    demo = sum(is_small_truck_under_5_lakh(r) for r in rows)
    print(f"'small truck under 5 lakh' matches: {demo}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> int:
    models_by_id = load_models(MODELS_CSV)
    listings = generate_catalog(models_by_id)
    write_listings(LISTINGS_CSV, listings)
    rows = read_csv(LISTINGS_CSV)

    print_summary(rows)
    print()
    validate_models(models_by_id)
    validate_reference_files(models_by_id)
    validate_listing_columns(rows, models_by_id)
    validate_descriptions(listings, rows)
    validate_edge_cases(rows)

    if FAILURES:
        print(f"\n{len(FAILURES)} check(s) FAILED")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
