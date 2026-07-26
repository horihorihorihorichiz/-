# -*- coding: utf-8 -*-
"""hist/ の today_vg=2 固定バグを修正する（V4 の前段）。

   収穫当時の harvest.py が today_vg を 2 に決め打ちしていたため、学習データ
   6,701件すべてで today_vg=2 になっていた。calc.py はこの値で LTS 配点を
   切り替える（calc.py L384）ので、内回り/外回り・瞬発/消耗の区別を
   モデルは一度も学習していない。course.course_vg() で再計算して上書きする。

   ※ hist は収穫時に馬柱の "_venue" を落としているため、**過去走ごとの vg**
     （各 races[].vg）は復元できない。こちらは全件 2 のまま残る＝既知の制約。
     今日のコース特性(today_vg)だけを正す。

   usage: python3 hist_fix_vg.py [--dry-run] [--histdir hist]
"""
import argparse, collections, glob, json, os

import course


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--histdir", default="hist")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    before = collections.Counter()
    after = collections.Counter()
    unknown_venue = collections.Counter()
    changed = total = 0

    for path in sorted(glob.glob(os.path.join(a.histdir, "*.json"))):
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        r = d.get("race") or {}
        venue = (r.get("venue") or "").strip()
        if venue not in course._VENUES:
            # NARコード保存の可能性（rid 5-6桁目）
            venue = course.NAR_CODE.get(venue, venue)
        if venue not in course._VENUES:
            unknown_venue[r.get("venue")] += 1
            continue
        vg = course.course_vg(venue, r.get("surface"), r.get("distance"))
        total += 1
        before[r.get("today_vg")] += 1
        after[vg] += 1
        if r.get("today_vg") == vg:
            continue
        changed += 1
        if a.dry_run:
            continue
        r["today_vg"] = vg
        json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False)

    print(f"対象 {total}件 / 書換 {changed}件" + ("（dry-run: 書いていない）" if a.dry_run else ""))
    print("  修正前 today_vg:", dict(sorted(before.items(), key=lambda x: (x[0] is None, x[0]))))
    print("  修正後 today_vg:", dict(sorted(after.items(), key=lambda x: (x[0] is None, x[0]))))
    for k, v in after.items():
        print(f"    VG{k} {course.VG_LABEL[k]}: {v}件")
    if unknown_venue:
        print("  ⚠️ 場名不明でスキップ:", dict(unknown_venue))
    print("  ※過去走ごとの vg は _venue が hist に残っていないため復元不可（全件2のまま）")


if __name__ == "__main__":
    main()
