# -*- coding: utf-8 -*-
"""**オッズを一切使わずに**買える条件を探す（ユーザー要求「人気で判断するのはやめる」）。

   選定に使ってよいのは、発走前にオッズ抜きで分かるものだけ:
     馬場 / 芝ダ / 距離 / 頭数 / クラス(tier) / 場 / 開催日目 / コース特性VG /
     モデル得点差(g12=1位-2位, spread15=1位-5位) / モデル1位の枠番
   券種は「モデルの並び」だけで決める: 単勝1位 / 複勝1位 / 馬連1-2位 / ワイド1-2位 / 三連複1-2-3位。

   検証はRULES.mdの dev/conf 分割（dev=月≤202603, conf=月≥202604）。
   合格 = dev≥110% ∧ conf≥100% ∧ n≥40 ∧ 的中≥5 ∧ 最大配当を除いてもROI≥95%。

   usage: python3 oddsfree_mine.py wf_preds_v4bin.jsonl [--min-n 40]
"""
import argparse, itertools, json
from collections import defaultdict

import course

DEV_MAX = "202603"

JRA_CODE = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
            "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}


def key_of(nums):
    return "-".join(str(x) for x in sorted(nums))


def load(path):
    out = []
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        pay = d.get("payout") or {}
        if not pay.get("単勝"):
            continue
        order = [int(x) for x in d["order"]]
        if len(order) < 5:
            continue
        sc = d["scores"]
        sc = [float(x) for x in (sc if isinstance(sc, list) else
                                 [sc[str(n)] for n in order])]
        rid = d["rid"]
        venue = d.get("venue") or JRA_CODE.get(rid[4:6], "")
        field = int(d.get("field") or len(order))
        surface, dist = d.get("surface"), int(d.get("dist") or 0)
        out.append(dict(
            month=d.get("month") or rid[:6], rid=rid, order=order, pay=pay,
            surface=surface, dist=dist, tier=d.get("tier"),
            baba=(d.get("baba") or "").strip(), venue=venue, field=field,
            day=int(rid[8:10]) if len(rid) >= 10 else 0,
            vg=course.course_vg(venue, surface, dist) if venue else 3,
            g12=sc[0]-sc[1], spread15=sc[0]-sc[4],
            waku1=course.jra_waku(order[0], field),
        ))
    return out


# ── 券種: モデルの並びだけで決まる買い方 ───────────────────────────────
def bets(r):
    o, pay = r["order"], r["pay"]
    yield "単勝1位", 100, float((pay.get("単勝") or {}).get(str(o[0]), 0))
    yield "複勝1位", 100, float((pay.get("複勝") or {}).get(str(o[0]), 0))
    yield "馬連1-2位", 100, float((pay.get("馬連") or {}).get(key_of(o[:2]), 0))
    yield "ワイド1-2位", 100, float((pay.get("ワイド") or {}).get(key_of(o[:2]), 0))
    yield "三連複1-2-3位", 100, float((pay.get("三連複") or {}).get(key_of(o[:3]), 0))


# ── オッズ不使用の条件 ────────────────────────────────────────────────
def conds(r):
    c = {}
    c[f"馬場={r['baba'] or '?'}"] = True
    c["馬場=道悪(稍重不)"] = r["baba"] in ("稍", "重", "不")
    c[f"面={r['surface']}"] = True
    d = r["dist"]
    c["距離=短1000-1300"] = 1000 <= d <= 1300
    c["距離=中1301-1900"] = 1301 <= d <= 1900
    c["距離=長1901+"] = d >= 1901
    t = r["tier"]
    if t is not None:
        c["クラス=未勝利新馬(t10+)"] = t >= 10
        c["クラス=1勝(t6-9)"] = 6 <= t <= 9
        c["クラス=2勝以上(t<=5)"] = t <= 5
    f = r["field"]
    c["頭数=10以下"] = f <= 10
    c["頭数=11-14"] = 11 <= f <= 14
    c["頭数=15-17"] = 15 <= f <= 17
    c["頭数=18"] = f >= 18
    c["場=メイン4場"] = r["venue"] in ("東京", "中山", "京都", "阪神")
    c["開催=初日"] = r["day"] == 1
    c["開催=2日目以降"] = r["day"] >= 2
    c[f"VG={r['vg']}"] = True
    for th in (0.3, 0.6, 1.0, 1.5):
        c[f"g12>={th}"] = r["g12"] >= th
    c["g12<0.3(混戦)"] = r["g12"] < 0.3
    for th in (2.0, 3.0, 4.0):
        c[f"spread15>={th}"] = r["spread15"] >= th
    c["1位枠=内(1-3)"] = 1 <= r["waku1"] <= 3
    c["1位枠=中(4-6)"] = 4 <= r["waku1"] <= 6
    c["1位枠=外(7-8)"] = r["waku1"] >= 7
    return {k for k, v in c.items() if v}


class Cell:
    __slots__ = ("s", "r", "hits", "n", "mx", "ds", "dr", "cs", "cr")

    def __init__(self):
        self.s = self.r = self.ds = self.dr = self.cs = self.cr = 0.0
        self.hits = self.n = 0
        self.mx = 0.0

    def add(self, stake, ret, dev):
        self.s += stake; self.r += ret; self.n += 1
        self.hits += ret > 0
        self.mx = max(self.mx, ret)
        if dev:
            self.ds += stake; self.dr += ret
        else:
            self.cs += stake; self.cr += ret

    @property
    def roi(self): return self.r/self.s*100 if self.s else 0.0
    @property
    def dev(self): return self.dr/self.ds*100 if self.ds else 0.0
    @property
    def conf(self): return self.cr/self.cs*100 if self.cs else 0.0
    @property
    def excl(self):
        return (self.r-self.mx)/(self.s-100)*100 if self.s > 100 else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--min-n", type=int, default=40)
    ap.add_argument("--pairs", action="store_true", default=True)
    ap.add_argument("--show", default="", help="この条件(部分一致)のセルを合否に関わらず全部出す")
    a = ap.parse_args()

    rows = load(a.path)
    print(f"{len(rows)}R 読み込み（{a.path}）")

    cells = defaultdict(Cell)
    for r in rows:
        dev = r["month"] <= DEV_MAX
        cs = sorted(conds(r))
        for bt, stake, ret in bets(r):
            cells[(bt, "全体")].add(stake, ret, dev)
            for c in cs:
                cells[(bt, c)].add(stake, ret, dev)
            if a.pairs:
                for c1, c2 in itertools.combinations(cs, 2):
                    cells[(bt, f"{c1} × {c2}")].add(stake, ret, dev)

    print("\n── 全体（条件なし・モデルの並びだけで機械的に買った場合） ──")
    for bt in ("単勝1位", "複勝1位", "馬連1-2位", "ワイド1-2位", "三連複1-2-3位"):
        c = cells[(bt, "全体")]
        print(f"  {bt:14s} ROI {c.roi:6.1f}%  ({c.n}点 / 的中{c.hits})")

    ok = []
    for (bt, cond), c in cells.items():
        if cond == "全体" or c.n < a.min_n or c.hits < 5:
            continue
        if c.dev >= 110 and c.conf >= 100 and c.excl >= 95:
            ok.append((c.roi, bt, cond, c))
    ok.sort(reverse=True, key=lambda x: x[0])

    print(f"\n── 合格条件（dev≥110 ∧ conf≥100 ∧ n≥{a.min_n} ∧ 的中≥5 ∧ 最大除外≥95） ──")
    if not ok:
        print("  該当なし。オッズ抜きで市場を出し抜ける切り口は見つからなかった。")
    for roi, bt, cond, c in ok[:40]:
        print(f"  {roi:6.1f}%  {bt:12s} {cond:52s} "
              f"n={c.n:4d} 的中{c.hits:3d} dev{c.dev:6.1f}/conf{c.conf:6.1f} 除外{c.excl:6.1f}")
    print(f"\n  合格 {len(ok)}件 / 検査 {len(cells)}セル")

    if a.show:
        print(f"\n── 「{a.show}」を含むセル（合否問わず・n>={a.min_n}） ──")
        rowsf = [(c.roi, bt, cond, c) for (bt, cond), c in cells.items()
                 if a.show in cond and c.n >= a.min_n]
        for roi, bt, cond, c in sorted(rowsf, reverse=True, key=lambda x: x[0])[:30]:
            print(f"  {roi:6.1f}%  {bt:12s} {cond:52s} "
                  f"n={c.n:4d} 的中{c.hits:3d} dev{c.dev:6.1f}/conf{c.conf:6.1f} 除外{c.excl:6.1f}")


if __name__ == "__main__":
    main()
