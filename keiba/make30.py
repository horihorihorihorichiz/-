# -*- coding: utf-8 -*-
"""芝ダ×距離帯×クラス30セルの配点表を作って書き出す（2026-08-22）。
split30.py で最良となった分け方(λ=0.3・縮小先=6群)をそのまま学習し、
TSI=30点基準の相対点と、Ver.99.27と直接比べられる生スケール点の両方を出す。"""
import json, collections, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V, v99w2_fit as V2

NAMES = ["TSI","LTS","FSI","Bonus","DSI","NSI","CSI","WAS","TAS","HCS",
         "NRJA","展開乗数","spd_res","mgn_abs","wide4c","pos_gain"]
JP = {"TSI":"TSI タイム指数","LTS":"LTS 上がり","FSI":"FSI 枠×脚質","Bonus":"Bonus TFB/SSC",
      "DSI":"DSI 距離適性","NSI":"NSI クラス実績","CSI":"CSI コース適性","WAS":"WAS 斤量差",
      "TAS":"TAS 道悪適性","HCS":"HCS 馬体重","NRJA":"NRJA 間隔","展開乗数":"展開乗数",
      "spd_res":"spd_res スピード余力","mgn_abs":"mgn_abs 着差","wide4c":"wide4c 4角外回し",
      "pos_gain":"pos_gain 位置取り変化"}
TIERJP = {3:"重賞・OP",4:"3勝C",5:"2勝C",6:"1勝C",10:"未勝利・新馬"}

def key(r): return f"{r['surface']}{r['dist_cat']}/t{r['tier']}"
def sd(r):  return f"{r['surface']}{r['dist_cat']}"

races = V.load_races(); V2.attach_corner(races)
K = races[0]["Z16"].shape[1]
MINE = [r for r in races if r["month"] <= '202602']
X,M,W = V2.make_tensor(MINE, key="Z16")
w_all = V2.fit(X,M,W,1.0,w0=np.zeros(K),wstart=np.zeros(K))
by6 = collections.defaultdict(list)
for r in MINE: by6[sd(r)].append(r)
w6 = {}
for k,sub in by6.items():
    Xs,Ms,Ws = V2.make_tensor(sub,key="Z16")
    w6[k] = V2.fit(Xs,Ms,Ws,0.2,w0=w_all,wstart=w_all)
by = collections.defaultdict(list)
for r in MINE: by[key(r)].append(r)
w30, cnt, sdmean = {}, {}, {}
for k,sub in by.items():
    if len(sub) < 40: continue
    base = w6.get(sd(sub[0]), w_all)
    Xs,Ms,Ws = V2.make_tensor(sub,key="Z16")
    w30[k] = V2.fit(Xs,Ms,Ws,0.3,w0=base,wstart=base)
    cnt[k] = len(sub)
    sdmean[k] = np.mean(np.stack([r["sd"] for r in sub]),0)
out = {"axis":"surface+dist_cat/tier","l2":0.3,"names":NAMES,
       "w":{k:[round(float(x),8) for x in v] for k,v in w30.items()},
       "wg":[round(float(x),8) for x in w_all],
       "w6":{k:[round(float(x),8) for x in v] for k,v in w6.items()},
       "n":{k:int(v) for k,v in cnt.items()}}
json.dump(out, open("hori30_w.json","w"), ensure_ascii=False, indent=1)
print(f"セル数 {len(w30)} / 総R {sum(cnt.values())}")

lines = ["# 堀川システム 30分割 配点表（2026-08-22）",
         "", "分け方: **芝ダ×距離帯×クラス**（30セル）。split30.py の44パターン比較で最良。",
         "", "| 分け方 | セル | MINE 3着内 | VALIDATE | CONFIRM | 判定 |",
         "|---|--:|--:|--:|--:|:--|",
         "| **芝ダ×距離帯×クラス λ=0.3** | 30 | 52.6% | **55.7%** | **55.6%** | ○採用 |",
         "| 6群(現行) | 6 | 50.9% | 55.0% | 54.4% | — |",
         "| null(30セル乱数) | 30 | 51.5% | 55.1% | 53.8% | 基準 |",
         "| コース(120) | 120 | 52.8% | 54.9% | 54.1% | ×null並み |",
         "",
         "距離帯: S=1400m以下 / M=1500-1700m / L=1800m以上",
         "tier: 3=重賞・OP / 4=3勝C / 5=2勝C / 6=1勝C / 10=未勝利・新馬",
         "", "---", "", "## 配点表", "",
         "各セルのベクトルの大きさで正規化し、6群の平均TSIが30点になる共通係数を掛けた値。",
         "セル間でも Ver.99.27 とも直接比べられる。マイナスは減点方向に効く成分。", ""]
# 共通スケール: 6群の重みで「TSIが30点」になる係数を求め、全セルに同じ係数を使う
_t = [w6[g][0]/ (np.mean(np.abs(w6[g])) or 1.0) for g in w6]
SCALE = 30.0 / (np.mean(_t) or 1.0)
ks = sorted(w30, key=lambda k:(k.split('/')[0], int(k.split('t')[1])))
for grp in ["芝S","芝M","芝L","ダS","ダM","ダL"]:
    sub = [k for k in ks if k.startswith(grp+"/")]
    if not sub: continue
    lines += [f"### {grp}", "",
              "| 成分 | Ver.99.27 | " + " | ".join(f"t{k.split('t')[1]}<br>{TIERJP.get(int(k.split('t')[1]),'')}" for k in sub) + " |",
              "|---|--:|" + "--:|"*len(sub),
              "| （MINE R数） | — | " + " | ".join(str(cnt[k]) for k in sub) + " |"]
    BASE = {"TSI":"30","LTS":"30","FSI":"15","Bonus":"15","DSI":"5","NSI":"20",
            "CSI":"13","WAS":"15","TAS":"15"}
    for j,nm in enumerate(NAMES):
        row = f"| {JP[nm]} | {BASE.get(nm,'—')} | "
        vals=[]
        for k in sub:
            w=w30[k]
            # ★TSIで割る正規化はTSIの重みが0付近のセル(芝L/t3など)で破綻するため使わない。
            #   各セルのベクトルの大きさ(平均絶対値)で割り、6群の平均TSI相当が30点になる
            #   共通係数を掛ける。これでセル間もVer.99.27とも比較できる。
            sc = np.mean(np.abs(w)) or 1.0
            vals.append(f"{w[j]/sc*SCALE:.0f}")
        lines.append(row + " | ".join(vals) + " |")
    lines.append("")
open("HORIKAWA_30.md","w").write("\n".join(lines))
print("wrote HORIKAWA_30.md / hori30_w.json")
