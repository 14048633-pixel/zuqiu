# -*- coding: utf-8 -*-
"""2026-08-26 审计修正: 台账一次性数据治理(先备份再改, 幂等可重跑)
1) date列统一ISO YYYY-MM-DD(优先kickoff, 次选mm/dd/yyyy解析, 再次scan_ts)
2) snap_age_h<0 的已结算行 -> status=无效(snap<0赛后盘)(防泄漏铁律, 结果保留供审计)
3) Celta Vigo vs CA Osasuna 错配行修正(date按kickoff=2026-08-27, 未来场次status=待结算)
"""
import csv, io, os, re, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "analysis_records", "bet_ledger.csv")
BACKUP = os.path.join(HERE, "analysis_records", "bet_ledger.bak_20260826_audit_fix.csv")


def iso_date(r):
    k = (r.get("kickoff") or "")[:10]
    if re.match(r"^\d{4}-\d{2}-\d{2}$", k):
        return k
    d = (r.get("date") or "").strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", d)
    if m:
        return "%s-%02d-%02d" % (m.group(3), int(m.group(1)), int(m.group(2)))
    st = (r.get("scan_ts") or "")[:10]
    if re.match(r"^\d{4}-\d{2}-\d{2}$", st):
        return st
    return d


def main():
    rows = list(csv.DictReader(io.open(LEDGER, encoding="utf-8-sig")))
    fieldnames = list(rows[0].keys())
    if not os.path.exists(BACKUP):
        shutil.copy2(LEDGER, BACKUP)
        print("备份 ->", BACKUP)
    n_date = n_leak = n_celta = 0
    for r in rows:
        new = iso_date(r)
        if new != (r.get("date") or ""):
            r["date"] = new
            n_date += 1
        # 2) 赛后盘作废迁移
        try:
            leak = float(r.get("snap_age_h") or 999) < 0
        except (TypeError, ValueError):
            leak = False
        if leak and r.get("status") == "已结算":
            r["status"] = "无效(snap<0赛后盘)"
            r["data_note"] = (r.get("data_note") or "") + ";2026-08-26审计:赛后盘作废"
            n_leak += 1
        # 3) 错配行: 西甲 Celta vs Osasuna, date=08-16但kickoff=08-27(未来), scan_ts空
        if (r.get("league") == "西甲" and r.get("home") == "Celta Vigo"
                and r.get("away") == "CA Osasuna" and (r.get("kickoff") or "").startswith("2026-08-27")):
            r["date"] = "2026-08-27"
            if r.get("status") in ("赛果未提取", "待结算", ""):
                r["status"] = "待结算"
                r["result"] = r["ret"] = r["pnl"] = ""
                r["data_note"] = "2026-08-26审计:未来场次待结算(原date/状态错配)"
                n_celta += 1
    with io.open(LEDGER, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("date统一ISO: %d 行 | snap<0迁移无效: %d 行 | 错配行修正: %d 行 | 总行数: %d"
          % (n_date, n_leak, n_celta, len(rows)))


if __name__ == "__main__":
    main()
