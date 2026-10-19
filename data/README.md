# Catalog data

Data layer for the used-commercial-vehicle voice assistant. **All listings are synthetic.** Vehicle specs (payload, GVW, engine, new price band) come from public spec/aggregator pages or are best estimates. They are close to reality but not authoritative. See `../CITATIONS.md`.

## Files

| File | Rows | What it is |
|---|---|---|
| `models.csv` | 35 | Hand-curated real Indian CV variants (Tata, Mahindra, Ashok Leyland, Maruti Suzuki, Eicher, BharatBenz, Piaggio, Bajaj). If a variant is sold in two fuels, each fuel gets its own row. |
| `listings.csv` | 180 | Synthetic used listings, generated from `models.csv` by `scripts/generate_catalog.py`. Do not hand-edit this file; regenerate it. |
| `aliases.csv` | 150 | Spoken, Hinglish, misspelled and likely speech-to-text variants, each mapped to a canonical make / model / body_type / fuel / city value. |
| `city_neighbors.csv` | 25 | 2-3 nearby listing cities per city, with approximate road distances. Used to suggest a nearby city when a search returns nothing. |

## Regenerating

```
python scripts/generate_catalog.py
```

The script uses only the standard library and the seed `random.Random(42)`. Running it again gives a byte-identical `listings.csv`. It prints counts by city, body_type and fuel, then runs about 47 checks: enums, spec consistency, alias canonicals, neighbor cities, descriptions and the planted edge cases. It exits 1 if any check fails.

## Enums (lowercase snake_case)

- `body_type`: `three_wheeler, mini_truck, pickup, cargo_van, lcv, icv, tipper`
- `fuel`: `diesel, petrol, cng, electric`
- `city`: `mumbai, delhi, bengaluru, pune, hyderabad, chennai, ahmedabad, jaipur, lucknow, kolkata`
- `registration_state`: MH (mumbai, pune), DL, KA, TS, TN, GJ, RJ, UP, WB
- `seller_type`: `dealer, individual`
- `papers_verified`: `true, false`
- `aliases.kind`: `make, model, body_type, fuel, city`

## Column dictionary

### models.csv

| Column | Type / unit | Notes |
|---|---|---|
| model_id | text | Stable snake_case key, e.g. `tata_ace_gold_diesel` |
| make | text | Canonical make, e.g. `Tata`, `Ashok Leyland`, `Maruti Suzuki` |
| model | text | Canonical model, e.g. `Ace Gold`, `Bolero Pik-Up`. Alias `model` rows map to this value. |
| variant | text | e.g. `Diesel`, `V30`, `HD 1.7L VXi` |
| body_type | enum | see above |
| fuel | enum | see above |
| payload_kg | int, kg | Rated payload |
| gvw_kg | int, kg | Gross vehicle weight |
| engine_cc | int, cc | **Blank for electric** models |
| new_price_inr_min / new_price_inr_max | int, INR | Approximate ex-showroom new price band |
| launch_year | int | Approximate first model year for this variant/generation |
| source_url | text | Page the specs came from, or `estimate` |

### listings.csv

| Column | Type / unit | Notes |
|---|---|---|
| listing_id | text | `VH-0001` ... `VH-0180` |
| model_id, make, model, variant, body_type, fuel, payload_kg, gvw_kg | | Copied exactly from `models.csv` |
| year | int | `max(launch_year, 2012)` ... 2025 |
| price_inr | int, INR | Asking price, a multiple of 5,000. Starts from the new price, loses 10-15% a year (compounded, ages counted from 2026), is nudged up or down by up to 10% for km driven and by up to 7% noise, and never falls below 18% of the new price. |
| km_driven | int, km | Age x per-segment km/year (3W/mini trucks lowest, ICVs highest), rounded to 500 |
| city | enum | Listing city |
| registration_state | enum | State code of the city |
| owners | int | 1-3 |
| seller_type | enum | `dealer` / `individual` |
| papers_verified | bool | `true` for about 70% of listings |
| listing_date | ISO date | 2026-07-01 ... 2026-10-15 |
| description | text | Template built **only** from this row's columns, with no adjectives. The script checks this. |

Example description: `2024 Tata Ace Gold Diesel, 48,000 km, 1 owner, papers verified, listed in Pune by an individual seller.`

### aliases.csv

`alias` (lowercase, as spoken), `canonical` (exact value in `models.csv` / enum / city list), `kind`. The same alias can appear once per kind. For example, `chota hathi` is both model -> `Ace Gold` and body_type -> `mini_truck`. Single letters are left out on purpose; fuzzy matching handles those. `gurgaon`, `noida` and `ncr` map to the `delhi` listing city.

### city_neighbors.csv

`city`, `neighbor`, `distance_km` (approximate road distance). Rows are directed, so a city can list a neighbor that does not list it back. Kolkata's neighbors (lucknow, hyderabad) are far, but they are the nearest cities in the list.

## Planted edge cases (enforced and checked by the script)

- **a.** At least 3 listings priced exactly Rs 5,00,000 (500000). One is a diesel `mini_truck` in pune (Tata Ace Gold Diesel).
- **b.** Several listings priced Rs 5,05,000-5,20,000, just above 5 lakh, to catch `<` vs `<=` budget bugs.
- **c.** Zero `cng` listings in kolkata and zero `electric` listings in chennai, so zero-result demos are predictable. Kolkata still has diesel pickups and mini trucks.
- **d.** Near-duplicate Ace models (`Ace Gold`, `Ace HT Plus`, `Ace Mega`, `Ace CNG`) are all present in both pune and mumbai.
- **e.** At least 8 matches for "small truck under 5 lakh for city delivery" (`mini_truck` or `pickup`, price <= 500000), spread across several cities and fuels. These include CNG matches in pune and in mumbai.
- **f.** At least 15 listings in every city.

Other realism choices: CNG listings are concentrated in mumbai, delhi, pune and ahmedabad. Electric listings are concentrated in delhi and bengaluru.

## Honesty note

The listings are invented by a seeded generator. No real seller, vehicle or registration is represented. Specs come from aggregator pages (trucksbuses.com, 91trucks.com, tractorjunction, timesdrive, etc.). Those pages often disagree with each other and with themselves, so where they conflicted one plausible figure was picked. Rows with `source_url = estimate` are best guesses.
