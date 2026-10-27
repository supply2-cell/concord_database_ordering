"""manufacturers.csv + oem_examples.csv + wabco_prefix.csv -> oem.json, oem.cypher (+ перевірка)"""
import csv, json, re, sys
from pathlib import Path

HERE = Path(__file__).parent
rd = lambda f: list(csv.DictReader(open(HERE / f, encoding="utf-8-sig"), delimiter=";"))
norm = lambda s: re.sub(r"[\s.\-/_]", "", s.upper())
TYPES_ALIAS = {"ALL": ["TRC", "RGD", "TRL", "SMT"]}


def main():
    tree = {n["id"] for n in json.load(open(HERE / "tree.json", encoding="utf-8"))["nodes"]}
    mf, ex, wp, src = rd("manufacturers.csv"), rd("oem_examples.csv"), rd("wabco_prefix.csv"), rd("oem_sources.csv")
    M = {m["code"]: m for m in mf}
    S = {s["id"]: s for s in src}
    err, warn = [], []
    for m in mf:
        m["supplies"] = [x for x in m["supplies"].split(",") if x]
        m["applies"] = sum((TYPES_ALIAS.get(t, [t]) for t in m["applies"].split(",") if t), [])
        for s in m["supplies"]:
            if s not in tree: err.append(f"{m['code']}: вузол {s} не існує")
    for p in wp:
        if p["node"] not in tree: err.append(f"WABCO {p['prefix']}: вузол {p['node']} не існує")
    seen = set()
    for e in ex:
        e["norm"] = norm(e["oem"])
        if e["manufacturer"] not in M: err.append(f"{e['oem']}: виробник {e['manufacturer']} не існує")
        if e["node"] not in tree: err.append(f"{e['oem']}: вузол {e['node']} не існує")
        if e["source"] not in S: err.append(f"{e['oem']}: джерело {e['source']} не існує")
        key = (e["manufacturer"], e["norm"])
        if key in seen: err.append(f"дубль {key}")
        seen.add(key)
        rx = M.get(e["manufacturer"], {}).get("oem_regex")
        if rx and not re.match(rx, e["norm"]):
            warn.append(f"{e['manufacturer']} {e['oem']} ({e['norm']}) не відповідає шаблону {rx}")
        if e["manufacturer"] == "BPW":
            e["is_repkit_by_number"] = e["norm"].startswith("09801")
            if e["is_repkit_by_number"] and ".RK" not in e["node"] and not e["node"].endswith("PAD"):
                warn.append(f"BPW {e['oem']}: номер ремкомплекту, а вузол {e['node']}")
        if e["manufacturer"] == "WABCO":
            hit = [p for p in wp if e["norm"].startswith(p["prefix"])]
            if hit and hit[0]["node"] != e["node"]:
                warn.append(f"WABCO {e['oem']}: префікс каже {hit[0]['node']}, а вузол {e['node']}")
    # хто з шаблонів «перехоплює» чужі номери
    for e in ex:
        others = [c for c, m in M.items() if c != e["manufacturer"] and m["oem_regex"] and re.match(m["oem_regex"], e["norm"])]
        e["ambiguous_with"] = others
    if err:
        print("\n".join(err)); sys.exit(1)
    print("\n".join("УВАГА: " + w for w in warn))

    json.dump({"manufacturers": mf, "examples": ex, "wabco_prefix": wp, "sources": src},
              open(HERE / "oem.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    q = lambda s: s.replace("\\", "\\\\").replace("'", "\\'")
    L = ["CREATE CONSTRAINT oem_key IF NOT EXISTS FOR (o:OEM) REQUIRE o.key IS UNIQUE;",
         "CREATE INDEX oem_norm IF NOT EXISTS FOR (o:OEM) ON (o.norm);"]
    for m in mf:
        L.append(f"MERGE (n:Manufacturer {{id:'{m['code']}'}}) SET n.name='{q(m['name'])}', n.role='{m['role']}', "
                 f"n.oem_format='{q(m['oem_format'])}', n.oem_regex='{q(m['oem_regex'])}', n.notes='{q(m['notes'])}';")
        for s in m["supplies"]:
            L.append(f"MATCH (n:Manufacturer {{id:'{m['code']}'}}),(g:PartGroup {{id:'{s}'}}) MERGE (n)-[:SUPPLIES]->(g);")
        for t in m["applies"]:
            L.append(f"MATCH (n:Manufacturer {{id:'{m['code']}'}}),(v:VehicleType {{code:'{t}'}}) MERGE (n)-[:FOR_TYPE]->(v);")
    for e in ex:
        k = f"{e['manufacturer']}:{e['norm']}"
        s = S[e["source"]]
        L.append(f"MERGE (o:OEM {{key:'{q(k)}'}}) SET o.number='{q(e['oem'])}', o.norm='{e['norm']}', "
                 f"o.name_ua='{q(e['name_ua'])}', o.variant='{q(e['applies_note'])}', o.source='{q(s['title'])}', o.source_url='{q(s['url'])}';")
        L.append(f"MATCH (o:OEM {{key:'{q(k)}'}}),(m:Manufacturer {{id:'{e['manufacturer']}'}}) MERGE (o)-[:MADE_BY]->(m);")
        L.append(f"MATCH (o:OEM {{key:'{q(k)}'}}),(g:PartGroup {{id:'{e['node']}'}}) MERGE (o)-[:IN_GROUP]->(g);")
    (HERE / "oem.cypher").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"виробників {len(mf)} (причепи {sum(m['role']=='trailer' for m in mf)}, вузли {sum(m['role']=='component' for m in mf)}), "
          f"OEM-прикладів {len(ex)}, з них неоднозначних за шаблоном {sum(bool(e['ambiguous_with']) for e in ex)}")


if __name__ == "__main__":
    main()
