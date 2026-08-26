# -*- coding: utf-8 -*-
"""盘口快照新鲜度守卫 (分析前预警)
========================================================
解决"API 挂了/太久没抓取还用旧盘口出信号"的数据污染风险:
  - snapshot_staleness(): 检查快照文件最新时间, 距当前超过阈值 -> stale
  - 未来时间戳(时钟异常/脏数据) -> 标记 future_rows 异常, 不当作新鲜
纯标准库, 无网络依赖。
"""
import csv
import io
import os
from datetime import datetime, timezone

DEFAULT_STALE_HOURS = 12.0
FUTURE_TOLERANCE_MIN = 60  # 快照时间超过当前时间此分钟数 -> 视为未来脏数据


def _as_utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_ts(s):
    try:
        return _as_utc(datetime.fromisoformat(str(s).strip().replace("Z", "+00:00")))
    except Exception:
        return None


def is_future_snapshot(ts_str, now=None, tol_min=FUTURE_TOLERANCE_MIN):
    """快照时间是否在未来(脏数据/时钟异常)。"""
    dt = _parse_ts(ts_str)
    if dt is None:
        return False
    now = _as_utc(now or datetime.now(timezone.utc))
    return (dt - now).total_seconds() > tol_min * 60


def snapshot_staleness(snap_path, now=None, max_age_hours=DEFAULT_STALE_HOURS):
    """检查快照文件新鲜度。

    返回 dict:
      max_snap_iso  最新(非未来)快照时间 ISO 或 None
      age_hours     最新快照距今小时数 或 None
      stale         是否超过阈值(过期)
      missing       文件缺失/无有效行
      future_rows   未来时间戳脏数据行数
      total_rows    有效时间戳行数
    """
    out = {"max_snap_iso": None, "age_hours": None, "stale": False,
           "missing": True, "future_rows": 0, "total_rows": 0}
    if not snap_path or not os.path.exists(snap_path):
        return out
    now = _as_utc(now or datetime.now(timezone.utc))
    max_snap = None
    future = 0
    total = 0
    with io.open(snap_path, encoding="utf-8", errors="replace") as f:
        rd = csv.reader(f)
        try:
            next(rd)
        except StopIteration:
            return out
        for row in rd:
            if not row or not row[0].strip():
                continue
            dt = _parse_ts(row[0])
            if dt is None:
                continue
            total += 1
            if (dt - now).total_seconds() > FUTURE_TOLERANCE_MIN * 60:
                future += 1
                continue
            if max_snap is None or dt > max_snap:
                max_snap = dt
    out["total_rows"] = total
    out["future_rows"] = future
    if max_snap is None:
        return out
    out["missing"] = False
    out["max_snap_iso"] = max_snap.isoformat()
    age_h = (now - max_snap).total_seconds() / 3600.0
    out["age_hours"] = round(age_h, 1)
    out["stale"] = age_h > float(max_age_hours)
    return out