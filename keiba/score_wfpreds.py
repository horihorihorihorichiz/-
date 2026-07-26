# -*- coding: utf-8 -*-
"""既存の wf_preds*.jsonl を wf_compare.Acc と同じ物差しで採点する。
   V3(オリジナル: today_vg=2固定の学習データ) と V4 を同じ4ゲートで並べるため。
   usage: python3 score_wfpreds.py wf_preds.jsonl [wf_preds_v4.jsonl ...]"""
import json, sys

from wf_compare import Acc


def rows(path):
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        pay = d.get("payout") or {}
        tan = pay.get("単勝") or {}
        if not tan:
            continue
        win = int(list(tan.keys())[0])
        place = [int(k) for k in (pay.get("複勝") or {})]
        top3 = [win] + [n for n in place if n != win]
        if len(top3) < 3:
            continue
        order = [int(x) for x in d["order"]]
        sc = d.get("scores")
        if isinstance(sc, dict):
            s = {int(k): float(v) for k, v in sc.items()}
        else:   # wf_compare の dump 形式: order と同順の配列
            s = {n: float(v) for n, v in zip(order, sc)}
        r = dict(ns=order, top3=top3[:3], rid=d["rid"],
                 odds={int(k): float(v) for k, v in (d.get("odds") or {}).items()},
                 tier=d.get("tier"), surface=d.get("surface"), baba=d.get("baba"))
        yield r, s


def main():
    for path in sys.argv[1:]:
        a = Acc()
        for r, s in rows(path):
            a.add(r, s)
        a.report(path)


if __name__ == "__main__":
    main()
