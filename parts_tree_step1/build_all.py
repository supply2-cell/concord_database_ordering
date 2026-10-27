"""Збирає все: дерево, техніку, OEM і переглядач parts_tree.html"""
import subprocess, sys
from pathlib import Path
H = Path(__file__).parent
for s in ["build.py", "build_vehicles.py", "build_oem.py"]:
    subprocess.run([sys.executable, str(H / s)], check=True)
t = (H / "viewer_template.html").read_text(encoding="utf-8")
for k, f in [("/*__DATA__*/null", "tree.json"), ("/*__VEH__*/null", "vehicles.json"), ("/*__OEM__*/null", "oem.json")]:
    t = t.replace(k, (H / f).read_text(encoding="utf-8"))
(H / "parts_tree.html").write_text(t, encoding="utf-8")
# один файл для Neo4j у правильному порядку
(H / "import_all.cypher").write_text("".join((H / f).read_text(encoding="utf-8") for f in ["import.cypher", "vehicles.cypher", "oem.cypher"]), encoding="utf-8")
print("готово: parts_tree.html, import_all.cypher")
