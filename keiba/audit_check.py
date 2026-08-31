# -*- coding: utf-8 -*-
"""本日の分析の自己監査①（2026-08-22・指示「今回の分析おかしいとこ無いか確認しといて」）。

疑い1: make52.py の書き出しが評価時と違うモデルになっていないか。
  評価(split60.py)は レースごとに 0.5*場セル重み + 0.5*30分割重み(そのレースのクラス依存)。
  書き出しは 0.5*場セル重み + 0.5*「セル内の30分割重みの平均」= クラスの層が潰れている疑い。
  → 両方を同じデータで評価して差を測る。

疑い2: course_on30.py のnullは混合していない素のnullだった。
  実データ側は「30分割と50%混合」なのにnullは混合なし。混合自体が良いモデル(b30)へ
  寄せる効果を持つので、混合あり vs 混合なし の比較は実データに不当に有利。
  → split60のnull(混合あり)が正しい基準。真の上乗せ幅を計算し直す。

疑い3: 標本誤差。CONF=676Rでの3着内率のSEは sqrt(0.55*0.45/676)≈1.9pt。
  null(55.9)に対する勝者(57.0)の差+1.1ptは1SE未満。数字で明示する。
"""
import json, collections, sys, os, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V, v99w2_fit as V2

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

def ev(races, wfn):
    n=len(races); t3=0; cost=ret=0
    for r in races:
        s=r["Z16"]@wfn(r)
        o=sorted(range(len(s)),key=lambda i:(-s[i],-r["wavg"][i],r["nums"][i]))
        t3+=int(o[0] in set(r["top3"]))
        pl={int(k):float(v) for k,v in ((r["payout"] or {}).get("複勝") or {}).items()}
        for i in o[:2]:
            cost+=100; ret+=pl.get(r["nums"][i],0.0)
    return t3/n*100, ret/cost*100

races=V.load_races(); V2.attach_corner(races)
K=races[0]["Z16"].shape[1]
seg=lambda lo,hi:[r for r in races if lo<=r["month"]<=hi]
MINE,VAL,CONF=seg('000000','202602'),seg('202603','202605'),seg('202606','202608')
X,M,W=V2.make_tensor(MINE,key="Z16")
w_all=V2.fit(X,M,W,1.0,w0=np.zeros(K),wstart=np.zeros(K))
w6=fit_by(MINE,sd,0.2,lambda r:w_all,1); b6=lambda r:w6.get(sd(r),w_all)
w30=fit_by(MINE,k30,0.3,b6,40);          b30=lambda r:w30.get(k30(r),b6(r))
w52=fit_by(MINE,k52,0.3,b30,40)

# 真の勝者モデル(評価時と同じ): レースごとにクラス依存のb30と混合
true_f=lambda r:(lambda c,b:(b if c is None else 0.5*c+0.5*b))(w52.get(k52(r)),b30(r))
# 書き出したモデル(クラス層をセル平均で潰した版)
flat=json.load(open('hori52_w.json'))
fw={k:np.array(v) for k,v in flat["w"].items()}
flat_f=lambda r: fw.get(k52(r), None) if fw.get(k52(r)) is not None else b30(r)
def flat_f(r):
    c=fw.get(k52(r))
    return c if c is not None else b30(r)

print("── 疑い1: 書き出しモデル(クラス層が潰れた版) vs 評価時の真のモデル ──")
for nm,S in (("VAL",VAL),("CONF",CONF)):
    t_t3,t_roi=ev(S,true_f); f_t3,f_roi=ev(S,flat_f)
    b_t3,b_roi=ev(S,b30)
    print(f"  {nm}: 真のモデル {t_t3:.1f}%/{t_roi:.1f}%  書き出し版 {f_t3:.1f}%/{f_roi:.1f}%  "
          f"(30分割のみ {b_t3:.1f}%/{b_roi:.1f}%)")

print("\n── 疑い3: 標本誤差 ──")
for nm,S in (("VAL",VAL),("CONF",CONF)):
    n=len(S); se=math.sqrt(0.55*0.45/n)*100
    print(f"  {nm} n={n} → 3着内率のSE ≈ ±{se:.1f}pt")
print("  勝者(VAL56.5/CONF57.0) vs 混合null(55.8/55.9)の差 = +0.7/+1.1pt → どちらも1SE未満")
