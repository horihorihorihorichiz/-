#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
競馬予想テンプレート Ver.99.27 計算エンジン
- 算術・表引き・順位付け・exp・正規化・Case判定を厳密に実行する。
- 入力(レース+各馬の生データ)を渡すと STEP0〜STEP10 を計算して台帳を返す。
- データ抽出と判断(脚質の新聞表記/Tier分類/VG分類/CSI/TAS off走/HCS免除)は
  人間(またはClaude)が構造化して渡す。それ以外の数値処理は全てここで行う。

使い方:
    python calc.py race.json
  または
    from calc import run, print_report
    res = run(race_dict); print_report(res)
"""
import math, json, sys

# ───────────────────────── 基礎テーブル ─────────────────────────
KIJUN = {
    "芝": [(1000,33.5),(1200,34.0),(1400,34.2),(1600,34.3),(1800,34.5),
           (2000,34.7),(2200,34.9),(2400,35.0),(2600,35.1),(3000,35.3),
           (3200,35.5),(3600,35.8)],
    "ダ": [(1000,36.0),(1200,36.5),(1400,36.8),(1600,37.0),(1800,37.5),
           (2000,37.8),(2200,38.0),(2400,38.2),(2600,38.5)],
}
C_BY_VG = {1:0.6, 2:0.1, 3:0.0, 4:-0.2, 5:-0.5}
LTS_HAITEN = {1:30, 2:25, 3:20, 4:15, 5:15}
BOOST_MULT = {0:1.0, 1:1.2, 2:1.1}
# 展開乗数 [スロー, ミドルs, ミドル, ミドルハイ, ハイ]  (stage 0..4)
KANKAI = {
    "逃":    [1.10,1.06,1.00,0.94,0.90],
    "先":    [1.04,1.02,1.00,0.98,0.96],
    "先差":  [1.04,1.02,1.05,0.99,1.00],   # 先差🔄
    "差先":  [1.00,0.99,1.05,1.02,1.04],   # 差先🔄
    "差":    [0.93,0.97,1.00,1.03,1.07],
    "追":    [0.90,0.96,1.00,1.04,1.10],
}
STAGE_NAME = ["スロー","ミドルs","ミドル","ミドルハイ","ハイ"]
# FSI 基本マッチ [逃,先,先差,差先,差,追]
FSI_MATRIX = {
    "A": {"逃":15,"先":15,"先差":10,"差先":10,"差":5, "追":0},   # 1-2枠
    "B": {"逃":10,"先":15,"先差":15,"差先":10,"差":10,"追":5},   # 3-4枠
    "C": {"逃":5, "先":10,"先差":15,"差先":15,"差":10,"追":10},  # 5-6枠
    "D": {"逃":0, "先":5, "先差":10,"差先":10,"差":15,"追":15},  # 7-8枠
}
# 枠番割り当て表: 頭数 -> 各枠(1..8)の(下限,上限)馬番
WAKU_TABLE = {
 8:[(1,1),(2,2),(3,3),(4,4),(5,5),(6,6),(7,7),(8,8)],
 9:[(1,1),(2,2),(3,3),(4,4),(5,5),(6,6),(7,7),(8,9)],
 10:[(1,1),(2,2),(3,3),(4,4),(5,5),(6,6),(7,8),(9,10)],
 11:[(1,1),(2,2),(3,3),(4,4),(5,5),(6,7),(8,9),(10,11)],
 12:[(1,1),(2,2),(3,3),(4,4),(5,6),(7,8),(9,10),(11,12)],
 13:[(1,1),(2,2),(3,3),(4,5),(6,7),(8,9),(10,11),(12,13)],
 14:[(1,1),(2,2),(3,4),(5,6),(7,8),(9,10),(11,12),(13,14)],
 15:[(1,1),(2,3),(4,5),(6,7),(8,9),(10,11),(12,13),(14,15)],
 16:[(1,2),(3,4),(5,6),(7,8),(9,10),(11,12),(13,14),(15,16)],
 17:[(1,2),(3,4),(5,6),(7,8),(9,10),(11,12),(13,15),(16,17)],
 18:[(1,2),(3,4),(5,6),(7,8),(9,10),(11,12),(13,15),(16,18)],
}
def waku_of(field, umaban):
    if field in WAKU_TABLE:
        for w,(lo,hi) in enumerate(WAKU_TABLE[field], start=1):
            if lo <= umaban <= hi: return w
        return 8
    # 表に無い頭数(<8 等)は 枠=馬番(最大8)
    return min(umaban, 8)
def band_of(field, umaban):
    w = waku_of(field, umaban)
    return "A" if w<=2 else "B" if w<=4 else "C" if w<=6 else "D"

def kijun(surface, dist):
    tbl = KIJUN[surface]
    if dist <= tbl[0][0]: return tbl[0][1]
    if dist >= tbl[-1][0]: return tbl[-1][1]
    for i in range(len(tbl)-1):
        d0,v0 = tbl[i]; d1,v1 = tbl[i+1]
        if d0 <= dist <= d1:
            return v0 + (v1-v0)*(dist-d0)/(d1-d0)
    return tbl[-1][1]

def p_hosei(dist_cat, pace):
    if pace is None: return 0.0
    t = {"S":{"S":0.3,"M":0,"H":-0.3},
         "M":{"S":0.5,"M":0,"H":-0.5},
         "L":{"S":0.8,"M":0,"H":-0.8}}[dist_cat]
    return t[pace]

def b_hosei(idx):
    if idx is None: return 0.0
    if idx <= -25: return 0.5
    if idx <= -20: return 0.3
    if idx <= -15: return 0.0
    if idx <= -10: return -0.3
    return -0.5

def tsi_coeff(today_d, past_d):
    if past_d >= today_d: return 1.00
    gap = today_d - past_d
    if gap <= 200: return 0.95
    if gap <= 400: return 0.90
    if gap <= 600: return 0.88
    return 0.80

def comp_rank(values, reverse):
    """競争順位(タイは同順位)。reverse=True で大きいほど良い。"""
    order = sorted(range(len(values)), key=lambda i: values[i], reverse=reverse)
    ranks = [0]*len(values)
    i = 0
    while i < len(order):
        j = i
        while j+1 < len(order) and values[order[j+1]] == values[order[i]]:
            j += 1
        for k in range(i, j+1):
            ranks[order[k]] = i+1   # 同値は最小順位
        i = j+1
    return ranks

# ───────────────────────── NSI Grade ─────────────────────────
GRADE_ORDER = ["S+","S","A+","A","B","C","D"]
GRADE_RATE  = {"S+":1.0,"S":0.9,"A+":0.8,"A":0.7,"B":0.5,"C":0.3,"D":0.1}
DOWN2 = {"S+":"A+","S":"A","A+":"B","A":"C","B":"D","C":"D","D":None}
def base_grade(T, P, fin):
    if P < T and fin == 1: return "S+"
    if (P == T and fin == 1) or (P < T and fin in (2,3)): return "S"
    if P == T and fin == 2: return "A+"
    if (P == T and fin == 3) or (P == T+1 and fin == 1): return "A"
    if (P == T+1 and fin in (2,3)) or (P == T+2 and fin == 1): return "B"
    if P == T+2 and fin <= 3: return "C"
    return "D"
def nsi_grade(T, races):
    best = 0.0; lbl = "D"
    for r in races:
        if r.get("tier") is None: continue
        days = r.get("days", 0)
        if days > 730:   # 2年超は対象外
            continue
        g = base_grade(T, r["tier"], r["finish"])
        if days > 365:   # 1-2年は2段階下げ
            g = DOWN2[g]
            if g is None: continue
        if GRADE_RATE[g] > best:
            best = GRADE_RATE[g]; lbl = g
    return best, lbl

# ───────────────────────── 各馬計算 ─────────────────────────
def lts_best(horse, race):
    surf = race["surface"]; td = race["distance"]; dc = race["dist_cat"]
    same = [r for r in horse["races"] if r["surface"] == surf]
    used = same[:5]
    vals = []
    for r in used:
        if r.get("agari") is None: continue
        corr = (r["agari"] + p_hosei(dc, r.get("pace"))
                + b_hosei(r.get("baba_idx"))
                + C_BY_VG[r["vg"]]
                + (kijun(surf, td) - kijun(surf, r["dist"])))
        vals.append(round(corr, 3))
    return min(vals) if vals else None

def tsi_best(horse, race):
    td = race["distance"]
    cand = []
    for r in horse["races"]:
        if r.get("tsi") is None: continue
        cand.append(r["tsi"] * tsi_coeff(td, r["dist"]))
    return max(cand) if cand else None

def corner_stats(horse):
    norms = []
    for r in horse["races"]:
        if r.get("corner4") is not None and r.get("field"):
            norms.append(r["corner4"]/r["field"])
    mean = sum(norms)/len(norms) if norms else 1.0
    cnt_le050 = sum(1 for x in norms if x <= 0.50)
    cnt_le022 = sum(1 for x in norms if x <= 0.22)
    return mean, cnt_le050, cnt_le022

def fsi(horse, race):
    band = band_of(race["field"], horse["umaban"])
    style = horse["style"]
    base = FSI_MATRIX[band][style]
    add = 0
    if base in (0,5,10):
        hits = 0
        for r in horse["races"][:9]:
            if band_of(r["field"], r["umaban"]) == band and r["finish"] <= 3:
                hits += 1
        if hits >= 2: add = 10
        elif hits == 1: add = 5
    return min(base+add, 15), band

def bonus(horse):
    tfb = ssc = 0
    for r in horse["races"][:5]:
        if r["finish"] <= 3 and r["field"] >= 12 and r.get("corner4") is not None:
            if r["vg"] in (1,2) and r["corner4"] <= 3:
                tfb += 1
            elif r["vg"] in (3,4,5) and r["corner4"] > r["field"]*0.40:
                ssc += 1
    def pts(n): return 0 if n==0 else (8 if n==1 else 10)
    return min(pts(tfb)+pts(ssc), 15)

def dsi(horse, race):
    td = race["distance"]; haiten = race["dsi_haiten"]
    rs = horse["races"]
    # A: 近3走に ±200m かつ 掲示板(<=5)
    for r in rs[:3]:
        if abs(r["dist"]-td) <= 200 and r["finish"] <= 5:
            return 1.0*haiten, "A"
    # B: 1年以内 ±200m + 掲示板
    for r in rs:
        if r.get("days",0) <= 365 and abs(r["dist"]-td) <= 200 and r["finish"] <= 5:
            return 0.7*haiten, "B"
    # C: 1年以内 ±400m + 掲示板
    for r in rs:
        if r.get("days",0) <= 365 and abs(r["dist"]-td) <= 400 and r["finish"] <= 5:
            return 0.4*haiten, "C"
    return 0.0, "D"

def was_pool(kinryos):
    d = max(kinryos)-min(kinryos)
    if d < 2: return 0
    if d < 4: return 5
    if d == 4: return 10
    if d < 6: return 10
    if d == 6: return 15
    return 15
def was_each(kinryo, mx, pool):
    if pool == 0: return 0
    if kinryo == (mx - pool if False else None): pass
    D = mx - kinryo
    if abs(kinryo - (mx - 0)) < 1e-9 and False: pass
    # 最軽量判定は呼び出し側で
    if D <= 2: return 0
    return min(D, pool)

def tas(horse, race):
    baba = race["baba"]
    if baba == "良": return 0
    offs = horse.get("offtrack_finishes", None)  # 1年以内の稍/重/不での着順list
    if offs is None: offs = []
    if offs:
        best = min(offs)
        grade = "S" if best <= 2 else ("A" if best <= 4 else None)
    else:
        grade = "A"  # 該当レース無し → A
    if grade is None: return 0
    if baba == "稍":
        pt = 10 if grade=="S" else 5
        if race["surface"]=="ダ" and horse["style"] in ("逃","先","先差","差先"):
            pt += 3 if grade=="S" else 2
    else:  # 重/不
        pt = 15 if grade=="S" else 8
    return min(pt, 15)

def hcs(horse):
    w = horse.get("weight"); ch = horse.get("weight_change")
    if w is None: return 0
    wpt = 0 if w < 460 else (1 if w < 500 else 2)
    a = abs(ch) if ch is not None else 0
    cpt = 0 if a <= 5 else (-5 if a <= 9 else (-8 if a <= 14 else -10))
    ex = horse.get("hcs_exempt","none")
    if ex == "full": cpt = 0
    elif ex == "half": cpt = cpt/2.0
    return max(min(wpt+cpt, 5), -10)

def nrja(days):
    if days <= 14: return -3
    if days <= 21: return -1
    if days <= 56: return 0
    if days <= 84: return -1
    if days <= 140: return -3
    if days <= 175: return -5
    if days <= 240: return -7
    return -10

# ───────────────────────── STEP1 脚質確定 ─────────────────────────
def finalize_styles(race):
    N = race["field"]; horses = race["horses"]
    # まず LTS_best と順位
    lb = [lts_best(h, race) for h in horses]
    big = max([x for x in lb if x is not None]) + 99
    lb_f = [x if x is not None else big for x in lb]
    lts_rank = comp_rank(lb_f, reverse=False)
    for i,h in enumerate(horses):
        h["_lts_best"] = lb[i]; h["_lts_rank"] = lts_rank[i]
        mean, c50, c22 = corner_stats(h)
        h["_c4mean"] = mean; h["_c4_le050"] = c50; h["_hidden"] = (c22 >= 2)
        paper = h["paper_style"]; st = paper
        if paper in ("先","先差"):
            if h.get("boost",0) > 0 or lts_rank[i] <= N*0.30:
                st = "先差"
            else:
                st = "先"
        elif paper in ("差","差先"):
            if mean <= 0.45 and c50 >= 3:
                st = "差先"
            else:
                st = "差"
        elif paper == "逃": st = "逃"
        elif paper == "追": st = "追"
        h["style"] = st
    return

# ───────────────────────── STEP2 展開 ─────────────────────────
def pace_stage(race):
    N = race["field"]; hs = race["horses"]
    n_nige = sum(1 for h in hs if h["style"]=="逃")
    n_sen = (sum(1 for h in hs if h["style"]=="先")
             + sum(1 for h in hs if h["style"]=="先差")
             + 0.5*sum(1 for h in hs if h["style"]=="差先"))
    n_hidden = sum(1 for h in hs if h.get("_hidden"))
    log = [f"N_逃={n_nige} N_先={n_sen} 隠れ逃={n_hidden} (N={N})"]
    if n_nige + n_sen <= N*0.25: st = 0
    elif n_nige >= 3 or n_sen >= N*0.55: st = 4
    elif n_nige >= 2 and n_sen >= N*0.45: st = 3
    elif n_nige <= 1 and n_sen <= N*0.30: st = 1
    else: st = 2
    log.append(f"基本段階={st}({STAGE_NAME[st]})")
    # 単騎逃げ
    if n_nige == 1 and n_sen <= N*0.25 and n_hidden < 2:
        st -= 1; log.append("単騎逃げON -1")
    # 枠順系(芝12頭以上のみ)
    if race["surface"]=="芝" and N >= 12:
        adj = 0
        nige_wakus = [waku_of(N,h["umaban"]) for h in hs if h["style"]=="逃"]
        front_inner = any(band_of(N,h["umaban"]) in ("A","B")
                          for h in hs if h["style"] in ("先","先差","差先") or h.get("_hidden"))
        if nige_wakus and all(w>=5 for w in nige_wakus) and (n_nige+n_hidden)>=3: adj -= 1
        if nige_wakus and all(w>=5 for w in nige_wakus) and front_inner: adj -= 1
        if n_nige>=2 and all(w<=4 for w in nige_wakus): adj += 1
        adj = max(-2, min(1, adj))
        if adj: log.append(f"枠順系 {adj:+d}")
        st += adj
    st = max(0, min(4, st))
    # 馬場補正(最終): 稍=ミドルハイ(set3) / 重・不良=ミドル上限(min2)
    baba = race["baba"]
    if baba == "稍": st = 3; log.append("稍重→ミドルハイ(set3)")
    elif baba in ("重","不"): st = min(st, 2); log.append("重/不良→ミドル上限(min2)")
    st = max(0, min(4, st))
    log.append(f"確定展開={st}({STAGE_NAME[st]})")
    return st, log

# ───────────────────────── メイン ─────────────────────────
def run(race):
    hs = race["horses"]; N = race["field"]
    for h in hs:
        h["umaban"] = h.get("umaban", h["num"])
    finalize_styles(race)
    stage, pace_log = pace_stage(race)

    # TSI
    tb = [tsi_best(h, race) for h in hs]
    have = [x for x in tb if x is not None]
    med = (sorted(have)[len(have)//2]-5) if have else 0
    tb_f = [x if x is not None else med for x in tb]
    tsi_rank = comp_rank(tb_f, reverse=True)
    tsi_score = [round(30*(1-0.6*(r-1)/(N-1)),2) for r in tsi_rank]

    # LTS score(+中央繰上+ブースト)
    lts_rank = [h["_lts_rank"] for h in hs]
    haiten = LTS_HAITEN[race["today_vg"]]
    base_score = [haiten*(1-0.6*(r-1)/(N-1)) for r in lts_rank]
    import math as _m
    median_rank = _m.ceil(N/2)
    median_score = haiten*(1-0.6*(median_rank-1)/(N-1))
    lts_final = []
    for i,h in enumerate(hs):
        s = base_score[i]
        if h.get("boost",0) > 0 and lts_rank[i] > median_rank:
            s = max(s, median_score)         # 中央順位繰上(ブースト馬)
        s = s * BOOST_MULT[h.get("boost",0)]  # ブースト乗算
        lts_final.append(round(s,2))

    kinryos = [h["kinryo"] for h in hs]
    mx = max(kinryos); pool = was_pool(kinryos)

    rows = []
    for i,h in enumerate(hs):
        f_fsi, band = fsi(h, race)
        f_bonus = bonus(h)
        f_dsi, dsi_g = dsi(h, race)
        f_nsi_rate, nsi_g = nsi_grade(race["today_tier"], h["races"])
        f_nsi = round(f_nsi_rate*race["nsi_haiten"],2)
        # WAS
        if abs(h["kinryo"]-min(kinryos))<1e-9: f_was = pool
        else:
            D = mx-h["kinryo"]; f_was = 0 if D<=2 else min(D,pool)
        f_tas = tas(h, race)
        f_hcs = hcs(h)
        f_csi = h.get("csi", 0)
        f_nrja = nrja(h["last_race_days"])
        s2 = (tsi_score[i] + lts_final[i] + f_fsi + f_bonus + f_dsi + f_csi
              + f_nsi + f_was + f_tas + f_hcs + f_nrja)
        mult = KANKAI[h["style"]][stage]
        wavg = s2*mult
        rows.append(dict(num=h["num"], name=h["name"], style=h["style"],
            band=band, ltsrank=h["_lts_rank"], tsi=tsi_score[i], lts=lts_final[i],
            fsi=f_fsi, bonus=f_bonus, dsi=f_dsi, dsi_g=dsi_g, nsi=f_nsi, nsi_g=nsi_g,
            csi=f_csi, was=f_was, tas=f_tas, hcs=f_hcs, nrja=f_nrja,
            s2=round(s2,2), mult=mult, wavg=round(wavg,2)))

    # Power / %
    for r in rows: r["power"] = math.exp(r["wavg"]/14)
    tot = sum(r["power"] for r in rows)
    for r in rows: r["raw"] = r["power"]/tot*100
    top = max(r["raw"] for r in rows)
    if top > 30:
        f = 30/top
        for r in rows: r["pwin"] = r["raw"]*f
    else:
        for r in rows: r["pwin"] = r["raw"]
    rows.sort(key=lambda r: r["wavg"], reverse=True)

    # ランク + Case
    topw = rows[0]["wavg"]
    for r in rows:
        gr = (topw - r["wavg"])/topw
        r["rank"] = "S" if gr<=0.03 else "A" if gr<=0.08 else "B" if gr<=0.14 else "C"
    nS = sum(1 for r in rows if r["rank"]=="S")
    dr = rows[0]["pwin"]/rows[1]["pwin"] if len(rows)>1 and rows[1]["pwin"]>0 else 99
    if nS == 1:
        a = [r for r in rows if r["rank"]=="A"]
        nxt = a[0] if a else rows[1]
        gapSA = (rows[0]["wavg"]-nxt["wavg"])/rows[0]["wavg"]
        case = "Case1(三連複S軸→A+B上位/馬連S→A)" if gapSA<0.07 else "Case5(単勝+三連単S1着固定)"
        case += f"  gap(S-A)={gapSA*100:.2f}%"
    elif nS == 2: case = "Case2(馬連S同士+ワイド)"
    elif nS == 3: case = "Case3(三連複S BOX)"
    elif nS == 0: case = "Case4(ワイドA上位BOX)"
    else: case = f"Case?(S={nS})"
    drlbl = "①軸流し" if dr>=1.5 else "②BOX" if dr>=1.2 else "③分散"
    return dict(rows=rows, stage=stage, pace_log=pace_log,
                case=case, dr=round(dr,2), drlbl=drlbl)

def print_report(res):
    print("展開:", " / ".join(res["pace_log"]))
    print(f"DR={res['dr']} → {res['drlbl']}   {res['case']}\n")
    h = (f"{'馬':>2} {'名前':<12} {'脚':<3} {'TSI':>5} {'LTS':>5} {'FSI':>3} "
         f"{'Bon':>3} {'DSI':>4} {'NSI':>5} {'CSI':>3} {'WAS':>3} {'TAS':>3} "
         f"{'HCS':>4} {'NRJA':>4} {'S2':>6} {'乗':>4} {'WAvg':>6} {'PWin':>6} R")
    print(h)
    for r in res["rows"]:
        print(f"{r['num']:>2} {r['name']:<12} {r['style']:<3} {r['tsi']:>5} {r['lts']:>5} "
              f"{r['fsi']:>3} {r['bonus']:>3} {r['dsi']:>4}{r['dsi_g']:1} {r['nsi']:>5} "
              f"{r['csi']:>3} {r['was']:>3} {r['tas']:>3} {r['hcs']:>4} {r['nrja']:>4} "
              f"{r['s2']:>6} {r['mult']:>4} {r['wavg']:>6} {r['pwin']:>5.1f}% {r['rank']}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            race = json.load(f)
        print_report(run(race))
    else:
        print("usage: python calc.py race.json")
