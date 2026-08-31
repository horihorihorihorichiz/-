# -*- coding: utf-8 -*-
"""書き出した配点が「評価時のモデルと同じもの」かを検証する（2026-08-22新設・再発防止①）。

背景: 2026-08-22の監査で、書き出した配点表がクラス層を潰した別物になっており、
実測するとVAL55.8/CONF55.9(勝者は56.5/57.0)＝上乗せがほぼ消えるバグが見つかった。
評価に使ったモデルと、書き出した成果物が同一である保証がどこにも無かったのが原因。

このスクリプトは **成果物(hori52_w.json)だけから** スコア関数を組み立てて
VAL/CONFを実測し、jsonに記録された主張値(claims)と照合する。
一致したら verify_export.ok に jsonのsha256を書き、selfcheckがそれを検査する。
→ 配点を書き出したら必ずこれを回す。回していなければselfcheckが落ちる。

usage: python3 verify_export.py            # 検証して .ok を更新
       python3 verify_export.py --claims   # 現在の実測値をclaimsとしてjsonに書き込む(初回用)
"""
import json, hashlib, sys, os, datetime
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V, v99w2_fit as V2

ART = "hori52_w.json"
OK = "verify_export.ok"
TOL = 0.25          # pt。丸め誤差のみ許容


def scorer_from_artifact(d):
    """jsonの中身**だけ**からスコア関数を作る（学習コードを一切通らない）。"""
    wg = np.array(d["wg"])
    w6 = {k: np.array(v) for k, v in d["w6"].items()}
    w30 = {k: np.array(v) for k, v in d["w30"].items()}
    w52 = {k: np.array(v) for k, v in d["w52"].items()}
    mix = d["mix"]

    def wfn(r):
        b = w30.get(f"{r['surface']}{r['dist_cat']}/t{r['tier']}")
        if b is None:
            b = w6.get(f"{r['surface']}{r['dist_cat']}", wg)
        c = w52.get(f"{r.get('venue')}{r['surface']}{r['dist_cat']}")
        return b if c is None else mix * c + (1 - mix) * b
    return wfn


def ev(races, wfn):
    n = len(races); t3 = 0; cost = ret = 0
    for r in races:
        s = r["Z16"] @ wfn(r)
        o = sorted(range(len(s)), key=lambda i: (-s[i], -r["wavg"][i], r["nums"][i]))
        t3 += int(o[0] in set(r["top3"]))
        pl = {int(k): float(v) for k, v in ((r["payout"] or {}).get("複勝") or {}).items()}
        for i in o[:2]:
            cost += 100; ret += pl.get(r["nums"][i], 0.0)
    return round(t3 / n * 100, 2), round(ret / cost * 100, 2)


def main():
    d = json.load(open(ART))
    races = V.load_races(); V2.attach_corner(races)
    seg = lambda lo, hi: [r for r in races if lo <= r["month"] <= hi]
    VAL, CONF = seg('202603', '202605'), seg('202606', '202608')
    wfn = scorer_from_artifact(d)
    got = {"VAL": ev(VAL, wfn), "CONF": ev(CONF, wfn)}
    print(f"成果物だけから再構成したモデルの実測: VAL {got['VAL']} / CONF {got['CONF']}")

    if "--claims" in sys.argv:
        d["claims"] = {"VAL": got["VAL"], "CONF": got["CONF"],
                       "note": "成果物のみから再構成したモデルの3着内率/複勝2点ROI。verify_export.pyが照合する"}
        json.dump(d, open(ART, "w"), ensure_ascii=False, indent=1)
        print("claimsをjsonへ書き込んだ")
        d = json.load(open(ART))

    cl = d.get("claims")
    if not cl:
        print("❌ claimsが無い。--claims で書き込んでから使う"); return 1
    ok = all(abs(got[k][i] - cl[k][i]) <= TOL for k in ("VAL", "CONF") for i in (0, 1))
    if not ok:
        print(f"❌ 不一致: 主張{cl} vs 実測{got}。書き出しコードが評価時と別モデルを吐いている"); return 1
    sha = hashlib.sha256(open(ART, "rb").read()).hexdigest()
    json.dump({"sha256": sha, "verified": got,
               "at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")},
              open(OK, "w"))
    print(f"✅ 一致。{OK} を更新 (sha {sha[:12]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
