# -*- coding: utf-8 -*-
"""前日に出した並びと、当日のオッズを突き合わせる。

前日: ローカルが keiba/predictions/YYYYMMDD.json に並びを書き出す
当日: これを回すと netkeiba の無料オッズを取り、食い違いの大きいレースを挙げる

  python keiba/tools/oddscheck.py 20260829

出すのは「検討対象のレース」であって買い目ではない。
plus_fires.json が無い以上、買う根拠はまだ存在しない。
"""
import json, sys, os, urllib.request, gzip, time

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://race.netkeiba.com/", "Accept-Encoding": "gzip"}
API = "https://race.netkeiba.com/api/api_get_jra_odds.html?type=1&locale=ja&race_id={}&action=init"

# 食い違いと見なす線。動かすときはここだけ触る
TOP_N      = 3   # 並びの上位何位までを「システムの推し」とするか
COLD_RANK  = 6   # 市場で何番人気より下なら「人気薄」とするか
DOUBT_RANK = 5   # 1番人気が並びの何位より下なら「疑わしい」とするか


def fetch_odds(race_id, retry=3):
    """単勝オッズを {馬番: (オッズ, 人気)} で返す。取れなければ空。"""
    for i in range(retry):
        try:
            req = urllib.request.Request(API.format(race_id), headers=UA)
            raw = urllib.request.urlopen(req, timeout=30).read()
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            d = json.loads(raw.decode("utf-8", "replace"))
            tan = d.get("data", {}).get("odds", {}).get("1", {})
            return {int(k): (float(v[0]), int(v[2])) for k, v in tan.items()
                    if v[0] not in ("", "---.-")}
        except Exception:
            if i == retry - 1:
                return {}
            time.sleep(2 ** i)
    return {}


def check(race, odds):
    """1レース分。食い違いを拾って理由の一覧で返す。"""
    if not odds:
        return None
    hs = sorted(race["horses"], key=lambda h: h["rank"])
    notes = []
    for h in hs[:TOP_N]:
        o = odds.get(h["num"])
        if o and o[1] >= COLD_RANK:
            notes.append({
                "kind": "推しが人気薄",
                "num": h["num"], "name": h["name"],
                "score_rank": h["rank"], "odds": o[0], "pop": o[1],
                "eval": h.get("eval", ""),
            })
    fav = next((n for n, v in odds.items() if v[1] == 1), None)
    if fav is not None:
        fh = next((h for h in hs if h["num"] == fav), None)
        if fh and fh["rank"] >= DOUBT_RANK:
            notes.append({
                "kind": "1番人気が低評価",
                "num": fav, "name": fh["name"],
                "score_rank": fh["rank"], "odds": odds[fav][0], "pop": 1,
                "eval": fh.get("eval", ""),
            })
    return notes or None


def main(date):
    path = os.path.join(os.path.dirname(__file__), "..", "predictions", f"{date}.json")
    if not os.path.exists(path):
        print(f"並びがありません: {path}")
        print("前日にローカル側で書き出してください（keiba/AUTOMATION.md 参照）")
        return 1
    day = json.load(open(path, encoding="utf-8"))

    print(f"# {date} オッズ照合\n")
    print("並びと市場が食い違ったレースだけを挙げます。")
    print("**これは検討対象であって買い目ではありません。**")
    print("買う根拠とされる発火表 plus_fires.json は未作成です。\n")

    hit = 0
    for race in day["races"]:
        odds = fetch_odds(race["race_id"])
        if not odds:
            print(f"- {race['name']}　オッズ取得できず（発走後か未発売）")
            continue
        notes = check(race, odds)
        if not notes:
            continue
        hit += 1
        shape = race.get("shape", "")
        print(f"\n## {race['name']}　{race.get('post','')}　{shape}")
        for n in notes:
            mark = "▲" if n["kind"] == "1番人気が低評価" else "○"
            print(f"{mark} {n['num']:>2}番 {n['name']}　"
                  f"並び{n['score_rank']}位 / {n['odds']}倍({n['pop']}人気)"
                  + (f"　{n['eval']}" if n["eval"] else ""))
        time.sleep(1)

    print(f"\n---\n食い違いのあったレース: {hit} / {len(day['races'])}")
    if hit == 0:
        print("市場と並びが概ね一致しています。見送りが妥当です。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else time.strftime("%Y%m%d")))
