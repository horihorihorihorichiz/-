#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
レース結果ログ＆成績集計（Ver.99.x モデルのフィードバックループ）

目的: 予想(モデル出力)と実結果を1レース1行で蓄積し、
      的中率・Case別成績・敗因タグを自動集計して「次に直すべき弱点」を可視化する。

使い方:
  python log_result.py stats                 # 集計を表示
  python log_result.py add '<JSON1レコード>'  # 結果を1件追加
  （または add_result(dict) を import して呼ぶ）

レコード例(JSON):
{
  "race":"風待月賞(B2)","date":"2026-06-30","venue":"大井","surface":"ダ","dist":2000,"baba":"重",
  "model":{"axis":8,"S":[8],"top5":[8,5,4,6,2],"case":"Case5","DR":2.84},
  "actual":[11,null,null],          # 1-2-3着の馬番(分かる範囲。不明はnull)
  "popularity":{"axis":2,"win":1},  # 軸の人気 / 勝ち馬の人気(任意)
  "tags":["距離延長逃げ","外枠逃げ"],
  "note":"1人気⑪(2000m未経験/外枠逃げ)を9番手評価で取りこぼし"
}
"""
import json, sys, os
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.jsonl")

def add_result(rec):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("記録:", rec.get("race"), "→ 1着", (rec.get("actual") or [None])[0])

def _load():
    if not os.path.exists(LOG): return []
    out = []
    for line in open(LOG, encoding="utf-8"):
        line = line.strip()
        if line: out.append(json.loads(line))
    return out

def stats():
    rs = _load()
    if not rs:
        print("まだ結果ログがありません。"); return
    n = len(rs)
    win = trio_axis = quinella = show = 0   # 単勝/軸3着内/軸連対/—
    judged = 0
    case_tbl = {}; tag_tbl = {}
    for r in rs:
        m = r.get("model", {}); act = r.get("actual") or []
        first = act[0] if len(act) >= 1 else None
        top3 = [x for x in act[:3] if x is not None]
        axis = m.get("axis")
        case_tbl.setdefault(m.get("case","?"), [0,0])
        if first is not None and axis is not None:
            judged += 1
            case_tbl[m.get("case","?")][1] += 1
            if axis == first:
                win += 1; case_tbl[m.get("case","?")][0] += 1
            if axis in top3: trio_axis += 1
            if len(act) >= 2 and axis in [a for a in act[:2] if a]: quinella += 1
        for t in r.get("tags", []):
            tag_tbl[t] = tag_tbl.get(t, 0) + 1
    print(f"=== 成績集計（{n}レース / 着順判明 {judged}件）===")
    if judged:
        print(f"  軸の単勝的中  : {win}/{judged}  ({100*win/judged:.0f}%)")
        print(f"  軸が3着以内   : {trio_axis}/{judged}  ({100*trio_axis/judged:.0f}%)")
        print(f"  軸が連対(2着内): {quinella}/{judged}  ({100*quinella/judged:.0f}%)")
    print("\n--- Case別（軸単勝的中/判明数）---")
    for c, (h, t) in sorted(case_tbl.items()):
        print(f"  {c:<8} {h}/{t}")
    print("\n--- 敗因/特徴タグ集計（多いほど要注目の弱点）---")
    for t, c in sorted(tag_tbl.items(), key=lambda x: -x[1]):
        print(f"  {c:>2}  {t}")
    print("\n--- 直近メモ ---")
    for r in rs[-5:]:
        a = (r.get("actual") or [None])[0]
        print(f"  [{r.get('date','?')}] {r.get('race','?')} 1着{a} 軸{r.get('model',{}).get('axis')} | {r.get('note','')}")

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "add":
        add_result(json.loads(sys.argv[2])); stats()
    else:
        stats()
