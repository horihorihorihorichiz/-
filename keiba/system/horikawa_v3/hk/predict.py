# -*- coding: utf-8 -*-
"""予想の出力。順位・上位6頭の印・信頼度の目安・市場とのずれ。"""
import numpy as np

MARKS = ["◎", "○", "▲", "△", "△", "△"]


def shape(s):
    """レースの読みやすさ。得点の段差から 1強／2強／3強／階段／混戦 を決める。"""
    v = np.sort(s)[::-1]
    sd = s.std() or 1.0
    g12 = (v[0] - v[1]) / sd
    g23 = (v[1] - v[2]) / sd if len(v) > 2 else 0.0
    g34 = (v[2] - v[3]) / sd if len(v) > 3 else 0.0
    if g12 >= 0.80:
        return "1強", g12
    if g23 >= 0.70:
        return "2強", g23
    if g34 >= 0.60:
        return "3強", g34
    if g12 >= 0.35 and g23 >= 0.35:
        return "階段", g12
    return "混戦", g12


class Predictor:
    def __init__(self, model, names, calib=None):
        self.m = model
        self.names = names
        self.calib = calib or {}

    def run(self, feat, level="C", top_k=6):
        """feat は features.Builder.build の戻り値。"""
        w = self.m.w(feat["k"], level)
        s = np.asarray(feat["Z"]) @ w
        order = list(np.argsort(-s))
        sh, gap = shape(s)
        pop = feat.get("pop") or []
        base = 100.0 - float(np.mean(s))
        rows = []
        for rank, i in enumerate(order):
            p = pop[i] if i < len(pop) else 0
            rows.append({
                "順位": rank + 1,
                "印": MARKS[rank] if rank < min(top_k, len(MARKS)) else "",
                "馬番": feat["umaban"][i],
                "得点": round(float(s[i]) + base, 1),
                "人気": p or None,
                "市場とのずれ": (p - (rank + 1)) if p else None,
                "_i": i,
            })
        hit = self.calib.get(sh, {})
        return {
            "レース": feat["id"],
            "セル": feat["k"]["C"],
            "使った配点": self._which(feat["k"], level),
            "段階": level,
            "展開": feat.get("pace"),
            "形": sh,
            "段差": round(float(gap), 2),
            "信頼度": {
                "この形での1位が1着": hit.get("win"),
                "この形での上位6頭で3着独占": hit.get("cov"),
                "件数": hit.get("n"),
            },
            "枠": [r["馬番"] for r in rows[:top_k]],
            "並び": rows,
        }

    def _which(self, k, level):
        """内側検証で選ばれた段階に応じて、実際に使った配点を書く。"""
        nn = self.m.n if isinstance(self.m.n, dict) else {}
        if level == "G":
            return "全体1本（内側検証で、これ以上細かくしても良くならないと出た）"
        if level == "L1":
            return f'6群 {k["L1"]}（学習{nn.get("L1", {}).get(k["L1"], 0)}R）'
        if level == "mid":
            return f'場+クラス {k["A"]} × {k["B"]}'
        if k["C"] in self.m.C:
            return f'コース単位 {k["C"]}（学習{nn.get("C", {}).get(k["C"], 0)}R）'
        return f'コース単位は件数不足。親の 場+クラス {k["A"]}×{k["B"]} を使用'


def build_calibration(DS, model, level="C", top_k=6):
    """形（1強〜混戦）ごとの過去の的中率。信頼度の目安に使う。"""
    acc = {}
    for d in DS:
        w = model.w(d["k"], level)
        s = np.asarray(d["Z"]) @ w
        sh, _ = shape(s)
        order = np.argsort(-s)
        rank = np.empty(len(s), int); rank[order] = np.arange(len(s))
        t3 = [d["ord"].index(x) for x in (1, 2, 3) if x in d["ord"]]
        a = acc.setdefault(sh, [0, 0, 0])
        a[0] += 1
        a[1] += (d["ord"][order[0]] == 1)
        a[2] += (len(t3) == 3 and all(rank[i] < top_k for i in t3))
    return {k: {"n": v[0], "win": round(v[1] / v[0] * 100, 1),
                "cov": round(v[2] / v[0] * 100, 1)} for k, v in acc.items()}


def render(res):
    """人が読む形に整える。"""
    L = []
    L.append(f'{res["レース"]}  {res["セル"]}  形={res["形"]}(段差{res["段差"]})  展開={res["展開"]}')
    L.append(f'  配点: {res["使った配点"]}')
    c = res["信頼度"]
    if c.get("件数"):
        L.append(f'  この形の過去{c["件数"]}R: 1位が1着 {c["この形での1位が1着"]}% / '
                 f'上位6頭で3着独占 {c["この形での上位6頭で3着独占"]}%')
    L.append("  印 馬番   得点  人気  ずれ")
    for r in res["並び"][:8]:
        z = r["市場とのずれ"]
        L.append(f'  {r["印"] or "  "} {r["馬番"]:>3}  {r["得点"]:>6}  '
                 f'{(r["人気"] or "-"):>4}  {("+" + str(z) if z and z > 0 else (z if z is not None else "-")):>4}')
    L.append(f'  上位6頭の枠: {res["枠"]}')
    return "\n".join(L)
