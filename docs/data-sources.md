# Data sources for the country check and public demo

| Local file | Dataset and source | Licence | Download date | Data rows | CSV columns |
|---|---|---|---|---:|---|
| `data/public/iso3166.csv` | [ISO 3166-1 country and territory codes with UN regional codes, v10.0](https://github.com/lukes/ISO-3166-Countries-with-Regional-Codes/tree/v10.0) ([CSV](https://raw.githubusercontent.com/lukes/ISO-3166-Countries-with-Regional-Codes/v10.0/all/all.csv)) | [CC BY-SA 4.0](https://github.com/lukes/ISO-3166-Countries-with-Regional-Codes/blob/v10.0/LICENSE.md) | 2026-11-21 | 249 | `name`, `alpha-2`, `alpha-3`, `country-code`, `iso_3166-2`, `region`, `sub-region`, `intermediate-region`, `region-code`, `sub-region-code`, `intermediate-region-code` |
| `data/public/sanctions.csv` | [OpenSanctions Consolidated Sanctions](https://www.opensanctions.org/datasets/sanctions/), simplified target export ([snapshot 20261121074704-ixh](https://data.opensanctions.org/artifacts/sanctions/20261121074704-ixh/targets.simple.csv)) | [CC BY-NC 4.0](https://www.opensanctions.org/docs/commercial/exemption/) | 2026-11-21 | 73,934 | `id`, `schema`, `name`, `aliases`, `birth_date`, `countries`, `addresses`, `identifiers`, `sanctions`, `phones`, `emails`, `program_ids`, `dataset`, `first_seen`, `last_seen`, `last_change` |

The versioned OpenSanctions export has SHA-256
`769583d92843fc1b2d442008b46dbc364ccad660248a5e60b6f8e8f7197b1e82`.
If the snapshot has expired, the dataset page links to the current export. A different
snapshot can select different profiles.

## Run locally

From the repository root, create `data/public/` and save the two CSV files there using the
filenames above. Put or link the local `screening/dev` folder at `data/screening/dev`, or pass
`--dev-dir /path/to/screening/dev` to the generator. It copies `name_variants.json` from that
folder.

```sh
python tools/check_countries.py data/public/iso3166.csv
python tools/make_public_demo.py
python system/run data/public_demo output/public_demo.jsonl
```

The demo takes the first six eligible person profiles in ID order and uses the first listed
birth date and country to populate each set of invented customer records. Each profile is copied
into one hit per alert, since the runner emits one decision per hit. In each set of three output
lines the customers have, in order, the matching birth date, a birth date twenty years later,
and a missing birth date. A profile is eligible when it is a person with a birth date, a country
and a name of at least two real parts: the policy cannot confirm a person on a one-part name. The shifted date retains its original precision and uses February 28
if February 29 is unavailable in the destination year.

Keep the downloaded lists, generated data and demo output local.
