# -*- coding: utf-8 -*-
"""Ver.2-WIN のライブ適用（predict.py から呼ばれる）。
   ユーザーが送る情報（馬柱・自前指数・騎手）だけで「勝つ馬の得点」を再計算し、
   ランキングの 得点/PWin/ランク を置き換える。市場情報は不使用。
   params_v2.json の weights_win が無ければ何もしない(None)。"""
import json, math, os

import fit_v2 as V2

_DIR = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    try:
        return json.load(open(os.path.join(_DIR, name), encoding="utf-8"))
    except Exception:
        return None


def rescore(race, rows):
    """rows(calc.runの出力)を Ver.2-WIN で再採点。成功時は rows を書き換えて dict を返す"""
    pv = _load("params_v2.json")
    if not pv or "weights_win" not in pv:
        return None
    js = _load("jockey_stats.json") or {}
    jmap = js.get("jockeys", {})
    wavg = {r["num"]: r["wavg"] for r in rows}
    raw = {}
    n_hist = 0
    for h in race.get("horses", []):
        ff = V2.horse_feats(h, race)
        ff["wavg"] = wavg.get(h["num"])
        jid = h.get("jockey_id")
        ff["j_top3"] = jmap.get(jid, {}).get("top3") if jid else None
        tid = h.get("trainer_id")
        ff["t_top3"] = js.get("trainers", {}).get(tid, {}).get("top3") if tid else None
        raw[h["num"]] = ff
        if h.get("races"):
            n_hist += 1
    if len(raw) < 5 or n_hist < len(raw)*0.6:
        return None
    X = {k: V2.z_in_race({n: raw[n].get(k) for n in raw}) for k in V2.FEATS}
    engine = "Ver.2-WIN(U2)"
    s = None
    # V3(LambdaRank)があれば優先。lightgbm不在/モデル無しは自動でU2線形にフォールバック
    try:
        import lightgbm as lgb
        mpath = os.path.join(_DIR, "model_v3.txt")
        if os.path.exists(mpath):
            booster = lgb.Booster(model_file=mpath)
            ns = list(raw.keys())
            import numpy as np
            M = np.array([[X[k][n] for k in V2.FEATS] + [len(ns)] for n in ns],
                         dtype=np.float32)
            pred = booster.predict(M)
            s = {n: float(v) for n, v in zip(ns, pred)}
            engine = "Ver.3(LambdaRank)"
    except Exception:
        s = None
    if s is None:
        w = pv["weights_win"]
        s = {n: sum(w[i]*X[k][n] for i, k in enumerate(V2.FEATS)) for n in raw}
    # pwin: softmax→30%クリップ+再正規化(calcと同じ流儀)
    mx = max(s.values())
    e = {n: math.exp(s[n]-mx) for n in s}
    Z = sum(e.values())
    p = {n: e[n]/Z for n in e}
    for _ in range(len(p)):
        over = {n: v for n, v in p.items() if v > 0.30 + 1e-12}
        if not over:
            break
        rest = {n: v for n, v in p.items() if n not in over}
        room = 1.0 - 0.30*len(over)
        sm = sum(rest.values())
        for n in over:
            p[n] = 0.30
        if sm > 0:
            for n in rest:
                p[n] = rest[n]/sm*room
    # 表示得点: 100中心のWAvg風スケール(順序=V2-WIN)
    disp = {n: 100.0 + 12.0*s[n] for n in s}
    topd = max(disp.values())
    for r in rows:
        n = r["num"]
        r["wavg"] = round(disp[n], 1)
        r["pwin"] = p[n]*100
        gr = (topd - disp[n]) / topd if topd > 0 else 0
        r["rank"] = ("S" if gr <= 0.03 else "A" if gr <= 0.08 else
                     "B" if gr <= 0.14 else "C" if gr <= 0.30 else "D")
    rows.sort(key=lambda r: -r["wavg"])
    return dict(engine=engine, n=len(raw),
                jockey_used=sum(1 for n in raw if raw[n]["j_top3"] is not None))
