#!/usr/bin/env python3
"""Convert iLMeteo location CSVs into a compact bundled data file.

Input (semicolon-separated, ISO-8859-1, no header):
  ilmeteo_codici_comuni.csv    : ID;comune;sigla_prov;regione
  ilmeteo_codici_province.csv  : ID;provincia;sigla_prov

Output:
  locations.json.gz  -> hierarchical structure for the cascading config flow:
    {
      "regions": {
        "Lombardia": {
          "Milano (MI)": {           # province label
            "Milano": "4427",        # city name -> ilmeteo code
            ...
          },
          ...
        },
        ...
      }
    }

We deliberately drop the foreign-locations file (estero) and the ski file to
keep the bundle small and focused on Italian comuni. Region/province come
straight from the comuni file; the province CSV is only used to expand the
province sigla into a full readable name.
"""
import csv
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def build(comuni_path: str, province_path: str, out_path: str) -> None:
    # sigla -> full province name (e.g. "MI" -> "Milano")
    sigla_to_name: dict[str, str] = {}
    with open(province_path, encoding="latin-1") as f:
        for row in csv.reader(f, delimiter=";"):
            if len(row) < 3:
                continue
            _id, name, sigla = row[0], row[1].strip(), row[2].strip()
            sigla_to_name[sigla] = name

    regions: dict[str, dict[str, dict[str, str]]] = {}
    count = 0
    with open(comuni_path, encoding="latin-1") as f:
        for row in csv.reader(f, delimiter=";"):
            if len(row) < 4:
                continue
            code, comune, sigla, regione = (
                row[0].strip(),
                row[1].strip(),
                row[2].strip(),
                row[3].strip(),
            )
            if not code or not comune:
                continue

            prov_full = sigla_to_name.get(sigla, sigla)
            prov_label = f"{prov_full} ({sigla})" if sigla else prov_full

            regions.setdefault(regione, {}).setdefault(prov_label, {})[comune] = code
            count += 1

    # Sort everything for stable, user-friendly ordering
    sorted_regions: dict[str, dict[str, dict[str, str]]] = {}
    for region in sorted(regions):
        sorted_regions[region] = {}
        for prov in sorted(regions[region]):
            cities = regions[region][prov]
            sorted_regions[region][prov] = {
                c: cities[c] for c in sorted(cities)
            }

    data = {"regions": sorted_regions}

    # Write compressed
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with gzip.open(out_path, "wb", compresslevel=9) as gz:
        gz.write(raw)

    # Stats
    n_regions = len(sorted_regions)
    n_prov = sum(len(p) for p in sorted_regions.values())
    print(f"Comuni processati : {count}")
    print(f"Regioni           : {n_regions}")
    print(f"Province (label)  : {n_prov}")
    print(f"JSON non compresso: {len(raw)/1024:.1f} KB")
    print(f"File compresso    : {os.path.getsize(out_path)/1024:.1f} KB -> {out_path}")


if __name__ == "__main__":
    comuni = sys.argv[1] if len(sys.argv) > 1 else "ilmeteo_codici_comuni.csv"
    province = sys.argv[2] if len(sys.argv) > 2 else "ilmeteo_codici_province.csv"
    out = sys.argv[3] if len(sys.argv) > 3 else "locations.json.gz"
    build(comuni, province, out)
