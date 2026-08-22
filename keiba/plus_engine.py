# -*- coding: utf-8 -*-
"""PLUSエンジン: 期待値プラスの証明がある買い目だけを出すゲート（2026-08-22）。

指示「買い目が期待値すべてプラスになるように作り変えろ」の実装。
仕組み: plus_fires.json の active にある発火条件に該当した時だけ買い目を出力する。
       active が空の間は全レース見送り(=出力される買い目のEVは全部プラス、を空集合で満たす)。
       発火の追加は昇格試験(R1-R4+事前凍結)を通ったものだけ。ここに手で追加してはいけない。

usage: python3 plus_engine.py <race_id> [...]    # 判定(発火→買い目 / 非発火→見送りと理由)
"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_rank as R
from verify_export import scorer_from_artifact

FIRES = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "plus_fires.json")))


def judge(rid, today=None):
    race, rdate, _ = R.load_race(rid)
    rows, Z = R.scores_for(race)
    Z16, _ = R.z16_for(race, rows, Z, today or rdate)
    art = json.load(open("hori52_w.json"))
    wfn = scorer_from_artifact(art)
    dc = race.get("dist_cat") or ("S" if race["distance"] <= 1400 else
                                  "M" if race["distance"] <= 1700 else "L")
    rr = dict(surface=race["surface"], dist_cat=dc, tier=race.get("today_tier"),
              venue=race.get("venue"))
    w = wfn(rr)
    s = Z16 @ w
    order = sorted(range(len(rows)), key=lambda i: (-s[i], -rows[i]["wavg"], rows[i]["num"]))
    top = [rows[i]["num"] for i in order]

    out = {"rid": rid, "venue": race.get("venue"), "rank": top}
    fired = []
    for f in FIRES["active"]:
        pass          # 発火条件が昇格したらここに判定コードを足す(現在active=[])
    out["fires"] = fired
    if not fired:
        out["verdict"] = "見送り(発火なし)"
        out["note"] = ("現在アクティブな発火条件は0件。期待値プラスの証明を持つ買い方が"
                       "見つかっていないため、これが正しい出力。判定材料は9月中旬の"
                       "オッズドリフト検定で増える(plus_fires.json pending参照)")
    return out


def main():
    for rid in sys.argv[1:]:
        o = judge(rid)
        print(f"── {o['venue']} {rid} ──")
        print(f"  モデル順位: {o['rank'][:6]}...")
        if o["fires"]:
            for f in o["fires"]:
                print(f"  🔥 {f}")
        else:
            print(f"  {o['verdict']}")
            print(f"  {o['note']}")


if __name__ == "__main__":
    main()
