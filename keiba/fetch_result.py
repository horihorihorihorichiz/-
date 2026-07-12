# -*- coding: utf-8 -*-
"""レース結果と払戻を netkeiba 公開ページから取得する。
   usage: python fetch_result.py <race_id> [<race_id>...] [--json]
   JRA/NAR自動判定（race_id 5-6桁目が01-10ならJRA）。
   出力: 着順(全頭) + 払戻(単勝/複勝/馬連/ワイド/馬単/三連複/三連単)
"""
import re, sys, json, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def is_jra(rid):
    return rid[4:6] in {"%02d" % i for i in range(1, 11)}

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=30).read()
    try:
        return raw.decode("utf-8")  # 結果ページはUTF-8（db.netkeibaはEUC-JP）
    except UnicodeDecodeError:
        return raw.decode("euc-jp", errors="replace")

def get_result(rid):
    host = "race.netkeiba.com" if is_jra(rid) else "nar.netkeiba.com"
    h = fetch(f"https://{host}/race/result.html?race_id={rid}")
    out = {"race_id": rid}
    m = re.search(r'class="RaceName"[^>]*>\s*([^<]+)', h)
    if m: out["name"] = m.group(1).strip()
    # 着順
    order = []
    for tr in re.findall(r'<tr[^>]*class="[^"]*HorseList[^"]*".*?</tr>', h, re.S):
        rank = re.search(r'class="Rank">([^<]*)<', tr)
        num = re.search(r'class="Num Txt_C">\s*<div>(\d+)</div>', tr)
        name = re.search(r'class="HorseNameSpan">([^<]+)<', tr)
        if num:
            order.append({"rank": (rank.group(1).strip() if rank else ""),
                          "num": int(num.group(1)),
                          "name": (name.group(1).strip() if name else "")})
    out["order"] = order
    out["top3"] = [o["num"] for o in order if o["rank"] in ("1", "2", "3")][:3]
    # 払戻
    pays = {}
    KIND = {"Tansho": "単勝", "Fukusho": "複勝", "Wakuren": "枠連", "Umaren": "馬連",
            "Wide": "ワイド", "Umatan": "馬単", "Fuku3": "三連複", "Tan3": "三連単"}
    for cls, kind in KIND.items():
        m = re.search(r'<tr class="%s">.*?</tr>' % cls, h, re.S)
        if not m: continue
        blk = m.group(0)
        res = re.search(r'class="Result">(.*?)</td>', blk, re.S)
        pay = re.search(r'class="Payout">(.*?)</td>', blk, re.S)
        if not (res and pay): continue
        amounts = [int(x.replace(",", "")) for x in re.findall(r'([\d,]+)円', pay.group(1))]
        combos = []
        if cls in ("Tansho", "Fukusho"):
            nums = [int(n) for n in re.findall(r'<span>(\d+)</span>', res.group(1))]
            combos = [str(n) for n in nums]
        else:
            for ul in re.findall(r'<ul>(.*?)</ul>', res.group(1), re.S):
                nums = [int(n) for n in re.findall(r'<span>(\d+)</span>', ul)]
                if cls in ("Umatan", "Tan3"):
                    combos.append("→".join(str(n) for n in nums))
                else:
                    combos.append("-".join(str(n) for n in sorted(nums)))
        pays[kind] = dict(zip(combos, amounts))
    out["payout"] = pays
    return out

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    results = []
    for rid in args:
        try:
            r = get_result(rid)
        except Exception as e:
            r = {"race_id": rid, "error": str(e)}
        results.append(r)
        if not as_json:
            if "error" in r:
                print(f"{rid}: ERROR {r['error']}")
                continue
            t3 = "→".join(str(n) for n in r.get("top3", []))
            print(f"{rid} {r.get('name','')}: {t3}")
            for kind, d in r.get("payout", {}).items():
                s = " / ".join(f"{c}={v}円" for c, v in d.items())
                print(f"   {kind}: {s}")
    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
