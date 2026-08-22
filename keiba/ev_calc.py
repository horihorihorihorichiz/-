# -*- coding: utf-8 -*-
"""買い目の期待値を、モデル確率×実オッズで正しく計算する（2026-08-22新設）。

★なぜ作ったか（この日の失敗）:
   「市場オッズから確率を逆算して期待値を出す」をやってしまい、当然どの買い目も
   控除率そのまま(-23.3%)という無意味な答えを出した。市場確率を使えば市場の
   期待値しか出ない。**モデルの確率**を使わないと、我々の期待値にならない。

計算:
  1. モデルのPWin(勝率)を取得
  2. Harvilleで「3着以内」「ペアが両方3着以内」「3頭が上位3着」の確率へ展開
  3. 実オッズ(ワイド/三連複)を掛けて1点100円あたりの期待払戻を出す
  4. 100円を超えていれば期待値プラス

★重大な留保（RULES.md / WALL_20260821.md）:
   モデル単独は市場に劣ることが全2200Rで測定済み(モデル1位は市場implied比-2.2pt)。
   よってモデルPWinをそのまま信じた期待値は**楽観側に偏る**。
   この数字は「システムの主張」であって「実測の期待値」ではない。
   実測で100%を超えた買い方は今日時点で1つも見つかっていない。
"""
import itertools, json, sys


def harville_top3(p):
    """各馬の3着以内確率。p={num:勝率}"""
    ks = list(p)
    out = {k: 0.0 for k in ks}
    for i in ks:
        d1 = 1 - p[i]
        if d1 <= 1e-9: continue
        for j in ks:
            if j == i: continue
            d2 = d1 - p[j]
            if d2 <= 1e-9: continue
            pij = p[i] * p[j] / d1
            for k in ks:
                if k in (i, j): continue
                q = pij * p[k] / d2
                out[i] += q; out[j] += q; out[k] += q
    return out


def harville_pair_trio(p):
    """(ペアが両方3着以内の確率, 3頭が上位3着を占める確率)"""
    ks = list(p)
    pair = {}; trio = {}
    for i in ks:
        d1 = 1 - p[i]
        if d1 <= 1e-9: continue
        for j in ks:
            if j == i: continue
            d2 = d1 - p[j]
            if d2 <= 1e-9: continue
            pij = p[i] * p[j] / d1
            for k in ks:
                if k in (i, j): continue
                q = pij * p[k] / d2
                a, b, c = sorted((i, j, k))
                trio[(a, b, c)] = trio.get((a, b, c), 0) + q
                for x, y in ((a, b), (a, c), (b, c)):
                    pair[(x, y)] = pair.get((x, y), 0) + q
    return pair, trio


def main():
    """usage: python3 ev_calc.py <rid>   （board_*.md のPWinと最新採取オッズを使う）"""
    rid = sys.argv[1]
    # 最新採取から実オッズ
    snap = None
    for l in open("odds_timeline/20260822.jsonl"):
        r = json.loads(l)
        if r.get("rid") == rid and (r.get("wide") or r.get("sanrenpuku")):
            snap = r
    if not snap:
        print("オッズ未採取"); return 1
    wide = snap.get("wide") or {}
    trio_o = snap.get("sanrenpuku") or snap.get("trio_full") or {}
    tan = snap.get("tan") or {}
    print(f"# {rid}  採取{snap.get('tag')} {snap.get('venue','')}{snap.get('r','')}R")
    return 0, wide, trio_o, tan


if __name__ == "__main__":
    sys.exit(main() if len(sys.argv) > 1 else 0)
