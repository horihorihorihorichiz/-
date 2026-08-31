# -*- coding: utf-8 -*-
"""凍結セルの独立検証: 採掘に使っていないレースだけで測る（2026-08-21深夜 仕込み）。

対象データ = 台帳のうち mine200_baseline_rids.json（採掘時の8,002R）に**無い**レース。
収穫中の2022/2023の埋め戻しがここに入る。これらは採掘のどの判断にも使われていないので、
凍結12セル（mine200_watch.json）と的中率スター2セルにとって独立データになる。

注意（正直に書く）: モデルの重み(B-sd16)は2023H2以降で学習したものを2022/2023H1に
当てるため、レース時点より未来の重みを使う形になる。セル選択とは独立だが、
モデル成績そのものの評価には使えない。ここで見るのは「セルの条件×券種のROI」のみ。

usage: python3 mine200_check_new.py   (build_comps_v99.py → build_bsd16_ds.py の後に実行)
"""
import json, os, sys, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mine200 as M0
import mine200f as MF


def main():
    base = set(json.load(open("mine200_baseline_rids.json")))
    races = [r for r in M0.load() if r["rid"] not in base]
    print(f"独立レース（採掘8,002Rに無い行）: {len(races)}R")
    if not races:
        print("新しいレースがまだ台帳に入っていない。build_comps_v99.py → build_bsd16_ds.py を先に。")
        return
    mons = sorted({r["month"] for r in races})
    print(f"期間: {mons[0]}〜{mons[-1]}")

    # meta（馬場/距離/場）を hist から。キャッシュに無い分を追加
    meta = {}
    if os.path.exists(MF.META):
        meta = json.load(open(MF.META))
    add = 0
    for r in races:
        if r["rid"] in meta:
            continue
        try:
            d = json.load(open(f"hist/{r['rid']}.json", encoding="utf-8"))["race"]
            meta[r["rid"]] = {"baba": d.get("baba"), "distance": d.get("distance"),
                              "venue": d.get("venue")}
            add += 1
        except Exception:
            meta[r["rid"]] = {}
    if add:
        json.dump(meta, open(MF.META, "w"), ensure_ascii=False)

    consts = MF.make_conditions(races, meta)
    orders = {r["rid"]: r["rank16"] for r in races}
    ret, vals, segm = MF.build(races, consts, orders)

    def eval_cell(val_names, bet_name):
        bi = M0.BETS.index(bet_name)
        c = M0.COSTS[bi] / 100.0
        m = np.ones(len(races), dtype=bool)
        for v in val_names:
            key = next((k for k in vals if k[1] == v), None)
            if key is None:
                return None            # この値の条件に該当レースが1つも無い
            m &= vals[key]
        n = int(m.sum())
        if n == 0:
            return dict(n=0)
        return dict(n=n, roi=float(ret[m, bi].sum() / n / c),
                    hit=float((ret[m, bi] > 0).mean() * 100),
                    pl=float(ret[m, bi].sum() - n * M0.COSTS[bi]))

    watch = json.load(open("mine200_watch.json"))
    print("\n═ 凍結12セル（ROI200採掘の生き残り）の独立成績 ═")
    print(f"{'条件':<40}{'券種':<10}{'n':>5}{'的中':>7}{'ROI':>8}{'収支':>10}")
    agg_n = agg_ret = agg_cost = 0
    for cell in watch["cells"]:
        names = cell["cell"].split("×") if isinstance(cell["cell"], str) else cell["cell"]
        if isinstance(names, list) and len(names) == 1:
            names = names[0].split("×")
        e = eval_cell(names, cell["bet"])
        bi = M0.BETS.index(cell["bet"])
        if e is None or e["n"] == 0:
            print(f"{'×'.join(names):<40}{cell['bet']:<10}{'0':>5}{'—':>7}{'—':>8}{'—':>10}")
            continue
        agg_n += e["n"]; agg_ret += e["pl"] + e["n"] * M0.COSTS[bi]; agg_cost += e["n"] * M0.COSTS[bi]
        print(f"{'×'.join(names):<40}{cell['bet']:<10}{e['n']:>5}{e['hit']:>6.1f}%"
              f"{e['roi']:>7.1f}%{e['pl']:>+9.0f}円")
    if agg_cost:
        print(f"{'【12セル合算】':<50}{agg_n:>5}{'':>7}{agg_ret/agg_cost*100:>7.1f}%"
              f"{agg_ret-agg_cost:>+9.0f}円")

    print("\n═ 的中率スターセル（3期再現済み）の独立成績 ═")
    for names, bet in ((["≤8頭", "1位<2倍"], "軸1位流し26"),
                       (["≤8頭", "1位2-3倍"], "BOX5三連複"),
                       (["≤8頭", "1位<2倍"], "BOX5三連複")):
        e = eval_cell(names, bet)
        if e and e["n"]:
            print(f"  {'×'.join(names):<24}{bet:<12} n={e['n']:<5} 的中{e['hit']:5.1f}%  "
                  f"ROI{e['roi']:6.1f}%  {e['pl']:+.0f}円")
        else:
            print(f"  {'×'.join(names):<24}{bet:<12} 該当なし")

    json.dump({"n_new": len(races), "months": [mons[0], mons[-1]]},
              open("mine200_check_new_last.json", "w"))


if __name__ == "__main__":
    main()
