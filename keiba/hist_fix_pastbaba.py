# -*- coding: utf-8 -*-
"""hist/ の過去走 baba_idx を遡及補完する（train/serve統一 第3弾）。

   ライブ(fetch_race)は7/27から過去走のbaba_idxを保存するが、既存hist 6,701件の
   過去走は全てNone。netkeibaを再取得せずに、手元の全レースDB
   (hist / hist_enrich / hist2023 / hist_nar) から (馬名, 走破日)→馬場 の対応表を作り、
   past run の日付 = レース日 − days で突き合わせて埋める。
   馬は1日1走なので (馬名, 日付) は一意キー。過去走の馬場は「予測日に既知の歴史的事実」
   なのでリークではない（ライブがnetkeibaから得るのと同じ情報）。

   usage: python3 hist_fix_pastbaba.py [--dry-run]
"""
import argparse, datetime, glob, json, os

BIDX = {"良": 0, "稍": 1, "稍重": 1, "重": 2, "不": 3, "不良": 3}


def build_map():
    """(name, YYYYMMDD) -> baba_idx"""
    mp = {}
    # hist / hist2023 / hist_nar : {"race": {...horses[].name}, "date": ...}
    for pat in ("hist/*.json", "hist2023/*.json", "hist_nar/*.json"):
        for f in glob.glob(pat):
            try:
                d = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            r = d.get("race") or {}
            date = d.get("date") or ""
            b = BIDX.get((r.get("baba") or "").strip())
            if not date or b is None:
                continue
            for h in r.get("horses") or []:
                mp[(h.get("name"), date)] = b
    # hist_enrich : {"date","baba","horses":[{"name",...}]}
    for f in glob.glob("hist_enrich/*.json"):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        b = BIDX.get((d.get("baba") or "").strip())
        date = d.get("date") or ""
        if not date or b is None:
            continue
        for h in d.get("horses") or []:
            mp[(h.get("name"), date)] = b
    return mp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--histdir", default="hist")
    a = ap.parse_args()

    mp = build_map()
    print(f"対応表: {len(mp)}走分 (name,date)→baba")

    tot = filled = already = files_w = 0
    for f in sorted(glob.glob(os.path.join(a.histdir, "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        date = d.get("date")
        if not date:
            continue
        base = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
        changed = False
        for h in d.get("race", {}).get("horses", []):
            name = h.get("name")
            for r in h.get("races", []):
                tot += 1
                if r.get("baba_idx") is not None:
                    already += 1
                    continue
                days = r.get("days")
                if not days:
                    continue
                run_date = (base - datetime.timedelta(days=days)).strftime("%Y%m%d")
                b = mp.get((name, run_date))
                if b is None:
                    continue
                r["baba_idx"] = b
                filled += 1
                changed = True
        if changed and not a.dry_run:
            json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False)
            files_w += 1

    print(f"過去走{tot}: 既存{already} 補完{filled} ({filled/max(tot,1)*100:.1f}%) "
          f"残りNone{tot-already-filled}"
          + ("（dry-run）" if a.dry_run else f" / {files_w}ファイル更新"))
    print("※残りNone = 手元DBの窓(2024-07以降のJRA中心)の外で走った過去走。ライブは全走取得できる"
          "ため差は残るが、特徴側はNone→レース内z0で吸収する設計にすること")


if __name__ == "__main__":
    main()
