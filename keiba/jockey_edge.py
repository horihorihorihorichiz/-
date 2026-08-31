# -*- coding: utf-8 -*-
"""17番目の変数「乗り替わりの方向」を、市場と同時に入れた条件付きロジットで1回だけ測る
（2026-08-23・外部助言）。

★事前登録（見てから定義を変えない。規律R3/R5。試行は本定義の1本のみ）:
  変数 J = (今回騎手の較正済み勝率) − (前走騎手の較正済み勝率)
    ・較正済み勝率 = (勝利数 + k·p0) / (騎乗数 + k), k=200, p0=全体勝率
      ※そのレースの**開催日より前**の実績だけで計算する（時系列・リーク無し）
    ・前走騎手は hist台帳から復元（horse_id の直前の出走を探す）
    ・乗り替わりが無い/前走不明の場合は J = 0
  刻み方の候補（格上げ/格下げの3値化、重賞経験差など）は試さない＝掃引しない。

判定: log p_market と同時に入れて J の係数が t>3.0 なら、市場が織り込んでいない情報。
      参考として log p_model も入れた3変数版も併記（既に上乗せゼロと判明済み）。

usage: python3 jockey_edge.py
"""
import json, os, sys, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V
import v99w2_fit as V2
from verify_export import scorer_from_artifact
from calib_check import pwin_from_scores
import cond_logit as CL

EPS = 1e-12
SHRINK = 200


def load_hist(rid):
    try:
        return json.load(open(f"hist/{rid}.json", encoding="utf-8"))
    except Exception:
        return None


def main():
    races = V.load_races()
    V2.attach_corner(races)
    wfn = scorer_from_artifact(json.load(open("hori52_w.json")))
    races = sorted(races, key=lambda r: (r.get("date") or "", r["rid"]))

    # ── 台帳を時系列に走査し、騎手成績と「馬ごとの直前騎手」を育てながら特徴量を作る ──
    jstat = collections.defaultdict(lambda: [0, 0])     # jockey_id -> [starts, wins]
    last_jockey = {}                                    # horse_id -> 直前の騎手
    tot = [0, 0]
    rows, miss, chg = [], 0, 0
    for r in races:
        od = r.get("odds") or {}
        o = np.array([float(od.get(n) or 0) for n in r["nums"]])
        h = load_hist(r["rid"])
        if h is None or (o <= 1.0).any():
            continue
        horses = {x["num"]: x for x in h["race"]["horses"]}
        p0 = tot[1] / tot[0] if tot[0] else 0.07
        J = np.zeros(len(r["nums"]))
        known = 0
        for i, n in enumerate(r["nums"]):
            hh = horses.get(n)
            if not hh:
                continue
            jid, hid = hh.get("jockey_id"), hh.get("horse_id")
            prev = last_jockey.get(hid)
            if jid and prev and prev != jid:
                def rate(j):
                    s, w = jstat[j]
                    return (w + SHRINK * p0) / (s + SHRINK)
                J[i] = rate(jid) - rate(prev)
                known += 1
        chg += known
        s = r["Z16"] @ wfn(r)
        imp = 1.0 / o
        pk = imp / imp.sum()
        pm = pwin_from_scores(s)
        m = r["month"]
        seg = 0 if m <= "202602" else (1 if m <= "202605" else 2)
        w = int(r["top3"][0])
        rows.append((np.column_stack([np.log(pk + EPS), J, np.log(pm + EPS)]), w, seg,
                     None, pk, o, m))
        # 実績の更新（このレース以降にだけ効く）
        win_num = r["nums"][w]
        for n in r["nums"]:
            hh = horses.get(n)
            if not hh:
                continue
            jid, hid = hh.get("jockey_id"), hh.get("horse_id")
            if jid:
                jstat[jid][0] += 1
                tot[0] += 1
                if n == win_num:
                    jstat[jid][1] += 1
                    tot[1] += 1
                if hid:
                    last_jockey[hid] = jid
    seg = np.array([x[2] for x in rows])
    mine = np.where(seg == 0)[0]
    print(f"対象 {len(rows):,}レース / 乗り替わり検出 {chg:,}頭 "
          f"(1レースあたり{chg/max(len(rows),1):.1f}頭) / 騎手 {len(jstat):,}人")

    def sub(cols):
        return [(x[0][:, cols], x[1], x[2], x[3], x[4], x[5], x[6]) for x in rows]

    base = sub([0])                       # 市場のみ
    b0, _ = CL.fit(base, mine, K=1)
    ll0 = {}
    for si, nm in ((1, "VAL"), (2, "CONF")):
        idx = np.where(seg == si)[0]
        ll0[nm] = CL.loglik(b0, base, idx) / len(idx)
    print(f"基準線: 市場のみ VAL {ll0['VAL']:.4f} / CONF {ll0['CONF']:.4f}\n")

    print(f"{'モデル':<28}{'変数':<16}{'係数':>10}{'SE':>8}{'t値':>8}{'VAL上乗せ':>11}{'CONF上乗せ':>11}")
    for cols, label, names in (([0, 1], "市場+乗り替わり", ["log p_market", "J(乗り替わり)"]),
                               ([0, 1, 2], "市場+乗り替わり+堀川",
                                ["log p_market", "J(乗り替わり)", "log p_model"])):
        data = sub(cols)
        beta, cov = CL.fit(data, mine, K=len(cols))
        se = np.sqrt(np.diag(cov))
        ups = []
        for si, nm in ((1, "VAL"), (2, "CONF")):
            idx = np.where(seg == si)[0]
            ups.append(CL.loglik(beta, data, idx) / len(idx) - ll0[nm])
        for i, nmv in enumerate(names):
            u = f"{ups[0]:>+11.4f}{ups[1]:>+11.4f}" if i == 0 else ""
            print(f"{label if i==0 else '':<28}{nmv:<16}{beta[i]:>10.4f}{se[i]:>8.4f}"
                  f"{beta[i]/se[i]:>8.2f}{u}")
        if label.endswith("乗り替わり"):
            t = beta[1] / se[1]
            print(f"  → 判定: J の t={t:.2f} "
                  + ("★市場が織り込んでいない情報あり(t>3.0)" if abs(t) > 3.0
                     else "規律R5のハードル(t>3.0)に届かない＝エッジと認めない"))
    json.dump({"n_races": len(rows), "n_changes": chg}, open("jockey_edge.json", "w"))
    print("\nsaved jockey_edge.json")


if __name__ == "__main__":
    main()
