# -*- coding: utf-8 -*-
"""発走10分前に、合成1位のオッズが基準を越えていたら LINE に通知する。

仕組み:
  木の順位は動かないので、予想を作った時点で確定させておく（alerts JSON）。
  市場の順位はオッズで動くので、**発走10分前に生オッズだけ取り直して**
  合成し直す。そのうえで合成1位の単勝オッズを見て、基準以上なら送る。

  予想を作る    python predict_boost.py <cards> --date YYYYMMDD --alerts ../../data/alerts_YYYYMMDD.json
  通知を回す    python notify.py ../../data/alerts_20260830.json
  試し送信      python notify.py ../../data/alerts_20260830.json --test
  送らず確認    python notify.py ../../data/alerts_20260830.json --dry

朝に起動して置いておくと、最終レースまで居座って各レースの10分前に判定する。
Windows なら「タスク スケジューラ」で開催日の朝に起動させるのが楽。

LINE Notify は 2025年3月31日で終了しているため使えない。Messaging API の
push を使う。トークンは config.py に置くこと（.gitignore 済み）。
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta

import requests

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

LEAD_MIN = 10          # 発走の何分前に判定するか
ODDS_MIN = 5.0         # 合成1位の単勝がこの倍率以上なら通知
HOLE_MIN = 5.0         # 「穴軸」とみなす単勝の下限

# 穴を軸にした形の、探索窓1,826Rでの実測回収率。文面に必ず添える。
# 数字を隠して買い目だけ送ると、ただの当たりそうな話になってしまう。
MEASURED = {
    "ワイド 穴軸→合成上位": 80.4,   # restructure.py: 人気で相手を選ぶと85.2%
    "複勝 合成1位(4番人気以下)": 72.3,  # patterns.py B2
    "複勝 合成1位(6番人気以下)": 43.9,  # patterns.py B3
}
API = "https://race.netkeiba.com/api/api_get_jra_odds.html?type=1&locale=ja&race_id={}"
PUSH = "https://api.line.me/v2/bot/message/push"


def live_odds(rid, session):
    """{馬番: (単勝オッズ, 人気)}。取れなければ空。"""
    try:
        r = session.get(API.format(rid), timeout=15)
        j = r.json()
        o = (j.get("data") or {}).get("odds", {}).get("1")
        if not o:
            return {}
        out = {}
        for k, v in o.items():
            try:
                od, pp = float(v[0]), int(v[2])
            except (ValueError, TypeError, IndexError):
                continue
            if od <= 0 or od >= 999:
                continue          # 999.9 は「まだ出ていない」の意味で入っている
            out[int(k)] = (od, pp)
        return out if reliable(out) else {}
    except Exception:
        return {}


def reliable(odds):
    """オッズが本開通しているかを、内部の辻褄で見る。

    発売前は 999.9 と仮の人気が混ざって入っていることがある。そのまま使うと
    「999.9倍なのに4番人気」のような馬が合成1位になり、誤って通知してしまう。
    いちばん安い馬が1番人気になっていなければ、まだ信用しない。
    """
    if len(odds) < 5:
        return False
    cheapest = min(odds.items(), key=lambda kv: kv[1][0])
    return cheapest[1][1] == 1


def order_by_blend(race, odds):
    """合成順位の昇順で全馬を返す。各馬に odds / pop / _b（合成順位）を入れる。"""
    hs = [dict(h) for h in race["horses"] if h["umaban"] in odds]
    hs.sort(key=lambda h: odds[h["umaban"]][0])
    for i, h in enumerate(hs):
        h["odds"], h["pop"] = odds[h["umaban"]]
        h["_m"] = i                       # 市場順位（0始まり）
    for h in hs:
        h["_b"] = (h["trank"] - 1) + h["_m"]
    return sorted(hs, key=lambda h: (h["_b"], h["trank"]))


def blend_top(race, odds):
    """合成1位。同点は木の順位で割る（predict_boost.py と同じ決め方）。

    合成は「木の順位 + 市場の順位」なので上位が同点になりやすい。
    新潟記念のように上位3頭が全部同点、ということが普通に起きる。
    そこで割り方を揃えておかないと、ボードと通知で1位が食い違う。
    """
    ranked = order_by_blend(race, odds)
    if len(ranked) < 5:
        return None
    best = ranked[0]
    return {**best, "blend": best["_b"]}


def send_line(text, dry=False):
    tok = getattr(config, "LINE_TOKEN", "")
    to = getattr(config, "LINE_TO", "")
    if dry:
        print("--- 送信内容（dry） ---\n" + text + "\n-----------------------")
        return True
    if not tok or not to:
        print("config.py の LINE_TOKEN / LINE_TO が空。送信をとばした。")
        print("--- 送るはずだった内容 ---\n" + text)
        return False
    r = requests.post(PUSH, timeout=15,
                      headers={"Authorization": f"Bearer {tok}",
                               "Content-Type": "application/json"},
                      json={"to": to, "messages": [{"type": "text", "text": text[:4900]}]})
    if r.status_code != 200:
        print(f"LINE 送信に失敗 {r.status_code}: {r.text[:200]}")
        return False
    return True


def suggest(race, odds):
    """穴を軸にした形。軸は合成順位がいちばん上の HOLE_MIN 倍以上の馬。"""
    ranked = order_by_blend(race, odds)
    if len(ranked) < 4:
        return None
    hole = next((h for h in ranked if h["odds"] >= HOLE_MIN), None)
    if hole is None:
        return None
    aite = [h for h in ranked[:4] if h["umaban"] != hole["umaban"]][:2]
    if len(aite) < 2:
        return None
    return {"hole": hole, "aite": aite, "rank": ranked.index(hole) + 1}


def message(race, top, sug=None):
    ev = f"／追い切り {top['evalWord']}" if top.get("evalWord") else ""
    t = (f"🐎 {race['place']}{race['r']}R {race['post']}発走"
         f"（あと{LEAD_MIN}分）\n"
         f"{race['title'] or ''} {race['surf']}{race['dist']}m {race['n']}頭\n"
         f"\n合成1位　{top['umaban']} {top['name']}\n"
         f"単勝 {top['odds']:.1f}倍（{top['pop']}番人気）／木の順位 {top['trank']}位{ev}")
    if sug:
        h, a = sug["hole"], sug["aite"]
        t += ("\n\n── 穴軸の形 ──\n"
              f"軸 {h['umaban']} {h['name']}"
              f"（{h['odds']:.1f}倍・{h['pop']}番人気・合成{sug['rank']}位・木{h['trank']}位）\n"
              "相手 " + " / ".join(
                  f"{x['umaban']} {x['name']}（{x['odds']:.1f}倍）" for x in a) +
              "\nワイド2点\n"
              f"\n実測 {MEASURED['ワイド 穴軸→合成上位']:.1f}%"
              "（相手を人気順で選ぶと85.2%なので、穴軸にするぶん負けが増える形）")
    t += ("\n\n※これは並びであって買い目の推奨ではない。"
          f"1位が{ODDS_MIN:.0f}倍以上という条件も、穴軸の形も、"
          "探索窓の実測は100%を大きく割る。負ける形と分かったうえで買うこと。")
    return t


def main():
    path = sys.argv[1]
    dry = "--dry" in sys.argv
    plan = json.load(open(path, encoding="utf-8"))
    s = requests.Session()
    s.headers["User-Agent"] = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 Chrome/144.0 Safari/537.36")

    if "--test" in sys.argv:
        r = plan["races"][0]
        od = live_odds(r["id"], s)
        t = blend_top(r, od) if od else None
        if not t:
            print("オッズがまだ出ていないので、見本の文面で送る")
            t = {**r["horses"][0], "odds": 7.7, "pop": 6, "blend": 0}
        send_line("【試し送信】\n" + message(r, t), dry)
        return

    todo = []
    for r in plan["races"]:
        hh, mm = r["post"].split(":")
        when = datetime.strptime(plan["date"], "%Y%m%d").replace(
            hour=int(hh), minute=int(mm)) - timedelta(minutes=LEAD_MIN)
        todo.append((when, r))
    todo.sort(key=lambda x: x[0])
    now = datetime.now()
    skipped = [r["post"] for w, r in todo if w <= now]
    if skipped:
        print(f"判定時刻を過ぎているレース {len(skipped)}件はとばす（{skipped[0]}〜{skipped[-1]}）")
    todo = [(w, r) for w, r in todo if w > now]
    if not todo:
        print("これから判定するレースが無い。")
        return
    print(f"{len(todo)}レースを見張る。最初は {todo[0][0]:%H:%M}"
          f"（{todo[0][1]['place']}{todo[0][1]['r']}R の{LEAD_MIN}分前）")
    print(f"条件: 合成1位の単勝が {ODDS_MIN} 倍以上", flush=True)

    for when, r in todo:
        wait = (when - datetime.now()).total_seconds()
        while wait > 0:
            time.sleep(min(wait, 30))
            wait = (when - datetime.now()).total_seconds()
        od = live_odds(r["id"], s)
        if not od:
            print(f"{datetime.now():%H:%M} {r['place']}{r['r']}R オッズが取れない。とばす", flush=True)
            continue
        top = blend_top(r, od)
        if not top:
            print(f"{datetime.now():%H:%M} {r['place']}{r['r']}R 合成できない。とばす", flush=True)
            continue
        hit = top["odds"] >= ODDS_MIN
        print(f"{datetime.now():%H:%M} {r['place']}{r['r']}R 合成1位 "
              f"{top['umaban']}{top['name']} {top['odds']:.1f}倍 "
              f"({top['pop']}番人気/木{top['trank']}位) → "
              f"{'通知' if hit else '条件外'}", flush=True)
        if hit:
            send_line(message(r, top, suggest(r, od)), dry)


if __name__ == "__main__":
    main()
