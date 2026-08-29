# -*- coding: utf-8 -*-
"""実効配点表の完全版を生成（2026-08-22・指示「すべて変えてみて 52ざっと更新して」）。

これまでの成果物は「場の層」と「クラス層」が別ファイルで、手で使うには
2つの表を自分で合成する必要があった。この版は全セルについて合成済みの
**実効配点**（= 0.5×場の層 + 0.5×クラス層）を出す。
= verify_export.py が検証したライブのスコア計算と完全に同じ数式。
場×芝ダ×距離帯(49) × クラス(3/4/5/6/10) = データのある組み合わせ全部。
"""
import json, collections, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V

NAMES = ["TSI","LTS","FSI","Bonus","DSI","NSI","CSI","WAS","TAS","HCS",
         "NRJA","展開乗数","spd_res","mgn_abs","wide4c","pos_gain"]
JP = {"TSI":"TSI タイム指数","LTS":"LTS 上がり","FSI":"FSI 枠×脚質","Bonus":"Bonus TFB/SSC",
      "DSI":"DSI 距離適性","NSI":"NSI クラス実績","CSI":"CSI コース適性","WAS":"WAS 斤量差",
      "TAS":"TAS 道悪適性","HCS":"HCS 馬体重","NRJA":"NRJA 間隔","展開乗数":"展開乗数",
      "spd_res":"spd_res スピード余力","mgn_abs":"mgn_abs 着差","wide4c":"wide4c 4角外回し",
      "pos_gain":"pos_gain 位置取り変化"}
TIERJP = {3:"重賞OP",4:"3勝C",5:"2勝C",6:"1勝C",10:"未勝利"}
BASE = {"TSI":"30","LTS":"30","FSI":"15","Bonus":"15","DSI":"5","NSI":"20",
        "CSI":"13","WAS":"15","TAS":"15"}

d = json.load(open("hori52_w.json"))
wg = np.array(d["wg"]); w6={k:np.array(v) for k,v in d["w6"].items()}
w30={k:np.array(v) for k,v in d["w30"].items()}; w52={k:np.array(v) for k,v in d["w52"].items()}

# 共通スケール（6群の平均TSIが30点）
_t=[w6[g][0]/(np.mean(np.abs(w6[g])) or 1.0) for g in w6]
SCALE=30.0/(np.mean(_t) or 1.0)

# データのある組み合わせを台帳から数える
races=V.load_races()
cnt=collections.Counter()
for r in races:
    if r["month"]<='202602':
        cnt[(f"{r.get('venue')}{r['surface']}{r['dist_cat']}", r["tier"])]+=1

def eff(vcell, sd, tier):
    b = w30.get(f"{sd}/t{tier}", w6.get(sd, wg))
    c = w52.get(vcell)
    return b if c is None else 0.5*c + 0.5*b

lines=["# 堀川システム 実効配点・完全版（2026-08-22）","",
 "**この表1つで完結する。** 場の層とクラス層を50%ずつ合成済みの実効配点で、",
 "ライブのスコア計算(verify_export.pyが検証)と同じ数式。合成の手作業は不要。","",
 "成績(未知2期間・audit_null 0/8生存): VAL 3着内56.5%/複2ROI85.3% ・ CONF 57.0%/84.0%",
 "現行6群比 +2.6pt。ラベルは選択バイアス検証を経て「有望・未確定」(9月新データで最終判定)。","",
 "使い方: 各成分をレース内zスコア化 → 下表の点数を掛けて合算 = S2_Raw。",
 "距離帯: S=1400m以下 / M=1500-1700m / L=1800m以上。40R未満の組は太字なし=クラス層のみ。",""]
ven=["札幌","函館","福島","新潟","東京","中山","中京","京都","阪神","小倉"]
vcells=sorted(w52, key=lambda x:(ven.index(x[:2]) if x[:2] in ven else 99, x))
for vc in vcells:
    sd = vc[2:]
    tiers=[t for t in (3,4,5,6,10) if cnt.get((vc,t),0)>0]
    if not tiers: continue
    lines+=[f"### {vc}","",
      "| 成分 | 99.27 | "+" | ".join(f"{TIERJP[t]}" for t in tiers)+" |",
      "|---|--:|"+"--:|"*len(tiers),
      "| （MINE R数） | — | "+" | ".join(str(cnt[(vc,t)]) for t in tiers)+" |"]
    W={t: eff(vc, sd, t) for t in tiers}
    for j,nm in enumerate(NAMES):
        vals=[]
        for t in tiers:
            w=W[t]; sc=np.mean(np.abs(w)) or 1.0
            vals.append(f"{w[j]/sc*SCALE:.0f}")
        lines.append(f"| {JP[nm]} | {BASE.get(nm,'—')} | "+" | ".join(vals)+" |")
    lines.append("")
open("HORIKAWA_FULL.md","w").write("\n".join(lines))
print(f"wrote HORIKAWA_FULL.md ({len(vcells)}セル × クラス)")
