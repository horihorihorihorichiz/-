# -*- coding: utf-8 -*-
"""過去15枚のデイボードから朝オッズを掘り、確定オッズとのドリフトで仮説検定（2026-08-22夜）。

データ: git履歴の board_YYYYMMDD.md 15枚(7/21〜8/22)。
 ・メイン表: 全レースの軸馬(モデル1位)の朝オッズ
 ・【A】等の個別表: そのレース全頭の朝オッズ
確定オッズ=hist_odds / 結果払戻=hist。

事前凍結の仮説(extract_driftと同じ):
 H1: 朝→確定の比 r≤0.80(強く締まった)馬は、確定オッズ帯の基準複勝ROIを上回る
 H2: r≥1.30(強く流れた)馬は基準を下回る
基準 = 全13,194Rから作る確定オッズ帯別の複勝ROI(帯構成を揃えた残差)。
"""
import json, os, re, subprocess, collections
import numpy as np

ROOT = subprocess.run(["git","rev-parse","--show-toplevel"],capture_output=True,text=True).stdout.strip()
VCODE = {"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05",
         "中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def load_board(name):
    r = subprocess.run(["git","log","--all","--format=%H","--","keiba/"+name],
                       capture_output=True,text=True,cwd=ROOT)
    for h in r.stdout.split():
        c = subprocess.run(["git","show",f"{h}:keiba/{name}"],capture_output=True,text=True,cwd=ROOT)
        if c.returncode==0 and len(c.stdout)>1000:
            return c.stdout
    return None

def rid_index():
    """(date8, venue, R番号) → rid。台帳から。"""
    idx={}
    import sys; sys.path.insert(0,'.')
    meta = json.load(open("mine200_meta.json")) if os.path.exists("mine200_meta.json") else {}
    for line in open("bsd16_races.jsonl"):
        r=json.loads(line)
        rid=r["rid"]
        v=meta.get(rid,{}).get("venue")
        if not v: continue
        # 日付はhistから
        idx[rid]=v
    # date別引き: histを開くのは重いのでrid→dateはhistファイルの中身が要る…
    # 代替: hist/{rid}.json の date を必要なridだけ後で開く
    return idx

def main():
    # ボードを収集
    boards={}
    for d in ["20260721","20260722","20260723","20260724","20260725","20260726",
              "20260801","20260802","20260808","20260809","20260813","20260814",
              "20260815","20260816","20260822"]:
        t=load_board(f"board_{d}.md")
        if t: boards[d]=t
    print(f"ボード {len(boards)}枚")

    # メイン表の軸馬 + 個別表の全頭
    main_re = re.compile(r"^\|\s*(\S{2})\s*\|\s*(\d+)\s*\|[^|]*\|[^|]*\|[^|]*\|\s*(\d+)\s+\S+\s*\|\s*([\d.]+)倍")
    sub_head = re.compile(r"^##.*?【[SAB]+】(\S{2})(\d+)R")
    sub_row = re.compile(r"^\|\s*(\d+)\s*\|[^|]+\|[^|]*\|[^|]+\|[^|]+\|[^|]+\|\s*([\d.]+)\(")
    obs=[]   # (date, venue, R, num, am_odds, is_axis)
    for d,txt in boards.items():
        cur=None
        for line in txt.splitlines():
            m=main_re.match(line)
            if m:
                v,rn,num,od=m.group(1),int(m.group(2)),int(m.group(3)),float(m.group(4))
                if v in VCODE: obs.append((d,v,rn,num,od,True))
                continue
            m=sub_head.match(line)
            if m:
                cur=(m.group(1),int(m.group(2))) if m.group(1) in VCODE else None
                continue
            if line.startswith("## "): cur=None
            if cur:
                m=sub_row.match(line)
                if m:
                    obs.append((d,cur[0],cur[1],int(m.group(1)),float(m.group(2)),False))
    print(f"朝オッズ観測 {len(obs)}頭 (軸{sum(1 for o in obs if o[5])})")

    # (date,venue,R)→rid: histをスキャン(対象日だけ)
    dates=set(o[0] for o in obs)
    ridmap={}
    import glob
    for p in glob.glob("hist/*.json"):
        rid=os.path.basename(p)[:-5]
        try: h=json.load(open(p))
        except Exception: continue
        dt=str(h.get("date","")).replace("-","")
        if dt in dates:
            v=(h.get("race") or {}).get("venue") or h.get("venue")
            rn=int(rid[10:12])
            ridmap[(dt,v,rn)]=rid
    print(f"rid解決 {len(ridmap)}レース")

    # 基準: 全台帳の確定オッズ帯別複勝ROI
    BANDS=[(0,2),(2,3),(3,5),(5,8),(8,15),(15,30),(30,70),(70,10**9)]
    def bi(o):
        for i,(a,b) in enumerate(BANDS):
            if a<=o<b: return i
        return len(BANDS)-1
    acc=np.zeros((len(BANDS),2))
    for line in open("bsd16_races.jsonl"):
        r=json.loads(line)
        pl={int(k):float(v) for k,v in ((r.get("payout") or {}).get("複勝") or {}).items()}
        for num,o in (r.get("odds") or {}).items():
            if not o: continue
            k=bi(float(o)); acc[k]+=[1, pl.get(int(num),0.0)]
    base=np.where(acc[:,0]>0, acc[:,1]/np.maximum(acc[:,0],1), 0)

    rows=[]
    hit_join=0
    for d,v,rn,num,am,ax in obs:
        rid=ridmap.get((d,v,rn))
        if not rid: continue
        ph=f"hist_odds/{rid}.json"; pr=f"hist/{rid}.json"
        if not (os.path.exists(ph) and os.path.exists(pr)): continue
        try:
            fo=json.load(open(ph)); h=json.load(open(pr))
        except Exception: continue
        fin=(fo.get("tan") or {}).get(str(num))
        if not fin: continue
        pay=(h.get("result") or {}).get("payout") or h.get("payout") or {}
        pl={}
        for k,val in (pay.get("複勝") or {}).items():
            try: pl[int(k)]=float(val)
            except Exception: pass
        hit_join+=1
        rows.append((float(am), float(fin), pl.get(num,0.0), ax))
    print(f"確定オッズ・結果と結合 {hit_join}頭")
    if hit_join<150:
        print("標本不足"); return

    A=np.array([[r[0],r[1],r[2]] for r in rows]); isax=np.array([r[3] for r in rows])
    ratio=A[:,1]/A[:,0]
    bidx=np.array([bi(o) for o in A[:,1]])
    exp=base[bidx]

    print("\n═ 朝→確定ドリフト比 r ごとの複勝成績(帯基準との残差) ═")
    print(f"{'r帯':>10}{'n':>6}{'実ROI':>8}{'帯基準':>8}{'残差':>8}")
    for lo,hi in ((0,0.7),(0.7,0.8),(0.8,0.9),(0.9,1.0),(1.0,1.1),(1.1,1.3),(1.3,1.6),(1.6,99)):
        m=(ratio>=lo)&(ratio<hi); n=int(m.sum())
        if n<30: continue
        act=A[m,2].sum()/n; e=exp[m].mean()
        print(f"{f'{lo:.1f}-{hi:.1f}':>10}{n:>6}{act:>7.1f}%{e:>7.1f}%{act-e:>+8.1f}")
    for nm,m in (("H1 r≤0.8(締)",ratio<=0.8),("H2 r≥1.3(流)",ratio>=1.3)):
        n=int(m.sum())
        if n<30: print(f"{nm}: n{n}不足"); continue
        act=A[m,2].sum()/n; e=exp[m].mean(); se=np.std(A[m,2])/np.sqrt(n)
        print(f"{nm}: n={n} 実ROI{act:.1f}% 基準{e:.1f}% 残差{act-e:+.1f}pt (SE±{se:.1f})")
    # 軸馬(モデル1位)に限定した版=実運用に直結
    m=isax
    print(f"\n═ 軸馬(モデル1位)のみ n={int(m.sum())} ═")
    for lo,hi in ((0,0.85),(0.85,1.0),(1.0,1.15),(1.15,99)):
        mm=m&(ratio>=lo)&(ratio<hi); n=int(mm.sum())
        if n<25: continue
        act=A[mm,2].sum()/n; e=exp[mm].mean()
        print(f"  r {lo:.2f}-{hi:.2f}: n{n} 実ROI{act:.1f}% 基準{e:.1f}% 残差{act-e:+.1f}")
    np.save("board_drift_ds.npy", np.column_stack([A, ratio, isax]))
    print("\nsaved board_drift_ds.npy")

if __name__=="__main__":
    main()
