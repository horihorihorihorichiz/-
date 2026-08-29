# -*- coding: utf-8 -*-
"""発走10分前に、合成1位のオッズが基準を越えていたら LINE に通知する。

仕組み:
  木の順位は動かないので、予想を作った時点で確定させておく（alerts JSON）。
  市場の順位はオッズで動くので、**発走10分前に生オッズだけ取り直して**
  合成し直す。そのうえで合成1位の単勝オッズを見て、基準以上なら送る。

  予想を作る    python predict_boost.py <cards> --date YYYYMMDD --alerts ... --viz ...
  通知を回す    python notify.py ../../data/alerts_20260830.json
  ボードも更新   python notify.py ../../data/alerts_20260830.json                     --viz ../../data/viz_20260830.json --board ../../data/board_20260830.html
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
HOLE_MIN = 5.0         # 軸が「穴」と言える単勝の下限（表示用。選択には使わない）

# 探索窓1,826Rでの実測回収率（system_bets.py）。文面に必ず添える。
# 軸も相手も木の順位だけで決める。人気は選択に使わない。
# 以前は「人気で穴を選んで軸にする」形を測っていて 80.4% だったが、
# 木で選ぶ形に替えたら 91.7% になった。11pt は選び方の差。
MEASURED = {
    "ワイド 木1位-2位": 91.7,        # ±5.1 / 1,826R
    "複勝 木1位": 87.2,              # ±1.8
    "単勝 木1位": 83.9,              # ±4.3
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


TOKEN_URL = "https://api.line.me/v2/oauth/accessToken"
_cached = {}


def access_token():
    """長期トークンがあればそれを使う。無ければチャネルID＋シークレットで発行する。

    チャネルシークレットは32桁の16進で、それ自体はアクセストークンではない。
    client_credentials でその場で短期トークン（30日）を取れる。
    """
    tok = getattr(config, "LINE_TOKEN", "")
    if tok:
        return tok
    if "tok" in _cached:
        return _cached["tok"]
    cid = str(getattr(config, "LINE_CHANNEL_ID", "") or "")
    sec = getattr(config, "LINE_CHANNEL_SECRET", "")
    if not cid or not sec:
        return ""
    try:
        r = requests.post(TOKEN_URL, timeout=15,
                          data={"grant_type": "client_credentials",
                                "client_id": cid, "client_secret": sec})
        if r.status_code != 200:
            print(f"トークンの発行に失敗 {r.status_code}: {r.text[:200]}")
            return ""
        _cached["tok"] = r.json().get("access_token", "")
        return _cached["tok"]
    except Exception as e:
        print(f"トークンの発行に失敗: {e}")
        return ""


def send_line(text, dry=False):
    tok = access_token()
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
    """軸も相手も木の順位だけで決める。人気は選択に使わない。

    以前は「人気で穴を選んで軸にする」形にしていたが、探索窓で測り直したら
    木で選ぶほうが 11pt 良かった（80.4% → 91.7%）。穴になるかどうかは
    結果であって条件ではない。
    """
    hs = [dict(h) for h in race["horses"] if h["umaban"] in odds]
    if len(hs) < 4:
        return None
    for h in hs:
        h["odds"], h["pop"] = odds[h["umaban"]]
    hs.sort(key=lambda h: h["trank"])
    return {"jiku": hs[0], "aite": hs[1:3]}


def message(race, top, sug=None):
    ev = f"／追い切り {top['evalWord']}" if top.get("evalWord") else ""
    t = (f"🐎 {race['place']}{race['r']}R {race['post']}発走"
         f"（あと{LEAD_MIN}分）\n"
         f"{race['title'] or ''} {race['surf']}{race['dist']}m {race['n']}頭\n"
         f"\n合成1位　{top['umaban']} {top['name']}\n"
         f"単勝 {top['odds']:.1f}倍（{top['pop']}番人気）／木の順位 {top['trank']}位{ev}")
    if sug:
        h, a = sug["jiku"], sug["aite"]
        ana = "（結果として穴軸）" if h["odds"] >= HOLE_MIN else ""
        t += (f"\n\n── 木の順位で組む{ana} ──\n"
              f"軸 {h['umaban']} {h['name']}"
              f"（{h['odds']:.1f}倍・{h['pop']}番人気・木1位）\n"
              "相手 " + " / ".join(
                  f"{x['umaban']} {x['name']}（{x['odds']:.1f}倍・木{x['trank']}位）"
                  for x in a) +
              "\nワイド 軸-相手 の2点\n"
              f"\n実測 {MEASURED['ワイド 木1位-2位']:.1f}%（±5.1・1,826R）。"
              "人気で穴を選んで軸にすると80.4%まで落ちるので、軸は木で決めている。")
    t += ("\n\n※これは並びであって買い目の推奨ではない。"
          "いちばん良い形でも実測91.7%で、控除率20%の壁に8pt届いていない。"
          "長く続ければ負ける形と分かったうえで買うこと。")
    return t


def refresh_board(viz_path, board_path, rid, odds):
    """オッズを見たついでに、ボードのそのレースだけ最新に直して作り直す。

    木の順位は動かないが、市場の順位はオッズで動くので合成の並びも動く。
    アーティファクトへの公開は Claude Code が動いているときしかできないので、
    ここで直すのはローカルのHTML。
    """
    try:
        viz = json.load(open(viz_path, encoding="utf-8"))
        R = next((x for x in viz["races"] if x["id"] == rid), None)
        if not R:
            return
        hs = [h for h in R["horses"] if h["umaban"] in odds]
        if len(hs) < 5:
            return
        hs.sort(key=lambda h: odds[h["umaban"]][0])
        for i, h in enumerate(hs):
            h["odds"], h["pop"] = odds[h["umaban"]]
            h["blend"] = (h["trank"] - 1) + i
            h["score"] = -float(h["blend"])
        R["horses"].sort(key=lambda h: (-h["score"], h["trank"]))
        json.dump(viz, open(viz_path, "w", encoding="utf-8"), ensure_ascii=False)
        import make_board
        make_board.build(viz_path, board_path, "堀川ボード")
    except Exception as e:
        print(f"ボードの更新に失敗: {e}")


def main():
    path = sys.argv[1]
    dry = "--dry" in sys.argv
    opt = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
    viz_path, board_path = opt("--viz"), opt("--board")
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
        if viz_path and board_path:
            refresh_board(viz_path, board_path, r["id"], od)
        hit = top["odds"] >= ODDS_MIN
        print(f"{datetime.now():%H:%M} {r['place']}{r['r']}R 合成1位 "
              f"{top['umaban']}{top['name']} {top['odds']:.1f}倍 "
              f"({top['pop']}番人気/木{top['trank']}位) → "
              f"{'通知' if hit else '条件外'}", flush=True)
        if hit:
            send_line(message(r, top, suggest(r, od)), dry)


if __name__ == "__main__":
    main()
