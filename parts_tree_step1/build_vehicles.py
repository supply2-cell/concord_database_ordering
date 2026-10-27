"""vehicles.txt -> vehicles.json, vehicles.csv, vehicles.cypher"""
import re, json, csv, sys
from pathlib import Path

HERE = Path(__file__).parent
TYPES = {"TRC": "Тягач сідельний", "RGD": "Вантажівка з жорсткою рамою", "LCV": "Легкий вантажний до 3,5 т"}
LINE = re.compile(r"^(?P<ind> *)(?P<code>\S+) (?P<name>.+?)(?: \[(?P<t>[^\]]+)\])?(?: (?P<y1>\d{4})-(?P<y2>\d{4})?)?(?: \{(?P<e>[^}]*)\})?\s*$")


def main():
    rows, stack, err = [], [], []
    for n, raw in enumerate((HERE / "vehicles.txt").read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = LINE.match(raw)
        lvl = len(m["ind"]) // 2 if m else -1
        if not m or lvl > len(stack) or lvl > 2:
            err.append(f"рядок {n}: {raw!r}"); continue
        stack = stack[:lvl]
        par = stack[-1] if stack else None
        rid = f"{par['id']}.{m['code']}" if par else m["code"]
        types = [t.strip() for t in m["t"].split(",")] if m["t"] else (par["types"] if par else [])
        if any(t not in TYPES for t in types):
            err.append(f"рядок {n}: тип {types}")
        r = dict(id=rid, code=m["code"], name=m["name"].strip(),
                 kind=["manufacturer", "range", "generation"][lvl],
                 parent=par["id"] if par else None, types=types,
                 year_from=int(m["y1"]) if m["y1"] else None,
                 year_to=int(m["y2"]) if m["y2"] else None,
                 engines=[e.strip() for e in m["e"].split(",")] if m["e"] else (par["engines"] if par else []))
        rows.append(r); stack.append(r)
    if err:
        print("\n".join(err)); sys.exit(1)

    # покоління = модельний ряд без поколінь або саме покоління → «застосовна модель»
    has_kids = {r["parent"] for r in rows}
    for r in rows:
        r["is_model"] = r["kind"] == "generation" or (r["kind"] == "range" and r["id"] not in has_kids)
    (HERE / "vehicles.json").write_text(json.dumps({"types": TYPES, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    with open(HERE / "vehicles.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "kind", "brand", "range", "name", "types", "year_from", "year_to", "engines", "is_model"])
        by = {r["id"]: r for r in rows}
        for r in rows:
            brand = r["id"].split(".")[0]
            rng = ".".join(r["id"].split(".")[:2]) if r["kind"] != "manufacturer" else ""
            w.writerow([r["id"], r["kind"], by[brand]["name"], by[rng]["name"] if rng else "", r["name"],
                        ",".join(r["types"]), r["year_from"] or "", r["year_to"] or "", ",".join(r["engines"]), int(r["is_model"])])

    q = lambda s: s.replace("\\", "\\\\").replace("'", "\\'")
    L = ["CREATE CONSTRAINT manufacturer_id IF NOT EXISTS FOR (m:Manufacturer) REQUIRE m.id IS UNIQUE;",
         "CREATE CONSTRAINT vmodel_id IF NOT EXISTS FOR (m:VehicleModel) REQUIRE m.id IS UNIQUE;",
         "CREATE CONSTRAINT engine_id IF NOT EXISTS FOR (e:Engine) REQUIRE e.id IS UNIQUE;"]
    for c, n in TYPES.items():
        L.append(f"MERGE (v:VehicleType {{code:'{c}'}}) SET v.name_ua='{q(n)}';")
    for r in rows:
        yrs = f", n.year_from={r['year_from']}" if r["year_from"] else ""
        yrs += f", n.year_to={r['year_to']}" if r["year_to"] else ""
        if r["kind"] == "manufacturer":
            L.append(f"MERGE (n:Manufacturer {{id:'{r['id']}'}}) SET n.name='{q(r['name'])}', n.role='vehicle';")
            continue
        L.append(f"MERGE (n:VehicleModel {{id:'{r['id']}'}}) SET n.name='{q(r['name'])}', n.level='{r['kind']}', "
                 f"n.is_model={str(r['is_model']).lower()}{yrs};")
        if r["kind"] == "range":
            L.append(f"MATCH (n:VehicleModel {{id:'{r['id']}'}}),(m:Manufacturer {{id:'{r['parent']}'}}) MERGE (m)-[:MAKES]->(n);")
        else:
            L.append(f"MATCH (n:VehicleModel {{id:'{r['id']}'}}),(p:VehicleModel {{id:'{r['parent']}'}}) MERGE (p)-[:HAS_GENERATION]->(n);")
        if r["is_model"]:
            for t in r["types"]:
                L.append(f"MATCH (n:VehicleModel {{id:'{r['id']}'}}),(v:VehicleType {{code:'{t}'}}) MERGE (n)-[:OF_TYPE]->(v);")
            for e in r["engines"]:
                eid = r["id"].split(".")[0] + ":" + e
                L.append(f"MERGE (e:Engine {{id:'{q(eid)}'}}) SET e.name='{q(e)}';")
                L.append(f"MATCH (n:VehicleModel {{id:'{r['id']}'}}),(e:Engine {{id:'{q(eid)}'}}) MERGE (n)-[:HAS_ENGINE]->(e);")
    (HERE / "vehicles.cypher").write_text("\n".join(L) + "\n", encoding="utf-8")
    k = lambda x: sum(1 for r in rows if r["kind"] == x)
    print(f"марок {k('manufacturer')}, рядів {k('range')}, поколінь {k('generation')}, "
          f"застосовних моделей {sum(r['is_model'] for r in rows)}, двигунів {len({(r['id'].split('.')[0], e) for r in rows if r['is_model'] for e in r['engines']})}")


if __name__ == "__main__":
    main()
