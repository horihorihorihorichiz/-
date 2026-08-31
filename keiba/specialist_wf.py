# -*- coding: utf-8 -*-
"""specialist_wf.py — SPECIALIST_PROTOCOL_20260817.md の実装。

「条件を絞り、その条件専用に学習したモデルは汎用モデルを凌駕するか」を
月次ウォークフォワードで実測する。

設計（事前登録書どおり・実行前凍結）:
  - ベースライン: wf_preds_v3ext2.jsonl（汎用V3 LambdaRank 28特徴のWF予測 5,990R）。
    再現性検証済み: 現行コードで fold 202409 を再学習 → 206/206レースで order 完全一致・
    score差 0.0。よって専用との差は「学習データの絞り」だけに帰着する。
  - 専用モデル: 汎用V3と**同一の特徴(28)・同一ハイパラ・同一学習手順**(wf_compare.train_fold /
    VARIANTS["v3"] をそのまま使用)。差はセグメントによる学習データの絞りのみ。
  - セグメント定義（事前登録書 §設計・距離帯境界は MINING_PROTOCOL の凍結バンドを踏襲）:
      S1: 馬場×距離帯 6分割 = surface(芝/ダ) × dist(短<1400 / ﾏｲﾙ1400-1799 / 中長1800+)
      S2: クラス帯 3分割 = tier>=10(未勝利新馬) / tier6-9(条件戦) / tier<=5(上級)
      S3: 頭数帯 2分割 = 頭数<=12 / 頭数13+
  - フォールド時点のセグメント学習データが 800頭未満 → 「専用なし=汎用予測を流用」と記録。
    (安全ガード: 800頭以上でも train/val 分割が成立しない(レース数<=n_val)場合は同様に
     流用と記録し件数を報告する。想定発生数0。)
  - 分割(変更禁止): MINE=202409-202602 / VALIDATE=202603-202605 / CONFIRM=202606-202608
  - 凌駕判定(事前登録書 基準1・機械適用):
      VALIDATE: 単勝flat ROI が汎用比 +10pt以上 かつ モデル1位勝率 >= 汎用
      → CONFIRM でも ROI 汎用比 +5pt以上 を維持。

usage:
  python3 specialist_wf.py run            # WF実行 → wf_preds_spec_s{1,2,3}.jsonl
  python3 specialist_wf.py compare        # セグメント別 比較表 + 凌駕判定
"""
import json
import math
import os
import sys
from collections import defaultdict

import wf_compare as W

BASELINE = "wf_preds_v3ext2.jsonl"
START_FOLD = "202409"
MIN_HORSES = 800                       # 事前登録: これ未満は専用なし=汎用流用
MINE_END, VAL_END, CONF_END = "202602", "202605", "202608"
V3SPEC = W.VARIANTS["v3"]              # dict(v4=False, params={}) — 汎用と完全同一


# ── セグメント定義（凍結） ──────────────────────────────────────────
def seg_s1(r):
    d = r["dist"] or 0
    band = "短" if d < 1400 else ("ﾏｲﾙ" if d < 1800 else "中長")
    return f"{r['surface']}{band}"


def seg_s2(r):
    t = r["tier"] if r["tier"] is not None else -1
    return "tier>=10" if t >= 10 else ("tier6-9" if t >= 6 else "tier<=5")


def seg_s3(r):
    return "頭数<=12" if len(r["ns"]) <= 12 else "頭数13+"


SCHEMES = {"s1": seg_s1, "s2": seg_s2, "s3": seg_s3}


def load_baseline():
    base = {}
    for line in open(BASELINE, encoding="utf-8"):
        d = json.loads(line)
        base[d["rid"]] = d
    return base


def run():
    ds = W.load_ds()
    base = load_baseline()
    months = sorted({r["date"][:6] for r in ds})
    folds = [m for m in months if m >= START_FOLD]
    print(f"データ {len(ds)}R / folds {folds[0]}..{folds[-1]} ({len(folds)}) / "
          f"baseline {len(base)}R", flush=True)

    outs = {sc: [] for sc in SCHEMES}
    n_train_calls = 0
    guard_hits = []                    # 800頭以上なのに分割不能だったケース(想定0)
    for m in folds:
        train_all = [r for r in ds if r["date"][:6] < m]
        fold = [r for r in ds if r["date"][:6] == m]
        if len(train_all) < 400 or not fold:
            continue
        for sc, fn in SCHEMES.items():
            # フォールド内レースをセグメントに分ける
            by_seg = defaultdict(list)
            for r in fold:
                by_seg[fn(r)].append(r)
            for seg, fold_rs in sorted(by_seg.items()):
                train_seg = [r for r in train_all if fn(r) == seg]
                horses = sum(len(r["ns"]) for r in train_seg)
                n_val = max(50, len(train_seg) // 10)
                trainable = horses >= MIN_HORSES and len(train_seg) - n_val >= 1
                if horses >= MIN_HORSES and not trainable:
                    guard_hits.append((m, sc, seg, len(train_seg), horses))
                if trainable:
                    model = W.train_fold(train_seg, V3SPEC)
                    n_train_calls += 1
                    preds = [W.predict(model, r, V3SPEC["v4"]) for r in fold_rs]
                else:
                    preds = None       # 汎用流用
                for i, r in enumerate(fold_rs):
                    b = base[r["rid"]]
                    if preds is None:
                        order, scores = b["order"], b["scores"]
                    else:
                        s = preds[i]
                        order = sorted(s, key=lambda x: -s[x])
                        scores = [round(s[n], 4) for n in order]
                    outs[sc].append(dict(
                        rid=r["rid"], month=m, segment=seg,
                        spec_used=bool(preds is not None),
                        train_races=len(train_seg), train_horses=horses,
                        order=order, scores=scores,
                        odds=r["odds"], top3=r["top3"],
                        payout=r.get("payout") or {},
                        surface=r["surface"], dist=r["dist"], tier=r["tier"],
                        baba=r["baba"], venue=r["venue"], field=len(r["ns"])))
        done = sum(len(v) for v in outs.values())
        print(f"[{m}] {len(fold)}R×3scheme 済 (累計学習 {n_train_calls} / 行 {done})",
              flush=True)

    for sc in SCHEMES:
        path = f"wf_preds_spec_{sc}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for x in outs[sc]:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
        print(f"{path}: {len(outs[sc])}R", flush=True)
    print(f"総学習回数 {n_train_calls} / 分割不能ガード発動 {len(guard_hits)} 件 {guard_hits}",
          flush=True)


# ── 比較 ────────────────────────────────────────────────────────────
def split_of(m):
    if m <= MINE_END:
        return "MINE"
    if m <= VAL_END:
        return "VALIDATE"
    return "CONFIRM"


def ndcg3(order, top3):
    rel = {top3[0]: 3, top3[1]: 2, top3[2]: 1}
    dcg = sum((2 ** rel.get(h, 0) - 1) / math.log2(i + 2)
              for i, h in enumerate(order[:3]))
    ideal = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate((3, 2, 1)))
    return dcg / ideal


def tan_ret(d, top):
    return float((d["payout"].get("単勝") or {}).get(str(top), 0))


class Agg:
    def __init__(self):
        self.n = 0
        self.win = 0
        self.ret = 0.0
        self.ndcg = 0.0
        self.used = 0

    def add(self, order, d, used):
        self.n += 1
        self.win += (order[0] == d["top3"][0])
        self.ret += tan_ret(d, order[0])
        self.ndcg += ndcg3(order, d["top3"])
        self.used += used

    def out(self):
        n = max(self.n, 1)
        return dict(n=self.n, win=self.win / n * 100, roi=self.ret / n,
                    ndcg=self.ndcg / n * 100, used=self.used)


def compare():
    base = load_baseline()
    result = {}
    for sc in SCHEMES:
        rows = [json.loads(l) for l in open(f"wf_preds_spec_{sc}.jsonl", encoding="utf-8")]
        agg = defaultdict(lambda: (Agg(), Agg()))     # (spec, gen)
        for d in rows:
            b = base[d["rid"]]
            key = (d["segment"], split_of(d["month"]))
            a_s, a_g = agg[key]
            a_s.add(d["order"], d, d["spec_used"])
            a_g.add(b["order"], d, 0)
        segs = sorted({k[0] for k in agg})
        res = {}
        for seg in segs:
            res[seg] = {}
            for sp in ("MINE", "VALIDATE", "CONFIRM"):
                a_s, a_g = agg.get((seg, sp), (Agg(), Agg()))
                res[seg][sp] = dict(spec=a_s.out(), gen=a_g.out())
        result[sc] = res

    # 表示 + 凌駕判定(基準1機械適用)
    superior = []
    for sc, res in result.items():
        print(f"\n===== {sc.upper()} =====")
        print(f"{'segment':<10s} {'split':<9s} {'n':>4s} {'専用使用':>5s} "
              f"{'勝率 専/汎':>14s} {'ROI 専/汎':>16s} {'ΔROI':>7s} {'NDCG3 専/汎':>14s}")
        for seg, sps in res.items():
            for sp in ("MINE", "VALIDATE", "CONFIRM"):
                s, g = sps[sp]["spec"], sps[sp]["gen"]
                if s["n"] == 0:
                    continue
                print(f"{seg:<10s} {sp:<9s} {s['n']:>4d} {s['used']:>5d} "
                      f"{s['win']:>6.1f}/{g['win']:<6.1f} "
                      f"{s['roi']:>7.1f}/{g['roi']:<7.1f} {s['roi']-g['roi']:>+7.1f} "
                      f"{s['ndcg']:>6.1f}/{g['ndcg']:<6.1f}")
            v_s, v_g = sps["VALIDATE"]["spec"], sps["VALIDATE"]["gen"]
            c_s, c_g = sps["CONFIRM"]["spec"], sps["CONFIRM"]["gen"]
            val_ok = (v_s["n"] > 0 and (v_s["roi"] - v_g["roi"]) >= 10.0
                      and v_s["win"] >= v_g["win"])
            conf_ok = c_s["n"] > 0 and (c_s["roi"] - c_g["roi"]) >= 5.0
            verdict = "凌駕" if (val_ok and conf_ok) else \
                      ("VAL通過/CONF落ち" if val_ok else "不成立")
            print(f"  → 判定[{seg}]: {verdict}"
                  f"  (VAL ΔROI{v_s['roi']-v_g['roi']:+.1f}pt 勝率{v_s['win']:.1f}vs{v_g['win']:.1f}"
                  f" / CONF ΔROI{c_s['roi']-c_g['roi']:+.1f}pt)")
            if val_ok and conf_ok:
                superior.append((sc, seg))
    print(f"\n凌駕セグメント: {superior if superior else 'なし → 仮説不成立(基準3)'}")
    outp = os.environ.get("SPEC_OUT", "specialist_compare_result.json")
    json.dump(dict(result=result, superior=superior), open(outp, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=float)
    print("saved:", outp)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        run()
    elif cmd == "compare":
        compare()
    else:
        sys.exit(f"unknown cmd {cmd}")
