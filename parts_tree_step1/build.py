"""Парсить tree.txt -> tree.json, nodes.csv, edges.csv, import.cypher"""
import re, json, csv, sys
from pathlib import Path

HERE = Path(__file__).parent
VT = {"TRC": "Тягач сідельний", "RGD": "Вантажівка з жорсткою рамою",
      "TRL": "Причіп дишловий", "SMT": "Напівпричіп"}
ALIAS = {"ALL": ["TRC", "RGD", "TRL", "SMT"], "PWR": ["TRC", "RGD"], "TOW": ["TRL", "SMT"]}
LINE = re.compile(r"^(?P<ind> *)(?P<code>\S+) (?P<ua>[^|\[+]+?)(?: \| (?P<en>[^\[+]+?))?(?: \[(?P<ap>[^\]]+)\])?(?P<extra>(?: \+\S+)*)\s*$")


def parse_applies(s):
    out = []
    for t in s.split(","):
        t = t.strip()
        out += ALIAS.get(t, [t])
    bad = [t for t in out if t not in VT]
    if bad:
        raise ValueError(f"невідомий тип ТЗ {bad}")
    return [t for t in VT if t in out]


def build():
    nodes, order, stack, errors = {}, [], [], []
    for n, raw in enumerate((HERE / "tree.txt").read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = LINE.match(raw)
        if not m:
            errors.append(f"рядок {n}: не розпізнано: {raw!r}"); continue
        lvl = len(m["ind"]) // 2
        if len(m["ind"]) % 2 or lvl > len(stack):
            errors.append(f"рядок {n}: неправильний відступ"); continue
        stack = stack[:lvl]
        parent = stack[-1] if stack else None
        nid = f"{parent}.{m['code']}" if parent else m["code"]
        if nid in nodes:
            errors.append(f"рядок {n}: дубль ID {nid}"); continue
        applies = parse_applies(m["ap"]) if m["ap"] else (nodes[parent]["applies"] if parent else list(VT))
        if parent and not set(applies) <= set(nodes[parent]["applies"]):
            errors.append(f"рядок {n}: {nid} застосування ширше за батька")
        kind = "repkit" if m["code"] == "RK" or (parent and nodes[parent]["kind"] == "repkit") else "part"
        nodes[nid] = dict(id=nid, code=m["code"], kind=kind, name_ua=m["ua"].strip(),
                          name_en=(m["en"] or m["ua"]).strip(), level=lvl + 1,
                          parent=parent, extra_parents=m["extra"].split(), applies=applies,
                          children=[])
        nodes[nid]["extra_parents"] = [p[1:] for p in nodes[nid]["extra_parents"]]
        if parent:
            nodes[parent]["children"].append(nid)
        order.append(nid)
        stack.append(nid)
    for nid in order:
        for p in nodes[nid]["extra_parents"]:
            if p not in nodes:
                errors.append(f"{nid}: додатковий батько {p} не існує")
            elif p == nodes[nid]["parent"]:
                errors.append(f"{nid}: додатковий батько дублює основного")
    if errors:
        print("\n".join(errors)); sys.exit(1)
    # зворотні посилання для граничних вузлів
    for nid in order:
        nodes[nid]["linked_children"] = []
    for nid in order:
        for p in nodes[nid]["extra_parents"]:
            nodes[p]["linked_children"].append(nid)
    return nodes, order


def main():
    nodes, order = build()
    roots = [i for i in order if nodes[i]["parent"] is None]
    data = {"vehicle_types": VT, "roots": roots, "nodes": [nodes[i] for i in order]}
    (HERE / "tree.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    with open(HERE / "nodes.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "code", "kind", "name_ua", "name_en", "level", "parent", "extra_parents", "applies", "is_boundary"])
        for i in order:
            x = nodes[i]
            w.writerow([i, x["code"], x["kind"], x["name_ua"], x["name_en"], x["level"], x["parent"] or "",
                        ",".join(x["extra_parents"]), ",".join(x["applies"]), int(bool(x["extra_parents"]))])
    with open(HERE / "edges.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["child", "parent", "type"])
        for i in order:
            x = nodes[i]
            if x["parent"]:
                w.writerow([i, x["parent"], "PART_OF"])
            for p in x["extra_parents"]:
                w.writerow([i, p, "ALSO_PART_OF"])

    q = lambda s: s.replace("\\", "\\\\").replace("'", "\\'")
    lines = ["// Таксономія вузлів запчастин. Ідемпотентно (MERGE).",
             "CREATE CONSTRAINT part_group_id IF NOT EXISTS FOR (g:PartGroup) REQUIRE g.id IS UNIQUE;",
             "CREATE CONSTRAINT vehicle_type_code IF NOT EXISTS FOR (v:VehicleType) REQUIRE v.code IS UNIQUE;"]
    for c, n in VT.items():
        lines.append(f"MERGE (v:VehicleType {{code:'{c}'}}) SET v.name_ua='{q(n)}';")
    for i in order:
        x = nodes[i]
        lines.append(f"MERGE (g:PartGroup {{id:'{i}'}}) SET g.code='{x['code']}', g.name_ua='{q(x['name_ua'])}', "
                     f"g.name_en='{q(x['name_en'])}', g.level={x['level']}, g.kind='{x['kind']}'"
                     + (", g:RepairKit;" if x["kind"] == "repkit" else ";"))
    for i in order:
        x = nodes[i]
        if x["parent"]:
            lines.append(f"MATCH (c:PartGroup {{id:'{i}'}}),(p:PartGroup {{id:'{x['parent']}'}}) MERGE (c)-[:PART_OF {{primary:true}}]->(p);")
        for p in x["extra_parents"]:
            lines.append(f"MATCH (c:PartGroup {{id:'{i}'}}),(p:PartGroup {{id:'{p}'}}) MERGE (c)-[:PART_OF {{primary:false}}]->(p);")
        if x["parent"] is None or x["applies"] != nodes[x["parent"]]["applies"]:
            for a in x["applies"]:
                lines.append(f"MATCH (g:PartGroup {{id:'{i}'}}),(v:VehicleType {{code:'{a}'}}) MERGE (g)-[:APPLIES_TO]->(v);")
    (HERE / "import.cypher").write_text("\n".join(lines) + "\n", encoding="utf-8")

    b = sum(1 for i in order if nodes[i]["extra_parents"])
    lv = {}
    for i in order:
        lv[nodes[i]["level"]] = lv.get(nodes[i]["level"], 0) + 1
    rk = sum(1 for i in order if nodes[i]["kind"] == "repkit")
    print(f"вузлів: {len(order)}, систем: {len(roots)}, граничних: {b}, ремкомплектів: {rk}, по рівнях: {lv}")


if __name__ == "__main__":
    main()
