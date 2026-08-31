# -*- coding: utf-8 -*-
"""ファミリー5: 上がり性能の文脈（races[].agariを距離・馬場・ペース文脈で使う）。
   - 距離帯別標準上がりとの差（残差）: ベスト/直近3走平均
   - 上がり最速歴プロキシ（残差が+0.5s以上速かった率）
   - 上がり×コーナー位置（後方から速い上がり=差し脚の質）
   - 今日の距離帯にマッチした過去走のベスト上がり残差
   usage: python3 exp_agari_context.py
"""
import glob
import json
import os

import exp_harness as H

CLIP = 2.5

# ---- 標準上がりテーブル構築（過去走レコードのみ＝レース前情報。結果情報は不使用） ----
def build_table(histdir="hist"):
    acc = {}
    for f in glob.glob(os.path.join(histdir, "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for h in d["race"]["horses"]:
            for pr in h.get("races", []):
                a = pr.get("agari")
                s = pr.get("surface")
                dist = pr.get("dist")
                if not a or not s or not dist:
                    continue
                db = int(round(dist / 200.0) * 200)
                p = pr.get("pace")
                for key in ((s, db, p), (s, db), (s,)):
                    if key not in acc:
                        acc[key] = [0.0, 0]
                    acc[key][0] += a
                    acc[key][1] += 1
    return {k: (v[0] / v[1], v[1]) for k, v in acc.items()}


TBL = build_table()


def _resid(pr):
    """標準上がりとの差。正=標準より速い。クリップ±2.5s"""
    a = pr.get("agari")
    s = pr.get("surface")
    dist = pr.get("dist")
    if not a or not s or not dist:
        return None
    db = int(round(dist / 200.0) * 200)
    p = pr.get("pace")
    for key in ((s, db, p), (s, db), (s,)):
        t = TBL.get(key)
        if t and t[1] >= 30:
            return max(-CLIP, min(CLIP, t[0] - a))
    return None


def _pos4(pr):
    """4角相対位置 0(先頭)〜1(最後方)"""
    c = pr.get("corner4")
    fld = pr.get("field")
    if not c or not fld or fld < 2:
        return None
    return (c - 1) / (fld - 1)


# ---- 特徴量定義 ----

def agari_best_rel(h, race, rid):
    """過去9走のベスト上がり残差（距離・ペース補正済み）"""
    rs = [_resid(pr) for pr in h.get("races", [])]
    rs = [x for x in rs if x is not None]
    return max(rs) if rs else None


def agari_mean3_rel(h, race, rid):
    """直近3走の上がり残差平均"""
    rs = [_resid(pr) for pr in h.get("races", [])[:3]]
    rs = [x for x in rs if x is not None]
    return sum(rs) / len(rs) if rs else None


def agari_fast_rate(h, race, rid):
    """上がり最速歴プロキシ: 残差+0.5s以上（=その文脈で速い部類）だった過去走の率"""
    rs = [_resid(pr) for pr in h.get("races", [])]
    rs = [x for x in rs if x is not None]
    if not rs:
        return None
    return sum(1 for x in rs if x >= 0.5) / len(rs)


def agari_close_q(h, race, rid):
    """差し脚の質: 4角で後方(相対位置>=0.5)から出した上がり残差のベスト"""
    best = None
    for pr in h.get("races", []):
        p = _pos4(pr)
        r = _resid(pr)
        if p is None or r is None or p < 0.5:
            continue
        if best is None or r > best:
            best = r
    return best


def agari_dist_match(h, race, rid):
    """今日の距離±200mの過去走に限ったベスト上がり残差"""
    today = race.get("distance")
    if not today:
        return None
    rs = [_resid(pr) for pr in h.get("races", [])
          if pr.get("dist") and abs(pr["dist"] - today) <= 200]
    rs = [x for x in rs if x is not None]
    return max(rs) if rs else None


def main():
    ds = H.load_base()
    H.add_feature(ds, "agari_best_rel", agari_best_rel)
    H.add_feature(ds, "agari_mean3_rel", agari_mean3_rel)
    H.add_feature(ds, "agari_fast_rate", agari_fast_rate)
    H.add_feature(ds, "agari_close_q", agari_close_q)
    H.add_feature(ds, "agari_dist_match", agari_dist_match)

    results = []
    results.append(H.run_experiment(
        ds, extra=["agari_best_rel", "agari_mean3_rel"],
        label="A1_ベスト+直近3走残差"))
    results.append(H.run_experiment(
        ds, extra=["agari_best_rel", "agari_mean3_rel", "agari_close_q"],
        label="A2_A1+差し脚の質"))
    results.append(H.run_experiment(
        ds, extra=["agari_best_rel", "agari_mean3_rel", "agari_fast_rate",
                   "agari_close_q"],
        label="A3_A2+最速歴率"))
    results.append(H.run_experiment(
        ds, extra=["agari_dist_match", "agari_mean3_rel", "agari_close_q"],
        label="A4_距離マッチ版"))

    print("\n==== summary ====")
    for r in results:
        print(f"{r['label']}: train={r['train']['capture5']:.1f} "
              f"test={r['test']['capture5']:.1f} gate={r['gate']}")
        print(f"  weights={dict(zip(r['feats'], r['weights']))}")


if __name__ == "__main__":
    main()
