# -*- coding: utf-8 -*-
"""コマンド。

  python -m hk.cli harvest            取得（着順表→追い切り）
  python -m hk.cli fit                学習して配点を書き出す
  python -m hk.cli check              未知期間で1回だけ測る
  python -m hk.cli predict <race_id>  1レース予想する
  python -m hk.cli selftest <race_id> 読み取りが正しいか1レースで確かめる
  python -m hk.cli gbdt [market]      木の学習器で学習して未知期間で測る（推奨）
"""
import sys, json, os
import numpy as np

sys.path.insert(0, os.getcwd())
try:
    import config
except ImportError:
    print("config.py がありません。config.example.py をコピーしてください。")
    sys.exit(1)

from . import harvest, features, fit as F, predict as P, parse, gbdt as G
from .net import Fetcher
from .store import Store

W_PATH = "weights/hori_w.json"


def _store():
    return Store(config.DB_PATH)


def cmd_harvest(args):
    st = _store()
    start = args[0] if args else "20230805"
    end = args[1] if len(args) > 1 else "20991231"
    f1 = Fetcher(config.NETKEIBA_COOKIE, config.RATE_RESULT)
    ids = st.get("ids")
    if not ids:
        print("開催日とレースIDを集めます")
        ids = harvest.scan_ids(f1, start, end)
        st.set("ids", ids); st.commit()
    print(f"レースID {len(ids)}件")
    harvest.results(f1, st, ids)
    f2 = Fetcher(config.NETKEIBA_COOKIE, config.RATE_OIKIRI)
    harvest.training(f2, st, ids, workers=1)
    print("完了")


USE_MARKET = False


def _dataset(st, until=None):
    races = st.all_races()
    book = features.Book(races, config.CUT_HIST)
    oik = st.all_oikiri()
    if oik:
        print(f"  追い切り {len(oik)}レース分を使います（調教3成分を足します）")
    else:
        print("  追い切りが未取得なので、調教3成分は作りません")
    b = features.WideBuilder(book, oikiri=oik, market=USE_MARKET)
    DS = []
    for ri, r in enumerate(book.races):
        if r["date"] >= config.CUT_HIST:
            d = b.build_wide(ri)
            d["Z"] = np.array(d["Z"], dtype=np.float32)
            if 1 in d["ord"]:
                d["top"] = [d["ord"].index(x) for x in (1, 2, 3) if x in d["ord"]]
                DS.append(d)
        b.advance(r)
    return DS, b.wide_names


def cmd_fit(args):
    st = _store()
    print("成分を作ります")
    DS, names = _dataset(st)
    TR = [d for d in DS if d["date"] < config.CUT_EMBARGO]
    print(f"学習 {len(TR)}R / 成分 {len(names)}個")
    lv, tab = F.choose_level(TR, names)
    m = F.Model().fit(TR, names)
    cal = P.build_calibration(TR, m, level=lv)
    os.makedirs("weights", exist_ok=True)
    out = {"names": names, "G": list(map(float, m.G)),
           "L1": {k: list(map(float, v)) for k, v in m.L1.items()},
           "A": {k: list(map(float, v)) for k, v in m.A.items()},
           "B": {k: list(map(float, v)) for k, v in m.B.items()},
           "C": {k: list(map(float, v)) for k, v in m.C.items()},
           "rep": {k: v for k, v in m.rep.items()},
           "n": {k: v for k, v in m.n.items()},
           "K": {k: [None if np.isinf(x) else float(x) for x in v] for k, v in m.K.items()},
           "calib": cal, "level": lv, "inner": tab}
    json.dump(out, open(W_PATH, "w"), ensure_ascii=False, indent=1)
    print(f"書き出しました → {W_PATH}")
    _print_table(m)


def _print_table(m):
    def norm(w):
        w = np.asarray(w, float)
        s = np.abs(w).mean() or 1.0
        return np.round(w / s * 30, 1)
    cells = ["芝S", "芝M", "芝L", "ダS", "ダM", "ダL"]
    print("\n実効配点（平均絶対値=30に正規化）")
    print("成分".ljust(10) + "全体".rjust(8) + "".join(c.rjust(8) for c in cells))
    g = norm(m.G)
    ws = {c: norm(m.L1[c]) for c in cells if c in m.L1}
    for j, nm in enumerate(m.names):
        print(nm.ljust(10) + f"{g[j]:8.1f}" +
              "".join(f"{ws[c][j]:8.1f}" if c in ws else "       -" for c in cells))


def cmd_gbdt(args):
    """木の学習器で学習し、未知期間で1回だけ測る。"""
    global USE_MARKET
    USE_MARKET = "market" in args
    st = _store()
    DS, names = _dataset(st)
    TR = [d for d in DS if d["date"] < config.CUT_EMBARGO]
    V = [d for d in DS if d["date"] >= config.CUT_VAL]
    print(f"学習 {len(TR)}R / 未知 {len(V)}R / 成分 {len(names)}個"
          + ("（市場込み）" if USE_MARKET else "（市場なし）"))
    if not G.HAVE_LGB:
        print("lightgbm が入っていません:  pip install lightgbm"); return
    m, best = G.fit(TR, names)
    r, per = G.evaluate(V, m)
    print("\n木の学習器 / 未知期間")
    print("  " + "  ".join(f"{k}={v}" for k, v in r.items() if k != "n"))
    # 線形との比較
    lin_names = names[:26] if len(names) >= 26 else names
    DSl = [{**d, "Z": [row[:len(lin_names)] for row in d["Z"]]} for d in DS]
    TRl = [d for d in DSl if d["date"] < config.CUT_EMBARGO]
    Vl = [d for d in DSl if d["date"] >= config.CUT_VAL]
    ml = F.Model().fit(TRl, lin_names, verbose=False)
    rl, perl = F.evaluate(Vl, ml, "L1")
    print("\n線形（比較用）/ 未知期間")
    print("  " + "  ".join(f"{k}={v}" for k, v in rl.items() if k != "n"))
    print("\n木 − 線形（対応のある検定・t>3.0で採用）")
    for i, lab in enumerate(["1位が1着", "1位が3着内", "上位6頭で3着独占"]):
        d = F.mcnemar(per, perl, i)
        print(f"  {lab:16s} {d['差pt']:+.2f}pt (SE {d['SE']}, t={d['t']})")
    m.save_model("weights/hori_gbdt.txt")
    import json as _j
    _j.dump({"names": list(names), "rounds": best, "market": USE_MARKET},
            open("weights/hori_gbdt_meta.json", "w"), ensure_ascii=False, indent=1)
    print("\n書き出しました → weights/hori_gbdt.txt")


def cmd_check(args):
    st = _store()
    DS, names = _dataset(st)
    TR = [d for d in DS if d["date"] < config.CUT_EMBARGO]
    V = [d for d in DS if d["date"] >= config.CUT_VAL]
    print(f"学習 {len(TR)}R / 未知 {len(V)}R / 成分 {len(names)}個")
    chosen, _tab = F.choose_level(TR, names)
    m = F.Model().fit(TR, names)
    rows = {}
    per = {}
    for lv, nm in [("G", "全体1本"), ("L1", "6群"), ("mid", "場+クラス"), ("C", "コース単位")]:
        rows[nm], per[nm] = F.evaluate(V, m, lv)
    print(f"\n内側検証が選んだ段階: {chosen}")
    print("\n未知期間での成績")
    for nm, r in rows.items():
        print(f"  {nm:10s} " + "  ".join(f"{k}={v}" for k, v in r.items() if k != "n"))
    print("\n全体1本との差（対応のある検定・t>3.0で採用）")
    for nm in list(rows)[1:]:
        for i, lab in enumerate(["1位が1着", "1位が3着内", "上位6頭で3着独占"]):
            d = F.mcnemar(per[nm], per["全体1本"], i)
            print(f"  {nm:10s} {lab:16s} {d['差pt']:+.2f}pt (SE {d['SE']}, t={d['t']})")


def cmd_predict(args):
    if not args:
        print("race_id を指定してください"); return
    st = _store()
    w = json.load(open(W_PATH))
    m = F.Model()
    m.names = w["names"]; m.G = np.array(w["G"])
    m.L1 = {k: np.array(v) for k, v in w["L1"].items()}
    m.A = {k: np.array(v) for k, v in w["A"].items()}
    m.B = {k: np.array(v) for k, v in w["B"].items()}
    m.C = {k: np.array(v) for k, v in w["C"].items()}
    m.n = w["n"]; m.rep = w["rep"]
    races = st.all_races()
    book = features.Book(races, config.CUT_HIST)
    b = features.Builder(book, oikiri=st.all_oikiri())
    target = None
    for ri, r in enumerate(book.races):
        if r["id"] == args[0]:
            target = ri
            break
        b.advance(r)
    if target is None:
        print("そのレースが保管庫にありません。先に harvest してください。"); return
    feat = b.build(target)
    pr = P.Predictor(m, w["names"], w.get("calib"))
    print(P.render(pr.run(feat, level=w.get("level", "L1"))))


def cmd_selftest(args):
    """1レースだけ取ってきて、読み取り結果をそのまま見せる。
       netkeiba の画面と見比べて、列がずれていないか確かめるためのもの。"""
    rid = args[0] if args else "202605020811"
    f = Fetcher(config.NETKEIBA_COOKIE, config.RATE_RESULT)
    t = f.get(f"https://db.netkeiba.com/race/{rid}/")
    if not t:
        print("取得できませんでした。config.py のクッキーを確認してください。"); return
    r = parse.race(rid, t)
    if not r:
        print("読み取れませんでした。netkeiba 側の作りが変わった可能性があります。"); return
    print(f'{r["id"]} {r["date"]} {r["place"]} {r["surf"]}{r["turn"]}{r["dist"]}m '
          f'{r["ground"]} {r["cls"]} {r["n"]}頭')
    print("着 枠 馬番 騎手   タイム  着差    指数 通過      上り  単勝 人気 馬体重")
    for h, ti in list(zip(r["rows"], r["tidx"]))[:5]:
        print(f'{h["fin"]:>2} {h["waku"]:>2} {h["umaban"]:>3} {h["jockey"]:>6} '
              f'{h["sec"]:>6.1f} {h["margin"]:>6} {ti:>6} {h["corner"]:>9} '
              f'{h["agari"]:>5} {h["odds"]:>5} {h["pop"]:>3} {h["bw"]:>5}({h["bwd"]:+d})')
    miss = sum(1 for x in r["tidx"] if not x)
    print(f'タイム指数が空の頭数: {miss}/{r["n"]}'
          + ("（直近3週間ほどのレースは未算出。それより古ければ列ずれの疑い）" if miss else ""))
    t2 = f.get(f"https://race.netkeiba.com/race/oikiri.html?race_id={rid}&type=2",
               encoding="utf-8")
    o = parse.oikiri(t2) if t2 else None
    if not o:
        print("追い切りは取得できませんでした（アクセス制限中か、そのレースに調教情報が無い）。")
        return
    print("\n追い切り")
    print("馬番 日付      コース 馬場 乗り役 本数 追い方 評価       脚 ラップ")
    for x in o[:5]:
        laps = " ".join(f"{a}" for a, _ in x["laps"])
        print(f'{x["umaban"]:>3} {x["date"]:>9} {x["course"]:>5} {x["ground"]:>3} '
              f'{x["rider"]:>5} {x["hon"]:>3} {x["way"]:>5} {x["eval"]:>8} {x["leg"]:>2} {laps}')


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    {"harvest": cmd_harvest, "fit": cmd_fit, "check": cmd_check,
     "predict": cmd_predict, "selftest": cmd_selftest, "gbdt": cmd_gbdt}.get(sys.argv[1], lambda a: print(__doc__))(sys.argv[2:])


if __name__ == "__main__":
    main()
