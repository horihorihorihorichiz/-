# -*- coding: utf-8 -*-
"""miner_v2.py — MINING_PROTOCOL_20260817.md の機械探索実装。

事前登録グリッド（単一条件+2条件結合+3条件結合。4条件以上は組合せ爆発と
過学習リスクのため禁止）× 買い方5種 を flat100円で採掘し、
MINE(202409-202602) → VALIDATE(202603-202605) → CONFIRM(202606-202608) の
3段関門を機械的に1回だけ判定する。

段構成（事前固定・変更禁止）:
  1. MINE:     n>=40, ROI>=130%, null検定(レース間シャッフル×1000) p<0.05
  2. VALIDATE: n>=15, ROI>=110%   (MINE通過セルのみ・1回だけ計算)
  3. CONFIRM:  n>=10, ROI>=100%   (VALIDATE通過セルのみ・1回だけ計算)

null検定: セル内レースについて「オッズ/モデル序列(=受け手)」と
「着順+払戻(=出し手)」の対応をレース間でシャッフルする。着順は市場人気ランク
空間にエンコードし、受け手レースの同ランク馬が的中したとみなして出し手レースの
実払戻で精算する（単勝払戻=オッズ×100 は厳密、複勝/馬連/三連複は
「勝ち馬の人気ランクと払戻額」の同時分布を保存する近似）。
p = (1 + #{null ROI >= 観測 ROI}) / (B+1), B=1000, seed固定。

買い方（sim_rank.settle_fire と同定義・flat 100円/点）:
  tan1  単勝 モデル1位            1点
  tan2  単勝 モデル2位            1点
  fuku1 複勝 モデル1位            1点
  uma12 馬連 モデル1-2位          1点
  trio  三連複 モデル1位軸 - 相手=軸を除く市場人気上位3頭から2頭 C(3,2)=3点
        (軸が市場1番人気のとき相手はちょうど市場2-4番人気)

バンド定義は run 前に凍結（レース属性/シグナルの分布のみ参照・払戻は不参照）。
usage: python3 miner_v2.py [--path wf_preds_v3ext2.jsonl] [--out DIR]
"""
import argparse
import itertools
import json
import math
import os

import numpy as np

# ── 事前固定パラメータ ─────────────────────────────────────────────
MINE_END = "202602"
VAL_END = "202605"          # VALIDATE = 202603..202605
CONF_END = "202608"         # CONFIRM  = 202606..202608
MINE_N, MINE_ROI = 40, 130.0
VAL_N, VAL_ROI = 15, 110.0
CONF_N, CONF_ROI = 10, 100.0
NULL_B = 1000
NULL_P = 0.05
SEED = 20260817
MAX_COMBO = 3               # 4条件以上は禁止（事前登録）

CENTRAL4 = {"東京", "中山", "京都", "阪神"}
STYLES = ["tan1", "tan2", "fuku1", "uma12", "trio"]
STAKE = {"tan1": 100.0, "tan2": 100.0, "fuku1": 100.0, "uma12": 100.0, "trio": 300.0}


def p_from_scores(sc):
    """v2_live.rescore と同じ softmax → 30%cap+再正規化 (sim_rank.py と同一)"""
    mx = max(sc.values())
    e = {n: math.exp(v - mx) for n, v in sc.items()}
    Z = sum(e.values())
    p = {n: v / Z for n, v in e.items()}
    for _ in range(len(p)):
        over = {n: v for n, v in p.items() if v > 0.30 + 1e-12}
        if not over:
            break
        rest = {n: v for n, v in p.items() if n not in over}
        room = 1.0 - 0.30 * len(over)
        sm = sum(rest.values())
        for n in over:
            p[n] = 0.30
        if sm > 0:
            for n in rest:
                p[n] = rest[n] / sm * room
    return p


def load(path):
    """レース読み込み + 市場人気ランク空間へのエンコード"""
    R = []
    for l in open(path, encoding="utf-8"):
        d = json.loads(l)
        pay = d.get("payout") or d.get("pay") or {}
        if not pay.get("単勝"):
            continue
        order = [int(x) for x in d["order"]]
        sc_raw = d["scores"]
        sc = {n: float(v) for n, v in zip(order, sc_raw)} if isinstance(sc_raw, list) \
            else {int(k): float(v) for k, v in sc_raw.items()}
        odds = {int(k): float(v) for k, v in (d.get("odds") or {}).items() if v}
        so = sorted(sc, key=lambda n: -sc[n])
        rid = d["rid"]
        # 市場人気ランク (1=最低オッズ)。同オッズは馬番昇順で確定的に。
        by_odds = sorted(odds, key=lambda h: (odds[h], h))
        rank = {h: i + 1 for i, h in enumerate(by_odds)}
        t1, t2 = order[0], (order[1] if len(order) > 1 else None)
        if t1 not in odds or t2 is None or t2 not in odds:
            continue  # 受け手として精算不能（対象データでは発生しない）
        # trio相手: 軸を除く市場人気上位3頭
        mtop = [h for h in by_odds if h != t1][:3]
        # 結果エンコード: 勝ち馬/複勝/馬連/三連複 をランク+払戻で保持
        w = [(rank[int(h)], float(v)) for h, v in pay["単勝"].items()]
        fuku = [(rank[int(h)], float(v)) for h, v in (pay.get("複勝") or {}).items()]
        uma = [(tuple(sorted(rank[int(x)] for x in k.split("-"))), float(v))
               for k, v in (pay.get("馬連") or {}).items()]
        tri = [(tuple(sorted(rank[int(x)] for x in k.split("-"))), float(v))
               for k, v in (pay.get("三連複") or {}).items()]
        R.append(dict(
            rid=rid, month=d["month"],
            surface=d.get("surface"), dist=int(d.get("dist") or 0),
            field=int(d.get("field") or len(order)), tier=d.get("tier"),
            day=int(rid[8:10]), venue=d.get("venue"),
            baba=(d.get("baba") or "").strip(),
            g12=sc[so[0]] - sc[so[1]] if len(so) > 1 else 9.0,
            sp15=sc[so[0]] - sc[so[4]] if len(so) > 4 else None,
            p1=p_from_scores(sc)[so[0]],
            o1=odds.get(so[0]), o2=odds.get(so[1]) if len(so) > 1 else None,
            m1=min(odds.values()),
            t1r=rank[t1], t2r=rank[t2],
            partners=[rank[h] for h in mtop] if len(mtop) == 3 else None,
            w=w, fuku=fuku, uma=uma, tri=tri,
            order=order, odds=odds, pay=pay))
    return R


def to_arrays(R):
    """numpy化。dead heat スロット: 勝2/複4/馬連2/三連複2 (データ検証済み上限)"""
    n = len(R)
    A = dict(
        t1r=np.full(n, -9, np.int32), t2r=np.full(n, -9, np.int32),
        P=np.full((n, 3), -9, np.int32),
        W=np.full((n, 2), -1, np.int32), WP=np.zeros((n, 2)),
        FR=np.full((n, 4), -1, np.int32), FP=np.zeros((n, 4)),
        UR=np.full((n, 2, 2), -1, np.int32), UP=np.zeros((n, 2)),
        TR=np.full((n, 2, 3), -1, np.int32), TP=np.zeros((n, 2)),
        trio_ok=np.zeros(n, bool))
    for i, r in enumerate(R):
        A["t1r"][i], A["t2r"][i] = r["t1r"], r["t2r"]
        if r["partners"]:
            A["P"][i] = r["partners"]
            A["trio_ok"][i] = True
        for s, (rk, v) in enumerate(r["w"][:2]):
            A["W"][i, s], A["WP"][i, s] = rk, v
        for s, (rk, v) in enumerate(r["fuku"][:4]):
            A["FR"][i, s], A["FP"][i, s] = rk, v
        for s, (pr, v) in enumerate(r["uma"][:2]):
            A["UR"][i, s], A["UP"][i, s] = pr, v
        for s, (tr, v) in enumerate(r["tri"][:2]):
            A["TR"][i, s], A["TP"][i, s] = tr, v
    return A


def returns_for(A, recip, donor):
    """recip(受け手index列) と donor(出し手index行列 shape=(..,n)) の払戻(円/flat100円)。
    donor==recip(恒等) で観測値。戻り: style→ndarray shape=donor.shape"""
    t1r = A["t1r"][recip]
    t2r = A["t2r"][recip]
    P = A["P"][recip]
    a = np.minimum(t1r, t2r)
    b = np.maximum(t1r, t2r)
    W, WP = A["W"][donor], A["WP"][donor]        # (..,n,2)
    FR, FP = A["FR"][donor], A["FP"][donor]
    UR, UP = A["UR"][donor], A["UP"][donor]
    TR, TP = A["TR"][donor], A["TP"][donor]
    out = {}
    out["tan1"] = ((t1r[..., None] == W) * WP).sum(-1)
    out["tan2"] = ((t2r[..., None] == W) * WP).sum(-1)
    out["fuku1"] = ((t1r[..., None] == FR) * FP).sum(-1)
    out["uma12"] = (((a[..., None] == UR[..., 0]) & (b[..., None] == UR[..., 1])) * UP).sum(-1)
    # trio: 出し手三連複 {x,y,z} が 軸t1r を含み、残り2頭が相手集合Pに含まれれば
    # ちょうど1点的中 (C(3,2)=3点買いのうち1点)
    ist1 = TR == t1r[..., None, None]                       # (..,n,2,3)
    inP = ((TR[..., None] == P[..., None, None, :]).any(-1))
    hit = (ist1.sum(-1) == 1) & ((ist1 | inP).sum(-1) == 3)
    trio = (hit * TP).sum(-1) * A["trio_ok"][recip]
    out["trio"] = trio
    return out


def settle_direct(r):
    """馬番恒等での直接精算（ランク空間エンコードの検証用）"""
    o, pay = r["order"], r["pay"]
    ret = {}
    ret["tan1"] = float((pay["単勝"]).get(str(o[0]), 0))
    ret["tan2"] = float((pay["単勝"]).get(str(o[1]), 0)) if len(o) > 1 else 0.0
    ret["fuku1"] = float((pay.get("複勝") or {}).get(str(o[0]), 0))
    k = "-".join(str(x) for x in sorted(o[:2]))
    ret["uma12"] = float((pay.get("馬連") or {}).get(k, 0)) if len(o) > 1 else 0.0
    t1 = o[0]
    by_odds = sorted(r["odds"], key=lambda h: (r["odds"][h], h))
    mtop = [h for h in by_odds if h != t1][:3]
    tot = 0.0
    if len(mtop) == 3:
        for pp in itertools.combinations(mtop, 2):
            kk = "-".join(str(x) for x in sorted([t1, *pp]))
            tot += float((pay.get("三連複") or {}).get(kk, 0))
    ret["trio"] = tot
    return ret


# ── バンド定義（凍結・払戻不参照で分布のみから設定）───────────────────
def build_axes(R):
    """axis → [(band_label, bool ndarray)]"""
    n = len(R)

    def arr(f):
        return np.array([f(r) for r in R])

    surface = arr(lambda r: r["surface"])
    dist = arr(lambda r: r["dist"])
    field = arr(lambda r: r["field"])
    tier = arr(lambda r: r["tier"] if r["tier"] is not None else -1)
    day = arr(lambda r: r["day"])
    venue = arr(lambda r: r["venue"])
    baba = arr(lambda r: r["baba"])
    g12 = arr(lambda r: r["g12"])
    sp15 = arr(lambda r: r["sp15"] if r["sp15"] is not None else np.nan)
    p1 = arr(lambda r: r["p1"])
    o1 = arr(lambda r: r["o1"] if r["o1"] else np.nan)
    o2 = arr(lambda r: r["o2"] if r["o2"] else np.nan)
    m1 = arr(lambda r: r["m1"])
    central = np.isin(venue, list(CENTRAL4))

    def bands(x, edges, labels):
        out = []
        for (lo, hi), lb in zip(edges, labels):
            m = ~np.isnan(x) & (x >= lo) & (x < hi)
            out.append((lb, m))
        return out

    axes = {
        "surface": [("芝", surface == "芝"), ("ダ", surface == "ダ")],
        "dist": bands(dist.astype(float),
                      [(0, 1400), (1400, 1800), (1800, 2200), (2200, 9e9)],
                      ["短<1400", "ﾏｲﾙ1400-1799", "中1800-2199", "長2200+"]),
        "field": bands(field.astype(float),
                       [(0, 9), (9, 13), (13, 17), (17, 19)],
                       ["頭数<=8", "頭数9-12", "頭数13-16", "頭数17-18"]),
        "tier": bands(tier.astype(float), [(0, 6), (6, 10), (10, 99)],
                      ["tier<=5", "tier6-9", "tier>=10"]),
        "day": [("初日", day == 1), ("2日目+", day >= 2)],
        "vgroup": [("中央4場", central), ("ローカル", ~central)],
        "baba": [("良", baba == "良"), ("道悪", np.isin(baba, ["稍", "重", "不"]))],
        "g12": bands(g12, [(-9, 0.10), (0.10, 0.25), (0.25, 0.40), (0.40, 99)],
                     ["g12<0.10", "g12 0.10-0.25", "g12 0.25-0.40", "g12>=0.40"]),
        "sp15": bands(sp15, [(-9, 0.25), (0.25, 0.50), (0.50, 0.90), (0.90, 99)],
                      ["sp15<0.25", "sp15 0.25-0.50", "sp15 0.50-0.90", "sp15>=0.90"]),
        "p1": bands(p1, [(0, 0.10), (0.10, 0.15), (0.15, 0.22), (0.22, 1.01)],
                    ["p1<0.10", "p1 0.10-0.15", "p1 0.15-0.22", "p1>=0.22"]),
        "o1": bands(o1, [(3, 5), (5, 8), (8, 12), (12, 20), (20, 9e9)],
                    ["o1 3-5", "o1 5-8", "o1 8-12", "o1 12-20", "o1 20+"]),
        "o2": bands(o2, [(3, 5), (5, 8), (8, 12), (12, 20), (20, 9e9)],
                    ["o2 3-5", "o2 5-8", "o2 8-12", "o2 12-20", "o2 20+"]),
        "m1": bands(m1, [(0, 1.5), (1.5, 3.0), (3.0, 9e9)],
                    ["市場1位<1.5", "市場1位1.5-3", "市場1位3+"]),
    }
    return axes


def enumerate_cells(axes):
    """1〜MAX_COMBO 軸の全組合せ × 各軸バンドの直積"""
    names = list(axes)
    cells = []
    for k in range(1, MAX_COMBO + 1):
        for combo in itertools.combinations(names, k):
            band_lists = [axes[a] for a in combo]
            for picks in itertools.product(*band_lists):
                label = " & ".join(lb for lb, _ in picks)
                mask = picks[0][1]
                for _, m in picks[1:]:
                    mask = mask & m
                cells.append((label, combo, mask))
    return cells


def null_test(A, idx, style, obs_ret, rng, B=NULL_B):
    """セル内(MINE)レース間シャッフル null検定。p = (1+#{null>=obs})/(B+1)"""
    n = len(idx)
    perms = np.tile(np.arange(n), (B, 1))
    perms = rng.permuted(perms, axis=1)
    donor = idx[perms]                      # (B, n)
    # メモリ節約: chunk
    chunk = max(1, int(1e6 // max(n, 1)))
    ge = 0
    for s in range(0, B, chunk):
        d = donor[s:s + chunk]
        ret = returns_for(A, idx, d)[style].sum(axis=1)
        ge += int((ret >= obs_ret - 1e-9).sum())
    return (1 + ge) / (B + 1)


def stats_for(mask, split_mask, obs, style):
    m = mask & split_mask
    n = int(m.sum())
    if n == 0:
        return n, 0.0, 0.0
    ret = float(obs[style][m].sum())
    stake = n * STAKE[style]
    hit = float((obs[style][m] > 0).mean())
    return n, ret / stake * 100.0, hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="wf_preds_v3ext2.jsonl")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()

    R = load(a.path)
    months = np.array([r["month"] for r in R])
    mine_m = months <= MINE_END
    val_m = (months > MINE_END) & (months <= VAL_END)
    conf_m = (months > VAL_END) & (months <= CONF_END)
    print(f"races={len(R)} MINE={mine_m.sum()} VAL={val_m.sum()} CONF={conf_m.sum()}")

    A = to_arrays(R)
    ident = np.arange(len(R))
    obs = returns_for(A, ident, ident)      # 観測払戻(ランク空間・恒等)

    # ── 検証: ランク空間精算 == 馬番直接精算 (全レース×全買い方) ──
    bad = 0
    for i, r in enumerate(R):
        d = settle_direct(r)
        for st in STYLES:
            if abs(d[st] - float(obs[st][i])) > 1e-6:
                bad += 1
                if bad <= 5:
                    print("MISMATCH", r["rid"], st, d[st], float(obs[st][i]))
    print(f"encoding verification: mismatches={bad} / {len(R)*len(STYLES)} settlements")
    assert bad == 0, "rank-space encoding mismatch — abort"

    axes = build_axes(R)
    cells = enumerate_cells(axes)
    n_cells = len(cells)
    n_trials = n_cells * len(STYLES)
    print(f"cells={n_cells} (1-3条件) × styles={len(STYLES)} → trials={n_trials}")

    rng = np.random.default_rng(SEED)

    # ── Stage 1: MINE (n>=40, ROI>=130) ───────────────────────────
    mine_pass = []
    for label, combo, mask in cells:
        mm = mask & mine_m
        n = int(mm.sum())
        if n < MINE_N:
            continue
        for st in STYLES:
            ret = float(obs[st][mm].sum())
            stake = n * STAKE[st]
            roi = ret / stake * 100.0
            if roi >= MINE_ROI:
                hit = float((obs[st][mm] > 0).mean())
                mine_pass.append(dict(cell=label, axes=list(combo), style=st,
                                      mine_n=n, mine_roi=round(roi, 1),
                                      mine_hit=round(hit * 100, 1)))
                mine_pass[-1]["_mask"] = mask
    print(f"MINE基準通過(null検定前): {len(mine_pass)}")

    # ── Stage 1b: null検定 ────────────────────────────────────────
    null_pass = []
    for c in mine_pass:
        idx = np.where(c["_mask"] & mine_m)[0]
        obs_ret = float(obs[c["style"]][idx].sum())
        p = null_test(A, idx, c["style"], obs_ret, rng)
        c["null_p"] = round(p, 4)
        if p < NULL_P:
            null_pass.append(c)
    print(f"null検定(p<{NULL_P})通過: {len(null_pass)}")

    # ── Stage 2: VALIDATE (通過セルのみ・1回だけ) ─────────────────
    val_pass = []
    for c in null_pass:
        n, roi, hit = stats_for(c["_mask"], val_m, obs, c["style"])
        c["val_n"], c["val_roi"], c["val_hit"] = n, round(roi, 1), round(hit * 100, 1)
        if n >= VAL_N and roi >= VAL_ROI:
            val_pass.append(c)
    print(f"VALIDATE通過: {len(val_pass)}")

    # ── Stage 3: CONFIRM (VALIDATE通過のみ・1回だけ) ──────────────
    conf_pass = []
    for c in val_pass:
        n, roi, hit = stats_for(c["_mask"], conf_m, obs, c["style"])
        c["conf_n"], c["conf_roi"], c["conf_hit"] = n, round(roi, 1), round(hit * 100, 1)
        # 合算[候補]ROI = VALIDATE+CONFIRM
        vc = c["_mask"] & (val_m | conf_m)
        nn = int(vc.sum())
        c["vc_n"] = nn
        c["vc_roi"] = round(float(obs[c["style"]][vc].sum()) / (nn * STAKE[c["style"]]) * 100, 1) if nn else 0.0
        if n >= CONF_N and roi >= CONF_ROI:
            conf_pass.append(c)
    print(f"CONFIRM通過: {len(conf_pass)}")

    # ── 多重比較の記録 ────────────────────────────────────────────
    exp_null_pass = len(mine_pass) * NULL_P            # null検定の偶然通過期待
    exp_val_pass = len(null_pass) * 0.05               # VALIDATE偶然通過期待(規約: 試行数×0.05)
    verdict_3x = len(val_pass) >= 3 * exp_val_pass and len(val_pass) > 0
    summary = dict(
        data=a.path, n_races=len(R),
        splits=dict(MINE=int(mine_m.sum()), VALIDATE=int(val_m.sum()), CONFIRM=int(conf_m.sum())),
        n_cells=n_cells, n_styles=len(STYLES), n_trials=n_trials,
        mine_pass_pre_null=len(mine_pass), null_pass=len(null_pass),
        val_pass=len(val_pass), conf_pass=len(conf_pass),
        expected_null_pass_by_chance=round(exp_null_pass, 1),
        expected_val_pass_by_chance=round(exp_val_pass, 2),
        val_pass_3x_rule=("PASS" if verdict_3x else "FAIL"),
        seed=SEED, null_B=NULL_B)
    print(json.dumps(summary, ensure_ascii=False, indent=1))

    def clean(c):
        return {k: v for k, v in c.items() if not k.startswith("_")}

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "miner_v2_result.json"), "w", encoding="utf-8") as f:
        json.dump(dict(summary=summary,
                       mine_pass=[clean(c) for c in mine_pass],
                       val_pass=[clean(c) for c in val_pass],
                       conf_pass=[clean(c) for c in conf_pass]),
                  f, ensure_ascii=False, indent=1)
    print("saved:", os.path.join(a.out, "miner_v2_result.json"))


if __name__ == "__main__":
    main()
