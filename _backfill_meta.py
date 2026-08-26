# -*- coding: utf-8 -*-
"""回填台账元数据: 从扫描存档补齐 risk_tags/veto/data_src/snap_age/upset/ct, 复盘找共同点用
无存档匹配的注单标注 data_note=无存档信息
"""
import csv, io, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "analysis_records", "bet_ledger.csv")
ARCH = os.path.join(HERE, "analysis_records", "20260815_scan_upcoming.json")

COLS_ADD = ["data_src", "snap_age_h", "upset_level", "data_note"]


def norm(s):
    return "".join(c.lower() for c in s if c.isalnum())


def main():
    d = json.load(io.open(ARCH, encoding="utf-8"))
    m_by_key = {}
    for m in d.get("matches", []):
        m_by_key[(m.get("league"), norm(m.get("home", "")), norm(m.get("away", "")))] = m
    rows = list(csv.DictReader(io.open(LEDGER, encoding="utf-8")))
    updated = noarch = 0
    for r in rows:
        m = m_by_key.get((r.get("league"), norm(r.get("home", "")), norm(r.get("away", ""))))
        if not m:
            if not r.get("data_note"):
                r["data_note"] = "无存档信息"
                noarch += 1
            continue
        res = m.get("result") or {}
        r["risk_tags"] = ";".join(res.get("risk_tags") or [])
        r["veto"] = 1 if any("否决" in str(x) for x in (res.get("risk_tags") or [])) else 0
        ds = res.get("data_src") or {}
        r["data_src"] = "home=%s/away=%s" % (ds.get("home", "?"), ds.get("away", "?"))
        r["snap_age_h"] = res.get("snap_age_h", "")
        r["upset_level"] = (res.get("upset") or {}).get("level", "")
        r["kickoff"] = m.get("ct", r.get("kickoff", ""))
        note = []
        if "cur" not in (ds.get("home", "") or "") or "cur" not in (ds.get("away", "") or ""):
            note.append("非实时数据")
        if "纯数据无伤病情报" in (r.get("risk_tags") or ""):
            note.append("无伤病情报")
        if "队名模糊匹配" in (r.get("risk_tags") or ""):
            note.append("队名模糊")
        if r.get("veto") == "1":
            note.append("触发否决")
        r["data_note"] = ";".join(note) if note else "数据完整"
        updated += 1
    cols = list(rows[0].keys())
    for c in COLS_ADD:
        if c not in cols:
            cols.append(c)
    with io.open(LEDGER, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("回填 %d 行, 无存档 %d 行" % (updated, noarch))
    print("列:", cols)


if __name__ == "__main__":
    main()
