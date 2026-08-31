# -*- coding: utf-8 -*-
"""ライブ経路の CORNER 特徴生成（V99W2 B-sd16 レーン用。2026-08-19新設）。

fetch_race.py が作る race_json（過去9走に corner_all / pace_first / pace_last /
run_time / margin を保存済み・2026-08-18改修）から、corner_feats.py の定義そのままで
spd_res / mgn_abs / wide4c / pos_gain のレース内zを計算する。

corner_eval.py build（corner_ds.npz）との一致を保証するための要点:
  - SpeedBench は hist/*.json を (date, rid) 順に再生した状態を再現する。
    基準日 date のレースに使うベンチ＝「date より前の日」の全過去走ライン
    （corner_eval.build と同じ: 同日レース分は flush 前なので参照されない）。
  - 再生は corner_bench_cache.json に日別集計でキャッシュ（hist の件数・末尾で指紋管理。
    hist が増えたら自動再構築）。
  - 欠測（値が作れない馬）は z=0 埋め（corner_feats.z_in_race ＝ v99w2_fit と同じ規約）。

usage:
  python3 corner_live.py verify [N]   # hist の N レース(既定8)で corner_ds.npz と照合
既存ファイルは一切変更していない（本ファイルは新規・独立）。
"""
import glob
import json
import os
import sys

import corner_feats as CF

_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(_DIR, "corner_bench_cache.json")
HIST = os.path.join(_DIR, "hist")

# v99w2_fit.CORNER4 と同一順（Z16 の 13〜16 列目）
CORNER4 = ["spd_res", "mgn_abs", "wide4c", "pos_gain"]


# ───────── SpeedBench 日別キャッシュ ─────────
def _fingerprint(files):
    return dict(n_files=len(files),
                first=os.path.basename(files[0]) if files else "",
                last=os.path.basename(files[-1]) if files else "")


def _build_cache():
    """hist 全件を1回読み、日別の (surface, dist//200, baba_idx) 速度合計を集計。"""
    files = sorted(glob.glob(os.path.join(HIST, "*.json")))
    days = {}
    for fp in files:
        try:
            d = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue                      # corner_eval.build と同じ（壊れたファイルは飛ばす）
        date = str(d.get("date", "") or "")
        horses = (d.get("race") or {}).get("horses") or []
        day = days.setdefault(date, {})
        for h in horses:
            for r in (h.get("races") or []):
                t, ds, sf = r.get("run_time"), r.get("dist"), r.get("surface")
                if not t or not ds or not sf or t <= 0:
                    continue              # CF.SpeedBench.feed と同じ棄却条件
                k = f"{sf}|{int(ds) // 200}|{r.get('baba_idx') or 0}"
                s = day.setdefault(k, [0.0, 0])
                s[0] += ds / t
                s[1] += 1
    cache = dict(fingerprint=_fingerprint(files), days=days)
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return cache


def _load_cache():
    files = sorted(glob.glob(os.path.join(HIST, "*.json")))
    if os.path.exists(CACHE):
        try:
            c = json.load(open(CACHE, encoding="utf-8"))
            if c.get("fingerprint") == _fingerprint(files):
                return c
        except Exception:
            pass
    print("corner_bench_cache.json を(再)構築中（hist全件・約10秒）…", file=sys.stderr)
    return _build_cache()


def bench_asof(date):
    """date(YYYYMMDD) より前の hist だけで CF.SpeedBench を再現して返す。"""
    cache = _load_cache()
    sb = CF.SpeedBench()
    date = str(date)
    for day in sorted(cache["days"]):
        if day >= date:
            continue
        for k, (sm, ct) in cache["days"][day].items():
            sf, bkt, bi = k.split("|")
            k3 = (sf, int(bkt), int(bi))
            for tbl, key in ((sb.t3, k3), (sb.t2, k3[:2]), (sb.t1, k3[:1])):
                s = tbl.setdefault(key, [0.0, 0])
                s[0] += sm
                s[1] += ct
    sb.day = date                          # 以後 feed しない前提（参照専用）
    return sb


# ───────── レース1件の corner z ─────────
def corner_z(race, date):
    """race(=fetch_race/histの race dict) の全頭について CORNER4 のレース内zを返す。
       返り値: {num: [spd_res_z, mgn_abs_z, wide4c_z, pos_gain_z]}
       z化は corner_eval.build と同一（全出走馬で z_in_race、欠測は0）。"""
    sb = bench_asof(date)
    horses = race.get("horses") or []
    raw = {h["num"]: CF.feats(h, race, sb) for h in horses}
    Z = {k: CF.z_in_race({n: raw[n][k] for n in raw}) for k in CF.FEATS}
    return {n: [Z[f][n] for f in CORNER4] for n in raw}


# ───────── 検算: corner_ds.npz と照合 ─────────
def verify(n_races=8):
    import numpy as np
    z = np.load(os.path.join(_DIR, "corner_ds.npz"), allow_pickle=False)
    A, rid_arr, feats = z["A"], z["rid"], [str(x) for x in z["feats"]]
    F = len(feats)
    idx = [feats.index(f) for f in CORNER4]
    ridx = A[:, F + 4].astype(int)
    num = A[:, F + 5].astype(int)
    # 期間をまたいで等間隔サンプル
    uniq = sorted(set(ridx.tolist()))
    picks = [uniq[i] for i in
             [int(round(k * (len(uniq) - 1) / max(n_races - 1, 1)))
              for k in range(n_races)]]
    print(f"corner_live 検算: {len(picks)}R を corner_ds.npz と照合")
    worst = 0.0
    for ri in picks:
        rid = str(rid_arr[ri])
        d = json.load(open(os.path.join(HIST, f"{rid}.json"), encoding="utf-8"))
        mine = corner_z(d["race"], str(d["date"]))
        m = ridx == ri
        ds_rows = {int(nm): A[j, idx] for j, nm in zip(np.where(m)[0], num[m])}
        diffs = [abs(mine[nm][c] - ds_rows[nm][c])
                 for nm in ds_rows for c in range(4)]
        mx = max(diffs)
        worst = max(worst, mx)
        print(f"  {rid} ({d['date']}) {len(ds_rows)}頭×4特徴  最大差 {mx:.2e}"
              + ("  ✅" if mx < 1e-6 else "  ❌"))
    print(f"全体最大差 {worst:.2e} → {'一致 ✅' if worst < 1e-6 else '不一致 ❌'}")
    return worst


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "verify":
        verify(int(sys.argv[2]) if len(sys.argv) > 2 else 8)
    else:
        print(__doc__)
