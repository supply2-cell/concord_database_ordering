"""Друга хвиля ремкомплектів: додає дочірній вузол RK до вказаних деталей (пропускає, якщо RK уже є)."""
from pathlib import Path

P = Path(__file__).parent / "tree.txt"
KITS = {
 "ENG.BLK.MOUNT": ("Ремкомплект опор двигуна", "Engine mount kit"),
 "ENG.HEAD.HEAD": ("Ремкомплект ГБЦ (прокладки)", "Cylinder head gasket set"),
 "ENG.LUB.OILPUMP": ("Ремкомплект масляного насоса", "Oil pump repair kit"),
 "ENG.COOL.FAN": ("Ремкомплект віскомуфти", "Viscous fan clutch repair kit"),
 "ENG.EXH.ADBLUE": ("Ремкомплект насоса / дозатора AdBlue", "AdBlue pump repair kit"),
 "ENG.ACC.ACCOMP": ("Ремкомплект компресора кондиціонера", "A/C compressor repair kit"),
 "ENG.ACC.BELT": ("Ремкомплект приводу ременя (натягувач, ролики)", "Belt drive kit"),
 "TRN.GBX.ACTUAT": ("Ремкомплект актуатора КПП", "AMT actuator repair kit"),
 "TRN.GBX.RET": ("Ремкомплект ретардера", "Retarder repair kit"),
 "TRN.GBX.PTO": ("Ремкомплект КВП", "PTO repair kit"),
 "TRN.PROP.SHAFT": ("Ремкомплект карданного вала (шліци)", "Propshaft repair kit"),
 "TRN.PROP.UJ": ("Ремкомплект хрестовини", "Universal joint repair kit"),
 "TRN.PROP.CBR": ("Ремкомплект підвісного підшипника", "Centre bearing repair kit"),
 "TRN.AXL.MDIFF": ("Ремкомплект міжосьового диференціала", "Inter-axle differential repair kit"),
 "CHS.SUS.LEAF.SHACK": ("Ремкомплект сережки ресори", "Spring shackle repair kit"),
 "CHS.SUS.ROD.BUSH": ("Ремкомплект сайлентблоків тяг", "Torque rod bush kit"),
 "CHS.SUS.STAB.LINK": ("Ремкомплект тяги стабілізатора", "Stabiliser link repair kit"),
 "CHS.SUS.STAB.BUSH": ("Ремкомплект втулок стабілізатора", "Stabiliser bush kit"),
 "CHS.SUS.SHOCK": ("Ремкомплект кріплення амортизатора (втулки)", "Shock absorber bush kit"),
 "STR.COL": ("Ремкомплект кардана рульової колонки", "Steering column joint repair kit"),
 "STR.DLINK": ("Ремкомплект поздовжньої тяги", "Drag link repair kit"),
 "STR.TLINK": ("Ремкомплект поперечної тяги", "Tie rod repair kit"),
 "STR.BALL": ("Ремкомплект наконечника тяги", "Tie rod end repair kit"),
 "PNE.HEAD": ("Ремкомплект пневмоголовки (ущільнювачі)", "Coupling head seal kit"),
 "BRK.CTRL.QRV": ("Ремкомплект клапана швидкого розгальмування", "Quick release valve repair kit"),
 "BRK.ABS.SENS": ("Ремкомплект датчика ABS (втулка, мастило)", "ABS sensor bush kit"),
 "BRK.WHB.DISC.PAD": ("Ремкомплект колодок (пружини, планка-фіксатор)", "Pad retainer kit"),
 "CPL.DRAW.BAR": ("Ремкомплект кріплення дишла (втулки, пальці)", "Drawbar bush kit"),
 "CPL.DRAW.TURN": ("Ремкомплект поворотного круга", "Turntable repair kit"),
 "CAB.SHELL.MIRR": ("Ремкомплект дзеркала", "Mirror repair kit"),
 "CAB.SHELL.WIPER": ("Ремкомплект трапеції склоочисника", "Wiper linkage repair kit"),
 "CAB.SUSP.BUSH": ("Ремкомплект сайлентблоків кабіни", "Cab mount bush kit"),
 "CAB.INT.SEAT": ("Ремкомплект сидіння", "Seat repair kit"),
 "CAB.INT.PEDAL": ("Ремкомплект педального вузла", "Pedal box repair kit"),
 "CAB.HVAC.PARK": ("Ремкомплект автономного обігрівача", "Parking heater repair kit"),
 "BOD.CURT.ROOF": ("Ремкомплект зсувного даху", "Sliding roof repair kit"),
 "BOD.BOX.DOOR": ("Ремкомплект завіс / замків воріт", "Rear door hinge & lock kit"),
 "BOD.TANKR.VALVE": ("Ремкомплект клапанів цистерни", "Tanker valve repair kit"),
}

lines = P.read_text(encoding="utf-8").splitlines()
info, stack = [], []
for raw in lines:
    if not raw.strip() or raw.lstrip().startswith("#"):
        info.append((None, None)); continue
    ind = (len(raw) - len(raw.lstrip())) // 2
    stack = stack[:ind]; code = raw.split()[0]
    info.append((".".join(stack + [code]), ind)); stack.append(code)
ids = {f for f, _ in info if f}
missing = set(KITS) - ids
assert not missing, missing

inserts = {}  # індекс рядка, після якого вставити
for k, (fid, ind) in enumerate(info):
    if fid in KITS and fid + ".RK" not in ids:
        j = k + 1
        while j < len(info) and info[j][1] is not None and info[j][1] > ind:
            j += 1
        ua, en = KITS[fid]
        inserts.setdefault(j - 1, []).append("  " * (ind + 1) + f"RK {ua} | {en}")
out = []
for k, raw in enumerate(lines):
    out.append(raw)
    out += inserts.get(k, [])
P.write_text("\n".join(out) + "\n", encoding="utf-8")
print("додано:", sum(len(v) for v in inserts.values()))
