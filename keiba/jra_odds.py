# -*- coding: utf-8 -*-
"""
jra_odds.py ── JRA公式(スマホ版 sp.jra.jp)から単勝・複勝オッズを取るフォールバック取得器

背景:
  netkeiba の無料オッズAPI (race.netkeiba.com/api/api_get_jra_odds.html) は
  場単位で配信停止になることがある (status NG "empty free odds schedule")。
  その時にJRA公式サイトから単勝・複勝だけでも取れるようにする。

仕組み (公開ページのナビゲーションのみ・ログイン不要):
  sp.jra.jp は JRADB の cname POST 方式。
    POST https://sp.jra.jp/JRADB/accessO.html  body: cname=sw15oli00/FA
  で「オッズ」インデックスが返り、そこに開催(場・日)ごとのリンク
    sw15orl{pp}{VV}{YYYY}{KK}{DD}{開催日8桁}/{checksum}
  が並ぶ。開催ページには各レース×券種のリンク
    sw15{T}ou{pp}{VV}{YYYY}{KK}{DD}{RR}{開催日8桁}Z.../{checksum}
    (T: 1=単勝複勝 3=枠連 4=馬連 5=ワイド 6=馬単 7=三連複 8=三連単)
  が並ぶ。checksum の算出法は不明なので自前生成はせず、ページから
  スクレイプした cname をそのまま次のPOSTに使う(3リクエストで到達)。

race_id との対応:
  netkeiba の JRA race_id 12桁 = YYYY(4) + 場VV(2) + 回KK(2) + 日DD(2) + R(2)。
  場コードはJRA公式と共通 (01札幌 02函館 03福島 04新潟 05東京 06中山
  07中京 08京都 09阪神 10小倉)。cname 内の VV+YYYY+KK+DD+RR がそのまま
  race_id の並べ替えなので、開催日(カレンダー日付)を知らなくても照合できる。

使い方:
  from jra_odds import fetch_official
  d = fetch_official("202604020812")
  # -> {"tan": {1: 43.4, ...}, "fuku": {1: 7.9, ...}, "fuku_max": {1: 10.9, ...},
  #     "names": {1: "ブロッコロ", ...}, "asof": "18:01現在", "kai_nichi": "2回新潟8日",
  #     "source": "sp.jra.jp", "reason": None}
  # 取れない時: tan/fuku は空dict、reason に理由。
CLI:
  python3 jra_odds.py 202604020812
注意:
  - 公開ページのみ。ログイン・購入系(ipat等)には一切触れない。
  - リクエスト間に1秒スリープ(計3リクエスト)。
  - 複勝は fuku=下限 / fuku_max=上限 (netkeiba fetch_jra の複勝も下限)。
"""
import re, sys, time, json, subprocess

BASE = "https://sp.jra.jp"
ACCESS_O = BASE + "/JRADB/accessO.html"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
ODDS_INDEX_CNAME = "sw15oli00/FA"   # トップページから取れなかった時の既定値(実測)
SLEEP = 1.0

JRA_VENUE = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
             "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}


def _http(url, post_data=None):
    """Shift_JISページを取得してunicodeで返す。proxy環境で確実なcurlを主、urllibを予備に。"""
    cmd = ["curl", "-sS", "-m", "25", "-A", UA]
    if post_data is not None:
        cmd += ["--data-urlencode", post_data]
    cmd.append(url)
    try:
        return subprocess.check_output(cmd, timeout=30).decode("cp932", "ignore")
    except Exception:
        import urllib.request, urllib.parse
        data = None
        if post_data is not None:
            k, v = post_data.split("=", 1)
            data = urllib.parse.urlencode({k: v}).encode()
        req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
        return urllib.request.urlopen(req, timeout=25).read().decode("cp932", "ignore")


def _f(x):
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return None


def _parse_race_id(race_id):
    rid = str(race_id)
    if not re.fullmatch(r"\d{12}", rid):
        return None
    year, vv, kk, dd, rr = rid[0:4], rid[4:6], rid[6:8], rid[8:10], rid[10:12]
    if vv not in JRA_VENUE:
        return None   # 地方(NAR)は対象外
    return dict(year=year, vv=vv, kk=kk, dd=dd, rr=rr, venue=JRA_VENUE[vv])


def _logger(debug):
    def log(*a):
        if debug:
            print("[jra_odds]", *a, file=sys.stderr)
    return log


def _fetch_expect(cname, marker, tries=3, log=None):
    """cnameをPOSTし、markerを含むページが返るまで最大tries回試す。
    (JRADBはまれに目的リンクを含まない中間ページを返すことがある: 実測)"""
    log = log or (lambda *a: None)
    last = ""
    for i in range(tries):
        if i:
            time.sleep(2)
        try:
            last = _http(ACCESS_O, "cname=" + cname)
        except Exception as e:
            log("fetch error:", e)
            continue
        if re.search(marker, last):
            return last
        log("marker '%s' missing (try %d)" % (marker, i + 1))
    return last


def _race_link_pat(rkey, t):
    """開催ページ内の「レース×券種」リンク cname にマッチする正規表現。
    T: 1=単複 3=枠連 4=馬連 5=ワイド 6=馬単 7=三連複 8=三連単。
    実例 sw155ou 10 012026010801 20260816 Z /78 (三連複はさらに Z99=軸未選択)。"""
    return r"'(sw15%dou\w{0,2}%s\d{8}Z?\w*/[0-9A-F]{2})'" % (t, rkey)


def _nav_day_page(p, race_pat, log):
    """オッズインデックス→開催(場・日)ページまでナビゲートし、race_pat を含む
    開催ページHTMLを返す。返り値 (day_html or None, reason or None)。"""
    # 1) オッズインデックス (開催一覧)。cname sw15oli00/FA が変わった時に備え
    #    トップページからも拾えるが、まず既定値で直接POSTする。
    try:
        idx = _fetch_expect(ODDS_INDEX_CNAME, "sw15orl", log=log)
    except Exception as e:
        return None, "sp.jra.jp に到達できない: %s" % e
    if "sw15orl" not in idx:
        # 既定cnameが無効化された可能性 → トップページからオッズリンクを再取得
        log("index cname stale; re-scrape top page")
        try:
            time.sleep(SLEEP)
            top = _http(BASE + "/")
            m = re.search(r"doAction\('/JRADB/accessO\.html'\s*,\s*'(sw15oli[^']+)'", top)
            if m:
                time.sleep(SLEEP)
                idx = _fetch_expect(m.group(1), "sw15orl", log=log)
        except Exception:
            pass
    if "sw15orl" not in idx:
        return None, "オッズインデックスに開催リンクが無い(開催日以外/サイト構造変更)"

    # 2) 開催(場・日)リンクを race_id の VV+YYYY+KK+DD で特定
    key = p["vv"] + p["year"] + p["kk"] + p["dd"]          # 例 0420260208
    mv = re.search(r"'(sw15orl\d{2}%s\d{8}/[0-9A-F]{2})'" % key, idx)
    if not mv:
        have = sorted(set(re.findall(r"sw15orl\d{2}(\d{10})\d{8}/", idx)))
        return None, ("開催 %s回%s%s日 がJRA公式オッズ一覧に無い(当日/前日のみ掲載)。"
                      "掲載中=%s" % (int(p["kk"]), p["venue"], int(p["dd"]), have))
    log("venue-day cname:", mv.group(1))
    time.sleep(SLEEP)
    return _fetch_expect(mv.group(1), race_pat, log=log), None


def fetch_official(race_id, debug=False):
    """JRA公式(sp.jra.jp)から単勝・複勝オッズ。
    返り値: dict(tan={馬番int:float}, fuku={馬番int:下限float}, fuku_max=...,
                 names={馬番int:馬名}, asof=更新時刻表示, kai_nichi="2回新潟8日",
                 source="sp.jra.jp", reason=None or 失敗理由)"""
    empty = dict(tan={}, fuku={}, fuku_max={}, names={}, asof=None,
                 kai_nichi=None, source="sp.jra.jp", reason=None)
    p = _parse_race_id(race_id)
    if not p:
        empty["reason"] = "race_id が JRA 12桁形式でない(場コード01-10): %s" % race_id
        return empty

    log = _logger(debug)

    # 1-2) オッズインデックス → 開催(場・日)ページ
    # 3) 当該レースの「単勝・複勝」リンク (sw151ou...VVYYYYKKDDRR...)
    key = p["vv"] + p["year"] + p["kk"] + p["dd"]
    rkey = key + p["rr"]                                    # 例 042026020812
    race_pat = _race_link_pat(rkey, 1)
    day, reason = _nav_day_page(p, race_pat, log)
    if reason:
        empty["reason"] = reason
        return empty
    mr = re.search(race_pat, day or "")
    if not mr:
        empty["reason"] = "%sR の単複オッズリンクが開催ページに無い(発売前/取止め?)" % int(p["rr"])
        return empty
    log("race cname:", mr.group(1))
    time.sleep(SLEEP)
    page = _fetch_expect(mr.group(1), r'class="umaban"', log=log)
    if 'class="umaban"' not in page:
        empty["reason"] = "オッズページ取得失敗(馬番表が無い)"
        return empty

    # 4) パース。行例:
    #  <td class="umaban">3</td>
    #  <td class="bamei"><a ...>マーゴットライズ</a></td>
    #  <td class="oztan oddsJyuBaiMiman">5.0</td>
    #  <td class="fukuArea"><div class="fukuMin">1.7</div>...<div class="fukuMax">2.2</div></td>
    tan, fuku, fmax, names = {}, {}, {}, {}
    row_re = re.compile(
        r'class="umaban">(\d+)</td>\s*'
        r'<td class="bamei">(?:<a[^>]*>)?([^<]*)(?:</a>)?</td>\s*'
        r'<td class="oztan[^"]*">([^<]*)</td>'
        r'(?:<td class="fukuArea"><div class="fukuMin">([^<]*)</div>'
        r'.*?<div class="fukuMax">([^<]*)</div></td>)?',
        re.S)
    for m in row_re.finditer(page):
        num = int(m.group(1))
        names[num] = m.group(2).strip()
        t = _f(m.group(3))
        if t:
            tan[num] = t
        fl, fh = _f(m.group(4)), _f(m.group(5))
        if fl:
            fuku[num] = fl
        if fh:
            fmax[num] = fh
    if not tan:
        empty["reason"] = "オッズ表のパース失敗(構造変更? 取消のみ?)"
        empty["names"] = names
        return empty

    # 発売中="18:06現在" / 発走後="最終"(最終オッズ) / 確定表示があれば"確定"
    mh = re.search(r"(\d+回\S{2,3}\d+日).{0,80}?(\d{1,2}:\d{2}現在|確定|最終)", page, re.S)
    asof = kai = None
    if mh:
        kai, asof = mh.group(1), mh.group(2)
    return dict(tan=tan, fuku=fuku, fuku_max=fmax, names=names,
                asof=asof, kai_nichi=kai, source="sp.jra.jp", reason=None)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="JRA公式(sp.jra.jp)単勝・複勝オッズ取得")
    ap.add_argument("race_id", help="netkeiba形式12桁 (例 202604020812)")
    ap.add_argument("--json", action="store_true", help="JSONで出力")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    d = fetch_official(args.race_id, debug=args.debug)
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return
    p = _parse_race_id(args.race_id) or {}
    print("■ JRA公式オッズ (%s)  %s %sR  %s %s" % (
        d["source"], p.get("venue", "?"), int(p.get("rr", 0) or 0),
        d.get("kai_nichi") or "", d.get("asof") or ""))
    if d["reason"]:
        print("  取得失敗:", d["reason"])
        return
    print("  馬番  単勝   複勝        馬名")
    for num in sorted(d["tan"]):
        fu = d["fuku"].get(num)
        fx = d["fuku_max"].get(num)
        fs = ("%s-%s" % (fu, fx)) if fu and fx else (str(fu) if fu else "-")
        print("  %3d  %6.1f  %-10s %s" % (num, d["tan"][num], fs, d["names"].get(num, "")))


if __name__ == "__main__":
    main()
