# -*- coding: utf-8 -*-
"""git履歴の事前オッズ×確定オッズでドリフトデータセットを作る（2026-08-22夜）。

背景: オッズドリフト検証は odds_timeline の3,000R(9月中旬)待ちだったが、
過去の開催日運用でコミットされた race_*.json (761件) に当日朝〜昼のオッズが眠っている。
確定オッズ(hist_odds)・結果(hist)と突き合わせれば、ドリフト仮説を今夜検定できる。

事前凍結の仮説:
 H1: 朝→確定の比 r=final/AM が r≤0.80(強く締まった)馬は、確定オッズ帯の基準複勝ROIを上回る
 H2: r≥1.30(強く流れた)馬は基準を下回る
基準 = 同じ確定オッズ帯の全馬の複勝ROI(このデータセット内で計算=帯構成を揃えた残差)。
"""
import json, os, subprocess, sys, collections, datetime
import numpy as np

os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")
ROOT = subprocess.run(["git","rev-parse","--show-toplevel"],capture_output=True,text=True).stdout.strip()

def git_snapshots():
    """(rid, commit_ts, blob_text?) を列挙。削除コミットはskip。"""
    out = subprocess.run(["git","log","--all","--format=C %H %ct","--name-only","--",
                          "keiba/race_2026*.json"],capture_output=True,text=True,cwd=ROOT).stdout
    cur=None
    pairs=[]
    for line in out.splitlines():
        if line.startswith("C "):
            _,h,ts=line.split(); cur=(h,int(ts))
        elif line.strip().startswith("keiba/race_2026") and cur:
            pairs.append((cur[0],cur[1],line.strip()))
    return pairs

def main():
    pairs = git_snapshots()
    print(f"履歴スナップショット {len(pairs)}件")
    # rid → [(ts, odds_dict)]
    snaps = collections.defaultdict(list)
    ok=0
    for h,ts,path in pairs:
        rid = path.split("race_")[1].split(".json")[0]
        r = subprocess.run(["git","show",f"{h}:{path}"],capture_output=True,text=True,cwd=ROOT)
        if r.returncode!=0: continue
        try: d=json.loads(r.stdout)
        except Exception: continue
        od={hh["num"]: hh.get("odds") for hh in (d.get("horses") or []) if hh.get("odds")}
        if len(od)>=5:
            snaps[rid].append((ts,od)); ok+=1
    print(f"オッズ入りスナップショット {ok}件 / レース {len(snaps)}本")

    # 当日オッズtimeline(8/22)のT-180も朝オッズとして合流
    try:
        for line in open("odds_timeline/20260822.jsonl"):
            r=json.loads(line)
            if r.get("tag")=="T-180" and r.get("tan"):
                od={int(k):float(v) for k,v in r["tan"].items()}
                if len(od)>=5:
                    snaps[r["rid"]].append((0,od))   # ts=0マーカー(当日T-180)
    except FileNotFoundError:
        pass

    rows=[]   # (rid, num, am_odds, fin_odds, fuku_pay)
    used=0
    for rid, ss in snaps.items():
        ph=f"hist_odds/{rid}.json"; pr=f"hist/{rid}.json"
        if not (os.path.exists(ph) and os.path.exists(pr)): continue
        try:
            fo=json.load(open(ph)); hist=json.load(open(pr))
        except Exception: continue
        fin=fo.get("tan") or {}
        # 結果の複勝払戻
        pay=(hist.get("result") or {}).get("payout") or hist.get("payout") or {}
        pl={}
        for k,v in (pay.get("複勝") or {}).items():
            try: pl[int(k)]=float(v)
            except Exception: pass
        if not fin or not pl: continue
        # レース日とスナップ時刻: 当日のもののみ(前夜None問題は odds有無で既に除外済み)
        date=str(hist.get("date") or "")
        ss2=[]
        for ts,od in ss:
            if ts==0: ss2.append((ts,od)); continue
            d=datetime.datetime.fromtimestamp(ts+9*3600).strftime("%Y%m%d")
            if d==date.replace("-",""): ss2.append((ts,od))
        if not ss2: continue
        ts,am=sorted(ss2)[0]   # 最も早い当日スナップ
        used+=1
        for num,ao in am.items():
            fo_=fin.get(str(num)) or fin.get(num)
            if not fo_ or not ao: continue
            rows.append((rid,int(num),float(ao),float(fo_),pl.get(int(num),0.0)))
    print(f"結合できたレース {used}本 / 馬 {len(rows)}頭")
    if len(rows)<200:
        print("標本不足。ここまでで打ち切り"); return

    A=np.array([[r[2],r[3],r[4]] for r in rows])
    ratio=A[:,1]/A[:,0]
    # 確定オッズ帯の基準ROI
    BANDS=[(0,2),(2,3),(3,5),(5,8),(8,15),(15,30),(30,70),(70,10**9)]
    def bi(o):
        for i,(a,b) in enumerate(BANDS):
            if a<=o<b: return i
        return len(BANDS)-1
    bidx=np.array([bi(o) for o in A[:,1]])
    base=np.zeros(len(BANDS))
    for i in range(len(BANDS)):
        m=bidx==i
        if m.sum(): base[i]=A[m,2].sum()/m.sum()
    exp_roi=base[bidx]

    print("\n═ 朝→確定のドリフト比 r ごとの複勝成績(帯を揃えた残差) ═")
    print(f"{'r帯':>12}{'n':>7}{'複勝ROI':>9}{'帯基準':>8}{'残差':>8}")
    CUT=[(0,0.7),(0.7,0.8),(0.8,0.9),(0.9,1.0),(1.0,1.1),(1.1,1.3),(1.3,1.6),(1.6,99)]
    resid_by=[]
    for lo,hi in CUT:
        m=(ratio>=lo)&(ratio<hi)
        n=int(m.sum())
        if n<80: resid_by.append(None); continue
        act=A[m,2].sum()/n; exp=exp_roi[m].mean()
        resid_by.append(act-exp)
        print(f"{f'{lo:.1f}-{hi:.1f}':>12}{n:>7}{act:>8.1f}%{exp:>8.1f}%{act-exp:>+8.1f}")
    # H1/H2判定
    m1=ratio<=0.80; m2=ratio>=1.30
    for nm,m in (("H1(締まった r≤0.8)",m1),("H2(流れた r≥1.3)",m2)):
        n=int(m.sum())
        if n<50: print(f"{nm}: n{n}不足"); continue
        act=A[m,2].sum()/n; exp=exp_roi[m].mean()
        se=np.std(A[m,2])/np.sqrt(n)
        print(f"{nm}: n={n} 実ROI{act:.1f}% 基準{exp:.1f}% 残差{act-exp:+.1f}pt (SE±{se:.1f})")
    json.dump({"n_horses":len(rows),"races":used},open("drift_ds_meta.json","w"))
    np.save("drift_ds.npy", np.column_stack([A, ratio, bidx]))
    print("\nsaved drift_ds.npy")

if __name__=="__main__":
    main()
