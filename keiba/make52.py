# -*- coding: utf-8 -*-
"""最終構成の配点表を書き出す（2026-08-22）。
階層: 全体1本 → 芝ダ×距離帯(6) → ×クラス(30) → ×場(52) を50%混合。
split60.py で VAL56.5/CONF57.0・複2ROI VAL85.3/CONF84.0 と最良になった構成。"""
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
BASE = {"TSI":"30","LTS":"30","FSI":"15","Bonus":"15","DSI":"5","NSI":"20",
        "CSI":"13","WAS":"15","TAS":"15"}
def sd(r):  return f"{r['surface']}{r['dist_cat']}"
def k30(r): return f"{r['surface']}{r['dist_cat']}/t{r['tier']}"
def k52(r): return f"{r.get('venue')}{r['surface']}{r['dist_cat']}"

def fit_by(races, kf, l2, base_of, min_n):
    out={}; by=collections.defaultdict(list)
    for r in races: by[kf(r)].append(r)
    for k,sub in by.items():
        if len(sub)<min_n: continue
        b=base_of(sub[0]); X,M,W=V2.make_tensor(sub,key="Z16")
        out[k]=V2.fit(X,M,W,l2,w0=b,wstart=b)
    return out

races=V.load_races(); V2.attach_corner(races)
K=races[0]["Z16"].shape[1]
MINE=[r for r in races if r["month"]<='202602']
X,M,W=V2.make_tensor(MINE,key="Z16")
w_all=V2.fit(X,M,W,1.0,w0=np.zeros(K),wstart=np.zeros(K))
w6=fit_by(MINE,sd,0.2,lambda r:w_all,1); b6=lambda r:w6.get(sd(r),w_all)
w30=fit_by(MINE,k30,0.3,b6,40);          b30=lambda r:w30.get(k30(r),b6(r))
w52=fit_by(MINE,k52,0.3,b30,40)
cnt=collections.Counter(k52(r) for r in MINE)
# 最終重み = 0.5*52セル + 0.5*30セル。30セル側は各52セルの代表レースで決まるので
# セルごとに「そのセルに属するMINEレースの30セル重みの平均」を使う
# ★2026-08-22 修正: 旧実装はMINEの全キーを回していたため、40R未満で w52 から
#   除外されたセル(福島ダL 7R / 札幌ダL 8R / 函館ダL 8R)まで最終辞書に入れてしまい、
#   独立した重みを持つかのように見えていた。実体は30分割の重みそのままで、
#   場別の情報は何も足されていない。誤解を招くので **w52 にあるキーだけ** を採る。
#   除外されたセルはライブ側で自動的に30分割へフォールバックする(挙動は同じ)。
by=collections.defaultdict(list)
for r in MINE: by[k52(r)].append(r)
skipped={k:len(sub) for k,sub in by.items() if k not in w52}
if skipped:
    print("40R未満で除外(30分割へフォールバック):",
          ", ".join(f"{k} {v}R" for k,v in sorted(skipped.items(), key=lambda x:x[1])))
# ★2026-08-22 監査で確定したバグの修正:
#   旧実装はクラス層をセル平均で潰した1本の重み"w"を書き出していたが、それは
#   評価時のモデルと別物で、実測 VAL55.8/CONF55.9(勝者は56.5/57.0)＝上乗せがほぼ消える。
#   スコアは実行時に2層を合成する: 0.5*w52[場+芝ダ+距離帯] + 0.5*w30[芝ダ+距離帯+クラス]
#   (w52が無いセルは w30 のみ。w30も無ければ w6 → wg)
json.dump({"axis":"venue+surface+dist_cat(2層合成)","mix":0.5,"names":NAMES,
           "combine":"score_w = 0.5*w52[venue+sd] + 0.5*w30[sd+tier]; "
                     "w52欠落セルはw30のみ; w30欠落はw6; それも無ければwg",
           "wg":[round(float(x),8) for x in w_all],
           "w6":{k:[round(float(x),8) for x in v] for k,v in w6.items()},
           "w30":{k:[round(float(x),8) for x in v] for k,v in w30.items()},
           "w52":{k:[round(float(x),8) for x in v] for k,v in w52.items()},
           "n":{k:int(cnt[k]) for k in w52}},
          open("hori52_w.json","w"), ensure_ascii=False, indent=1)
_t=[w6[g][0]/(np.mean(np.abs(w6[g])) or 1.0) for g in w6]
SCALE=30.0/(np.mean(_t) or 1.0)
L=["# 堀川システム 52分割 配点表（2026-08-22 最終構成）","",
   "階層: 全体1本 → 芝ダ×距離帯(6) → ×クラス(30) → **×場(52)を50%混合**","",
   "| 構成 | セル | VALIDATE 3着内 | CONFIRM | VAL複2ROI | CONF複2ROI |","|---|--:|--:|--:|--:|--:|",
   "| 6群(現行) | 6 | 55.0% | 54.4% | 83.3% | 81.0% |",
   "| +クラス | 30 | 55.7% | 55.6% | 83.6% | 82.1% |",
   "| **+場(52)混合50%** | 52 | **56.5%** | **57.0%** | **85.3%** | **84.0%** |",
   "| null(60セル乱数) | 60 | 55.8% | 55.9% | 83.0% | 80.5% |","",
   "現行比 3着内 +2.6pt / 複勝2点ROI +3.0pt。未知2期間とも改善。","",
   "距離帯: S=1400m以下 / M=1500-1700m / L=1800m以上","",
   "**欠落セルについて**: 10場×6区分=60のうち52セル。欠けているのはコース設定上",
   "そのレース自体が存在しないため（バグではない）。",
   "・函館/福島/小倉の芝M … 芝1500-1700mのコースが無い（芝は1200/1800/2000/2600のみ）",
   "・新潟/中山/中京/京都/阪神のダM … ダートは1400→1700/1800と飛ぶため1500-1700が無い",
   "加えて40R未満のセル（福島ダL 7R・札幌ダL 8R・函館ダL 8R）は独立した配点を持たず、",
   "30分割（芝ダ×距離帯×クラス）の配点をそのまま使う。",""
   "★この表は2層のうちの【場の層】(スコアの50%)。もう50%は HORIKAWA_30.md の",
   "【クラス層】(芝ダ×距離帯×クラス)で、レースごとに 場の層50% + クラス層50% を合成して使う。",
   "この表単独では勝者モデルにならない(監査で実測: 層を潰すとVAL55.8/CONF55.9に落ちる)。","",
   "各セルのベクトルの大きさで正規化し、6群の平均TSIが30点になる共通係数を掛けた値。","","---",""]
ven=["札幌","函館","福島","新潟","東京","中山","中京","京都","阪神","小倉"]
ks=sorted(w52,key=lambda k:(ven.index(k[:2]) if k[:2] in ven else 99,k))
for v in ven:
    sub=[k for k in ks if k.startswith(v)]
    if not sub: continue
    L+= [f"## {v}","", "| 成分 | Ver.99.27 | "+" | ".join(k[2:] for k in sub)+" |",
         "|---|--:|"+"--:|"*len(sub),
         "| （MINE R数） | — | "+" | ".join(str(cnt[k]) for k in sub)+" |"]
    for j,nm in enumerate(NAMES):
        vals=[]
        for k in sub:
            w=w52[k]; sc=np.mean(np.abs(w)) or 1.0
            vals.append(f"{w[j]/sc*SCALE:.0f}")
        L.append(f"| {JP[nm]} | {BASE.get(nm,'—')} | "+" | ".join(vals)+" |")
    L.append("")
open("HORIKAWA_52.md","w").write("\n".join(L))
print(f"セル数 {len(w52)} / wrote HORIKAWA_52.md, hori52_w.json")
