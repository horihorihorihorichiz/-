# -*- coding: utf-8 -*-
"""Ver.2-WIN のライブ適用（predict.py から呼ばれる）。
   ユーザーが送る情報（馬柱・自前指数・騎手）だけで「勝つ馬の得点」を再計算し、
   ランキングの 得点/PWin/ランク を置き換える。市場情報は不使用。
   params_v2.json の weights_win が無ければ何もしない(None)。"""
import glob, json, math, os

import fit_v2 as V2

_DIR = os.path.dirname(os.path.abspath(__file__))


def _z(s):
    """レース内zスコア化。目的関数の違う複数モデルを同じ土俵に載せてから平均するため。
       二値モデルは出力が確率(0-1)、LambdaRankは順位スコアで、生値のままでは平均できない。"""
    xs = list(s.values())
    m = sum(xs)/len(xs)
    sd = (sum((x-m)**2 for x in xs)/len(xs))**0.5 or 1.0
    return {n: (v-m)/sd for n, v in s.items()}


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
    for h in race.get("horses", []):
        raw[h["num"]].update(V2.extra_strength(h, race))
    X = {k: V2.z_in_race({n: raw[n].get(k) for n in raw}) for k in V2.FEATS + V2.EXTRA_FEATS}
    ctx = V2.race_ctx(race)
    rx = {n: V2.raw_extra(n, raw[n], ctx) for n in raw}
    engine = "Ver.2-WIN(U2)"
    s = None
    # 既定は V3。V4 は KEIBA_ENGINE=v4 で明示的に有効化する。
    # ※patterns.py の g12 閾値は V3 の得点で採掘したもの。V4 は得点の意味が変わる
    #   （二値=勝ち馬確率のレース内z）ので、パターン再採掘が済むまで既定にはしない。
    want_v4 = os.environ.get("KEIBA_ENGINE", "").lower() == "v4"
    try:
        import lightgbm as lgb
        import numpy as np
        ns = list(raw.keys())
        pseudo = dict(X=X, ns=ns, ctx=ctx, raw_extra=rx)

        def run(files, v4, zscore):
            """zscore=True のときだけレース内z化してから平均する。
               V3は単体モデルで、既存パターンのg12閾値が生スコア基準なので z化しない。
               行の形はモデルの特徴数で自動選択: 28=V3 / 36=V4 / 42=V5(+強さ特徴)。"""
            mats = {}

            def mat(v4_, extra):
                key = (v4_, extra)
                if key not in mats:
                    mats[key] = np.array(
                        [V2.build_row(pseudo, n, v4_, extra) for n in ns], dtype=np.float32)
                return mats[key]

            acc, used = {n: 0.0 for n in ns}, 0
            for fp in files:
                b = lgb.Booster(model_file=fp)
                M = None
                for v4_, extra in ((v4, False), (v4, True)):
                    cand = mat(v4_, extra)
                    if b.num_feature() == cand.shape[1]:
                        M = cand
                        break
                if M is None:
                    continue       # 特徴数が合わないモデルは使わない(取り違え防止)
                p = dict(zip(ns, (float(v) for v in b.predict(M))))
                p = _z(p) if zscore else p
                for n in ns:
                    acc[n] += p[n]
                used += 1
            return ({n: acc[n]/used for n in ns}, used) if used else (None, 0)

        if want_v4:
            v4files = sorted(glob.glob(os.path.join(_DIR, "model_v4_s*.txt")))
            s, used = run(v4files, True, True)
            if s:
                engine = f"Ver.4(二値+枠+馬場・{used}種平均)"
        if s is None:
            mp = os.path.join(_DIR, "model_v3.txt")
            if os.path.exists(mp):
                s, used = run([mp], False, False)
                if s:
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
