# Citations

## Data sources

Vehicle specs in `data/models.csv` (payload, GVW, engine cc, approximate ex-showroom new-price band, launch year) were taken from the public pages below, checked in October 2026. These aggregator pages often disagree with each other. Where they conflicted, one plausible figure was picked. Prices are indicative ex-showroom figures, and launch years are approximate.

All listings in `data/listings.csv` are **synthetic**. They were produced by `scripts/generate_catalog.py` (seed 42).

### Pages used (by domain)

**trucksbuses.com**
- https://trucksbuses.com/scv/pickups-and-mini-trucks/tata-ace-gold/specifications (Tata Ace Gold Diesel)
- https://trucksbuses.com/web-stories/tata-ace-gold-cng-diesel-petrol-ht-gvw-payload-body-length (Tata Ace CNG Bi-Fuel)
- https://www.trucksbuses.com/compare-scv-pick-ups-mini-trucks-vans/tata-ace-mega-vs-Tata-Ace-HT-Plus (Tata Ace HT Plus)
- https://www.trucksbuses.com/scv/pickups-and-mini-trucks/tata-ace-ev-electric/specifications (Tata Ace EV Standard)
- https://www.trucksbuses.com/scv/pickups-and-mini-trucks/tata-ace-ev-1000/specifications (Tata Ace EV 1000)
- https://www.trucksbuses.com/compare-scv-pick-ups-mini-trucks-vans/tata-intra-v30-vs-tata-intra-v50 (Tata Intra V50)
- https://trucksbuses.com/scv/pickups-and-mini-trucks/tata-yodha-2-0/specifications (Tata Yodha 2.0)
- https://trucksbuses.com/scv/pickups-and-mini-trucks/mahindra-bolero-maxx-pikup-city-3000-lx (Mahindra Bolero Maxx Pik-Up City 3000 LX)
- https://www.trucksbuses.com/scv/pickups-and-mini-trucks/mahindra-bolero-maxx-hd-pikup-1-7l-vxi/price (Mahindra Bolero Maxx Pik-Up HD 1.7L VXi)
- https://www.trucksbuses.com/scv/pickups-and-mini-trucks/mahindra-supro-profit-truck-maxi/specifications (Mahindra Supro Profit Truck Maxi)
- https://trucksbuses.com/scv/pickups-and-mini-trucks/ashok-leyland-dost-plus/specifications (Ashok Leyland Dost Plus)
- https://www.trucksbuses.com/scv/pickups-and-mini-trucks/maruti-suzuki-super-carry-cng (Maruti Suzuki Super Carry CNG)
- https://www.trucksbuses.com/trucks/cargo-truck/tata-407-gold-sfc (Tata 407 Gold SFC)
- https://www.trucksbuses.com/trucks/tipper/tata-signa-2823-k/specifications (Tata Signa 2823.K tipper)
- https://www.trucksbuses.com/trucks/tipper/bharatbenz-2828c (BharatBenz 2828C tipper)

**91trucks.com**
- https://91trucks.com/compare-truck/tata-intra-v30-vs-tata-intra-v50 (Tata Intra V30)
- https://91trucks.com/trucks/eicher/pro-3015/specifications (Eicher Pro 3015)
- https://91trucks.com/compare-auto-rickshaws/bajaj-maxima-c-diesel-vs-piaggio-ape-xtra-ldx (Bajaj Maxima C Diesel)

**trucks.tractorjunction.com**
- https://trucks.tractorjunction.com/en/mahindra-truck/bolero-pickup/price/khargone (Mahindra Bolero Pik-Up FB 1.3)
- https://trucks.tractorjunction.com/en/compare/mahindra+treo-zor-vs-mahindra+jeeto (Mahindra Jeeto Diesel)
- https://trucks.tractorjunction.com/en/maruti-suzuki-truck/eeco-cargo/price/dewas (Maruti Suzuki Eeco Cargo Petrol and CNG)
- https://trucks.tractorjunction.com/en/piaggio-truck/ape-xtra-ldx/price/jalandhar (Piaggio Ape Xtra LDX)

**Other**
- https://tractorkarvan.com/compare-commercial-vehicle/super-carry-petrol-vs-super-carry-chassis-cng (Maruti Suzuki Super Carry Petrol)
- https://coachbuildersindia.com/price-of-ashok-leyland-bada-dost-i4/ (Ashok Leyland Bada Dost i4)
- https://www.timesdrive.in/eicher/pro-2059/specification (Eicher Pro 2059)
- https://www.drivespark.com/trucks/eicher/pro-2110xp/ (Eicher Pro 2110 XP)
- https://evreporter.com/mahindra-electric-launches-treo-zor/ (Mahindra Treo Zor)

### Rows marked `estimate`

These rows have `source_url = estimate` because the numbers could not be confirmed on a public page:

- `tata_ace_gold_petrol`: price band partly from the Ace Gold family page; payload and GVW estimated
- `tata_ace_mega_diesel`: older model with no current spec page; all figures estimated
- `mahindra_jeeto_cng`
- `mahindra_supro_mini_cng`
- `eicher_pro_2049_standard`
- `tata_lpt_1109_cab_chassis`
- `bajaj_maxima_c_cng`

### Partially estimated fields in sourced rows

- Tipper payloads (`tata_signa_2823k_tipper`, `bharatbenz_2828c_tipper`, 17,000 kg each) were estimated from GVW minus typical kerb weight. The source pages did not give a clear payload figure.
- `bharatbenz_2828c_tipper` engine cc (7,200, OM926) and launch year were estimated.
- `bajaj_maxima_c_diesel` engine cc (470) was estimated.
- `tata_ace_ht_plus_diesel` GVW (1,870) was estimated because sources conflicted (900 vs 1,100 kg payload).
- `mahindra_jeeto_diesel` payload (700) was estimated: the source lists 600 kg generically and a 1,605 kg GVW for the diesel.
- Launch years are approximate throughout. They are only used to set the earliest listing year, with a floor of 2012.
