# -*- coding: utf-8 -*-
"""V8「情報拡張」の as-of 特徴量エンジン（F1 当日トラックバイアス / F2 前走不利推定 /
   F4 コースプロファイル）。V8_PROTOCOL_20260817.md の事前登録に対応する実装。

   ★設計の芯 = 「リークを構造で防ぐ」
     台帳(hist/*.json)を **日付昇順 → 同一開催日は R番号昇順** に1回だけ走査し、
     各レースについて「読む → 書く」の順序を厳守する。つまりレースRの特徴を作る時点で
     累積器に入っているのは R より前に発走したレースだけ。後から差し引く実装（全体集計を
     作ってから自分を引く）は一切していない。これにより

       - F1(当日トラックバイアス): 同一 day_key(=race_idの先頭10桁: 年+場+回+日) かつ
         R番号が小さいレースの結果だけを使う。当日3R未満なら全て0(中立)。
       - F4(コースプロファイル) : **当該レースの日付より前の日** のレース結果だけを使う。
         フォールド境界ではなく「そのレース自身の日付」を基準にするので、学習側と
         ライブ側で情報量の定義が完全に一致する（RULES.md の統一原則）。
       - F2(前走不利推定)の上がり基準テーブルも同じく「前の日まで」で作る。

   使い方:
     import course_bias as CB
     idx = CB.index()                     # 台帳を1回走査(キャッシュあり)
     ctx = idx.race_ctx(rid)              # F1/F4のレース単位特徴(10本)
     f2  = idx.f2(rid)                    # {馬番: F2特徴dict}
     CB.horse_v8(num, race, h, ctx, ...)  # 馬単位の相互作用・同コース実績

   単体実行:
     python3 course_bias.py            # 自己検証(as-of性・値域・当日1R目の中立性)
     python3 course_bias.py --rebuild  # キャッシュ再構築
"""
import glob
import json
import math
import os
import pickle
import sys

import course

_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(_DIR, "cb_cache.pkl")
CACHE_VER = 3          # 定義を変えたら必ず上げる(古いキャッシュの誤用防止)

# ── 定数(データから決めていない固定値。決め打ちの根拠はコメントに書く) ─────────
FRONT_EP = 0.30        # 早期位置ep<=0.30 を「逃げ・先行」とみなす(fit_v2.STYLE_POSの'先'=0.30)
MIN_DAY_RACES = 3      # 当日これ未満のR数では F1 を全て0(中立)にする(事前登録どおり)
MIN_DAY_SURF = 2       # 同一馬場サブセットはこれ未満なら0
SHRINK_K = 40.0        # F4コースプロファイルの縮小係数(標本nが小さいほど0へ寄せる)
NINKI_NEUTRAL = 0.25   # 勝ち馬の正規化人気の中立値。長期平均を測って決めると「未来を見た定数」に
                       # なるので、あえて固定の事前定数にしてある(荒れ度の原点)
AGARI_CLIP = 2.5       # 上がり残差のクリップ(秒)。外れ値の暴走を止める
AGARI_MIN_N = 30       # 上がり基準テーブルを採用する最小標本

# fit_v2.STYLE_POS と同一。course_bias→fit_v2 の循環importを避けるため写している。
# 値がズレると特徴の意味が変わるので、__main__ の自己検証で fit_v2.ep_of と一致を確認する。
STYLE_POS = {"逃": 0.10, "先": 0.30, "差": 0.60, "追": 0.85}

BABA_IDX = {"良": 0, "稍": 1, "稍重": 1, "重": 2, "不": 3, "不良": 3}


# ── レース単位(F1/F4)の特徴名。fit_v2 側はこの順序をそのまま使う ────────────────
CTX_F1 = ["tb_n", "tb_waku", "tb_waku_surf", "tb_front", "tb_front_surf", "tb_upset"]
CTX_F4 = ["cp_n", "cp_waku", "cp_front", "cp_fav"]
# 馬単位・生値(レース内z化しない。絶対的な意味を持つため)
RAW_F1 = ["tb_x_waku", "tb_x_ep"]
RAW_F4 = ["cp_x_waku", "cp_x_ep", "cs_runs"]
# 馬単位・レース内z化する量(Noneは0=平均扱いに落ちる)
Z_F2 = ["f2_wide_mean3", "f2_wide_max", "f2_kick_mean3", "f2_kick_max", "f2_last"]
Z_F4 = ["cs_top3", "cs_fin"]

NEUTRAL_CTX = {k: 0.0 for k in CTX_F1 + CTX_F4}


def dist_band(d):
    """コースキーの距離帯。短(<1400) / マイル(<1800) / 中長(>=1800)"""
    d = d or 0
    return "S" if d < 1400 else "M" if d < 1800 else "L"


def course_key(venue, surface, dist):
    return ((venue or "").strip(), surface or "", dist_band(dist))


def early_pos(h):
    """馬の早期位置ep(0=逃げ〜1=最後方)。過去5走の corner4/field 平均、無ければ紙上脚質。
       ※fit_v2.ep_of と同一定義(自己検証で一致を確認)"""
    rs = h.get("races", []) or []
    cf = [r["corner4"] / max(r.get("field") or 1, 1) for r in rs[:5] if r.get("corner4")]
    if cf:
        return sum(cf) / len(cf)
    return STYLE_POS.get(h.get("paper_style"))


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


# ══════════════════════════════════════════════════════════════════════════
#  1レース分の「結果サマリ」。F1の日内累積と F4のコース累積の両方の材料になる。
#  ここで作る量は全て **そのレース自身の結果** なので、使う側は必ず
#  「自分より前のレース」のサマリだけを混ぜること。
# ══════════════════════════════════════════════════════════════════════════
def race_summary(d):
    race = d.get("race") or {}
    order = (d.get("result") or {}).get("order") or []
    field = len(order)
    if field < 5:
        return None
    runners = [o for o in order if str(o.get("rank", "")).isdigit()]
    if len(runners) < 5:
        return None
    top3 = [o["num"] for o in order if str(o.get("rank", "")) in ("1", "2", "3")]
    if len(top3) < 3:
        return None
    nrun = len(runners)

    # (a) 内外バイアス: 3着内馬の枠番(0-1正規化)平均 − 出走全馬の枠番平均。
    #     レースごとに自己正規化しているので、外部定数も全期間平均も要らない=リークしない。
    wr = {o["num"]: (course.jra_waku(int(o["num"]), field) - 1) / 7.0 for o in runners}
    base_w = _mean(wr.values())
    waku_dev = _mean([wr[n] for n in top3 if n in wr])
    waku_dev = (waku_dev - base_w) if (waku_dev is not None and base_w is not None) else None

    # (b) 脚質バイアス: 逃げ・先行タイプ(ep<=0.30)の3着内率 − 期待値(3/出走頭数)。
    #     ※台帳の result には各レースの4角通過順が無いため、「実際に4角3番手以内だったか」
    #       ではなく「事前に先行が見込まれた馬か(過去走のcorner4平均/紙上脚質)」で近似する。
    #       これは発走前に確定している情報なので、リークではなく“近似の限界”。
    eps = {}
    for h in race.get("horses") or []:
        eps[h.get("num")] = early_pos(h)
    fr = [n for n in wr if eps.get(n) is not None and eps[n] <= FRONT_EP]
    front_dev = None
    if fr and len(fr) < nrun:
        s3 = set(top3)
        front_dev = sum(1 for n in fr if n in s3) / len(fr) - 3.0 / nrun

    # (c) 荒れ度: 勝ち馬の正規化人気 − 中立値0.25
    win = next((o for o in order if str(o.get("rank", "")) == "1"), None)
    upset = fav_win = None
    if win and win.get("ninki") and field > 1:
        upset = (win["ninki"] - 1) / (field - 1) - NINKI_NEUTRAL
        fav_win = 1.0 if win["ninki"] == 1 else 0.0

    return dict(waku=waku_dev, front=front_dev, upset=upset, fav=fav_win,
                surface=race.get("surface") or "", n=nrun)


# ══════════════════════════════════════════════════════════════════════════
#  F2: 前走不利推定（各馬の過去走レコードだけから作る＝完全に事前情報）
# ══════════════════════════════════════════════════════════════════════════
def _agari_bench(tbl, surface, dist, baba_idx):
    """as-of上がり基準(平均上がり)。(馬場,距離200括り,馬場状態)→(馬場,距離)→(馬場)の順に落ちる"""
    if not surface or not dist:
        return None
    db = int(round(dist / 200.0) * 200)
    for key in ((surface, db, baba_idx), (surface, db, None), (surface, None, None)):
        t = tbl.get(key)
        if t and t[1] >= AGARI_MIN_N:
            return t[0] / t[1]
    return None


def _pr_disadv(pr, tbl):
    """過去走1本から (wide, kick) を出す。
       wide = max(0, 4角相対位置 − 着順相対) × 4角相対位置
              …後方/外を回っていたのに着順はそれより良い＝ぶん回し・詰まりでの健闘度。
                位置が深いほど重く効くように4角相対位置を掛けている。
       kick = max(0, 上がり基準との差) × max(0, 着順相対 − 0.35)
              …その条件の標準より速い上がりを使ったのに着順が悪い＝展開不利で脚を余した度合い。"""
    fin, fld = pr.get("finish"), pr.get("field")
    if not fin or not fld or fld < 2:
        return None, None
    fin_rel = min(1.0, fin / fld)
    wide = None
    c4 = pr.get("corner4")
    if c4:
        pos_rel = min(1.0, c4 / fld)
        wide = max(0.0, pos_rel - fin_rel) * pos_rel
    kick = None
    bench = _agari_bench(tbl, pr.get("surface"), pr.get("dist"), pr.get("baba_idx"))
    if bench is not None and pr.get("agari"):
        edge = max(-AGARI_CLIP, min(AGARI_CLIP, bench - pr["agari"]))
        kick = max(0.0, edge) * max(0.0, fin_rel - 0.35)
    return wide, kick


def f2_feats(h, tbl):
    """1頭分のF2特徴(直近3走の平均/最大 + 前走の総量)。該当が無ければNone→レース内zで0"""
    rs = (h.get("races") or [])[:3]
    ws, ks = [], []
    for pr in rs:
        w, k = _pr_disadv(pr, tbl)
        if w is not None:
            ws.append(w)
        if k is not None:
            ks.append(k)
    f = {
        "f2_wide_mean3": _mean(ws),
        "f2_wide_max": max(ws) if ws else None,
        "f2_kick_mean3": _mean(ks),
        "f2_kick_max": max(ks) if ks else None,
        "f2_last": None,
    }
    if rs:
        w0, k0 = _pr_disadv(rs[0], tbl)
        if w0 is not None or k0 is not None:
            f["f2_last"] = (w0 or 0.0) + (k0 or 0.0)
    return f


# ══════════════════════════════════════════════════════════════════════════
#  F4補助: 当該馬の「同コース」実績（過去走レコードのみ＝事前情報）
#  ※既知の限界: 過去走レコードには開催場が入っておらず、vg も収穫初期の見落としで
#    実測 91% が 2 固定（＝信用できない）。よって「同コース」は
#    (馬場 × 距離帯) までの近似にとどめる。場まで一致させたいなら収穫側の拡張が要る。
# ══════════════════════════════════════════════════════════════════════════
def same_course_record(h, race):
    surf = race.get("surface")
    band = dist_band(race.get("distance"))
    runs, top3, fins = 0, 0, []
    for pr in h.get("races") or []:
        if pr.get("surface") != surf or dist_band(pr.get("dist")) != band:
            continue
        fin, fld = pr.get("finish"), pr.get("field")
        if not fin or not fld:
            continue
        runs += 1
        top3 += 1 if fin <= 3 else 0
        fins.append(fin / fld)
    return {
        "cs_runs": float(min(runs, 6)),
        "cs_top3": (top3 / runs) if runs else None,
        "cs_fin": -_mean(fins) if fins else None,   # 符号を揃える(大きいほど良い)
    }


# ══════════════════════════════════════════════════════════════════════════
#  as-of インデックス本体
# ══════════════════════════════════════════════════════════════════════════
class AsOfIndex:
    """台帳を時系列に1回走査して、レースごとの F1/F4 レース特徴と F2 馬特徴を確定させる。"""

    def __init__(self):
        self.ctx = {}          # rid -> {ctx特徴}
        self.f2 = {}           # rid -> {馬番 -> F2特徴}
        self.date = {}         # rid -> 'YYYYMMDD'
        self.course = {}       # 最終時点のコース累積(ライブ用)
        self.agari = {}        # 最終時点の上がり基準(ライブ用)
        self.g_fav = [0.0, 0]  # 最終時点の全体1人気勝率
        self.n_races = 0
        self.max_rid = ""

    # ---- 参照 -------------------------------------------------------------
    def race_ctx(self, rid):
        return self.ctx.get(rid) or dict(NEUTRAL_CTX)

    def f2_of(self, rid):
        return self.f2.get(rid) or {}

    def profile(self, venue, surface, dist):
        """ライブ用: 最終時点までの累積から F4 コースプロファイルを引く。
           (学習時は各レースの日付時点の値が self.ctx に固定されている)"""
        return _cp_from(self.course.get(course_key(venue, surface, dist)),
                        _rate(self.g_fav))

    def live_race_ctx(self, race, prior_day=None):
        """ライブ用のレース単位特徴。prior_day には当日の先行レースのサマリ列
           (race_summary()の戻り)を渡せる。無ければF1は中立0になる。"""
        c = self.profile(race.get("venue"), race.get("surface"), race.get("distance"))
        c.update(_tb_from(prior_day or [], race.get("surface")))
        return c

    # ---- 構築 -------------------------------------------------------------
    def build(self, histdir="hist", verbose=True):
        import re
        files = sorted(glob.glob(os.path.join(histdir, "*.json")))
        # 1周目: 日付だけを取る(全dictをメモリに載せないため生テキストから正規表現で抜く)
        pairs = []
        for f in files:
            rid = os.path.basename(f)[:-5]
            if len(rid) < 12 or not rid[10:12].isdigit():
                continue
            try:
                m = re.search(r'"date"\s*:\s*"(\d{8})"', open(f, encoding="utf-8").read())
            except Exception:
                continue
            if not m:
                continue
            self.date[rid] = m.group(1)
            pairs.append((m.group(1), rid, f))
        # ★as-ofの土台: 日付 → 開催キー → R番号 の昇順。この順序でしか累積器に触らない。
        pairs.sort(key=lambda x: (x[0], x[1][:10], int(x[1][10:12])))
        self.n_races = len(pairs)
        self.max_rid = pairs[-1][1] if pairs else ""

        cur_date = None
        pend = []              # 「同じ日付」の寄与。日付が変わるまで累積器に入れない
        day_acc = {}           # day_key -> 当日ここまでのサマリ列(日内は逐次更新して良い)
        for i, (date, rid, f) in enumerate(pairs):
            if date != cur_date:
                for s, ck, prs in pend:      # ← 前日までの分をここで初めて反映
                    self._absorb(s, ck, prs)
                pend = []
                day_acc = {}
                cur_date = date
            try:
                d = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            race = d.get("race") or {}
            dk = rid[:10]
            # ---- F1: 同一開催日・同一場の「先に発走した」レースだけ ----
            ctxf = _tb_from(day_acc.get(dk, []), race.get("surface"))
            # ---- F4: 「前の日まで」のコース累積だけ ----
            ck = course_key(race.get("venue"), race.get("surface"), race.get("distance"))
            ctxf.update(_cp_from(self.course.get(ck), _rate(self.g_fav)))
            self.ctx[rid] = ctxf
            # ---- F2: 「前の日まで」の上がり基準で各馬の過去走を評価 ----
            self.f2[rid] = {h.get("num"): f2_feats(h, self.agari)
                            for h in race.get("horses") or []}
            # ---- 書き込み(必ず読んだ後) ----
            s = race_summary(d)
            if s:
                day_acc.setdefault(dk, []).append(s)      # 日内は即時反映(=後のRから見える)
            pend.append((s, ck, race.get("horses") or []))  # 日跨ぎ分は翌日から反映
            if verbose and i % 1500 == 0:
                print(f"  ...{i}/{len(pairs)}", file=sys.stderr)
        for s, ck, prs in pend:
            self._absorb(s, ck, prs)
        return self

    def _absorb(self, s, ck, horses):
        """1レース分をグローバル累積(コースプロファイル・上がり基準)に取り込む"""
        if s:
            a = self.course.setdefault(ck, [0.0, 0, 0.0, 0, 0.0, 0])
            if s["waku"] is not None:
                a[0] += s["waku"]; a[1] += 1
            if s["front"] is not None:
                a[2] += s["front"]; a[3] += 1
            if s["fav"] is not None:
                a[4] += s["fav"]; a[5] += 1
                self.g_fav[0] += s["fav"]; self.g_fav[1] += 1
        for h in horses:
            for pr in h.get("races") or []:
                a, sf, ds = pr.get("agari"), pr.get("surface"), pr.get("dist")
                if not a or not sf or not ds:
                    continue
                db = int(round(ds / 200.0) * 200)
                for key in ((sf, db, pr.get("baba_idx")), (sf, db, None), (sf, None, None)):
                    t = self.agari.setdefault(key, [0.0, 0])
                    t[0] += a
                    t[1] += 1


def _rate(pair):
    return (pair[0] / pair[1]) if pair[1] else 0.0


def _tb_from(prior, surface=None):
    """当日の先行レースサマリ列 → F1特徴。3R未満は全て0(中立)。
       tb_n だけは「情報がまだ無い」ことを学習器に伝えるため常に実数を返す(事前登録どおり)。
       *_surf は今日と同じ馬場(芝/ダ)の先行レースだけで見た値(芝とダで馬場傾向は別物のため)。"""
    out = {k: 0.0 for k in CTX_F1}
    out["tb_n"] = float(len(prior))
    if len(prior) < MIN_DAY_RACES:
        return out
    out["tb_waku"] = _mean([p["waku"] for p in prior]) or 0.0
    out["tb_front"] = _mean([p["front"] for p in prior]) or 0.0
    out["tb_upset"] = _mean([p["upset"] for p in prior]) or 0.0
    sub = [p for p in prior if p.get("surface") == surface] if surface else []
    if len(sub) >= MIN_DAY_SURF:
        out["tb_waku_surf"] = _mean([p["waku"] for p in sub]) or 0.0
        out["tb_front_surf"] = _mean([p["front"] for p in sub]) or 0.0
    return out


def _cp_from(acc, g_fav_rate):
    """コース累積 → F4特徴。標本nでの縮小(shrinkage)込み。累積が無ければ全て0"""
    out = {k: 0.0 for k in CTX_F4}
    if not acc:
        return out
    sw, nw, sf, nf, fv, nv = acc
    out["cp_n"] = math.log1p(max(nw, nv))
    out["cp_waku"] = sw / (nw + SHRINK_K) if nw else 0.0
    out["cp_front"] = sf / (nf + SHRINK_K) if nf else 0.0
    if nv:
        out["cp_fav"] = (fv + g_fav_rate * SHRINK_K) / (nv + SHRINK_K) - g_fav_rate
    return out


# ── 馬単位のV8生特徴(相互作用 + 同コース実績) ────────────────────────────────
def horse_v8(num, race, h, ctx, field=None):
    """ctx は race_ctx()/live_race_ctx() の戻り。waku/epは fit_v2 と同じ定義で再計算する。"""
    fld = int(field or race.get("field") or len(race.get("horses") or []) or 1)
    n = int(num)
    waku = course.jra_waku(n, fld) if 1 <= n <= fld else 0
    waku_rel = (waku - 1) / 7.0 if waku else 0.5
    ep = early_pos(h)
    ep = 0.45 if ep is None else ep
    # 外バイアスの日は外枠馬を、先行有利の日は先行馬を持ち上げる向きに符号を揃えている
    out = {
        "tb_x_waku": ctx.get("tb_waku_surf", 0.0) * (waku_rel - 0.5),
        "tb_x_ep": ctx.get("tb_front_surf", 0.0) * (0.45 - ep),
        "cp_x_waku": ctx.get("cp_waku", 0.0) * (waku_rel - 0.5),
        "cp_x_ep": ctx.get("cp_front", 0.0) * (0.45 - ep),
    }
    out.update(same_course_record(h, race))
    return out


# ── キャッシュ ────────────────────────────────────────────────────────────
_IDX = None


def index(histdir="hist", rebuild=False, verbose=True):
    """as-ofインデックスを取得(プロセス内メモ + ディスクキャッシュ)。
       台帳ファイル数か最大race_idが変わったら自動で作り直す(収穫の進行に追従)。"""
    global _IDX
    if _IDX is not None and not rebuild:
        return _IDX
    files = sorted(glob.glob(os.path.join(histdir, "*.json")))
    sig = (CACHE_VER, len(files), os.path.basename(files[-1]) if files else "")
    if not rebuild and os.path.exists(CACHE):
        try:
            with open(CACHE, "rb") as f:
                got_sig, idx = pickle.load(f)
            if got_sig == sig:
                _IDX = idx
                return idx
        except Exception:
            pass
    if verbose:
        print(f"course_bias: as-ofインデックス構築中 ({len(files)}R)...", file=sys.stderr)
    idx = AsOfIndex().build(histdir, verbose=verbose)
    try:
        with open(CACHE, "wb") as f:
            pickle.dump((sig, idx), f)
    except Exception:
        pass
    _IDX = idx
    return idx


# ══════════════════════════════════════════════════════════════════════════
#  自己検証: 定義の一致・as-of性・値域・当日1R目の中立性
# ══════════════════════════════════════════════════════════════════════════
def _selftest():
    import fit_v2 as V2
    idx = index(rebuild="--rebuild" in sys.argv)
    print(f"インデックス: {idx.n_races}R / コースキー{len(idx.course)} / 上がり表{len(idx.agari)}")

    # 1) ep定義が fit_v2 と一致するか
    files = sorted(glob.glob(os.path.join(_DIR, "hist", "*.json")))
    d = json.load(open(files[len(files)//2], encoding="utf-8"))
    for h in d["race"]["horses"]:
        a, b = early_pos(h), V2.ep_of(h)
        assert (a is None and b is None) or abs(a - b) < 1e-12, f"ep定義がfit_v2と不一致 {a} {b}"
    print("✅ ep定義 = fit_v2.ep_of と一致")

    # 2) 当日1R目は F1 が全て中立0 / tb_n=0
    firsts = [os.path.basename(f)[:-5] for f in files if os.path.basename(f)[10:12] == "01"]
    bad = [r for r in firsts[:400] if any(idx.race_ctx(r)[k] != 0.0 for k in CTX_F1)]
    assert not bad, f"1R目でF1が中立でない: {bad[:3]}"
    print(f"✅ 当日1R目 {min(len(firsts),400)}件すべて F1=0(中立)")

    # 3) 3R目まで中立・4R目以降で発火(=MIN_DAY_RACES=3 の仕様通り)
    nz = sum(1 for f in files
             if os.path.basename(f)[10:12] >= "04"
             and idx.race_ctx(os.path.basename(f)[:-5])["tb_n"] >= 3)
    r3 = [os.path.basename(f)[:-5] for f in files if os.path.basename(f)[10:12] == "03"]
    assert all(idx.race_ctx(r)["tb_n"] <= 2 for r in r3), "3R目でtb_nが3以上"
    print(f"✅ 4R目以降で tb_n>=3 が {nz}件 / 3R目は必ず tb_n<=2")

    # 4) 値域
    lo = hi = None
    for rid, c in idx.ctx.items():
        for k in ("tb_waku", "tb_front", "tb_upset", "cp_waku", "cp_front", "cp_fav"):
            v = c[k]
            assert -1.5 <= v <= 1.5, f"{rid} {k}={v} が想定域外"
            lo = v if lo is None else min(lo, v)
            hi = v if hi is None else max(hi, v)
    print(f"✅ バイアス系の値域 [{lo:.3f}, {hi:.3f}] ⊂ [-1.5, 1.5]")

    # 5) as-of性: コーパス最古日のレースは F4 が全て0(それ以前のデータが存在しないのだから)
    first_date = min(idx.date.values())
    z = [r for r, dt in idx.date.items() if dt == first_date]
    assert all(idx.race_ctx(r)["cp_n"] == 0.0 for r in z), "最古日にコース累積が入っている=リーク"
    later = [r for r, dt in idx.date.items() if dt > first_date and idx.race_ctx(r)["cp_n"] > 0]
    print(f"✅ 最古日({first_date}) {len(z)}Rの F4 は全て0 / 以降 {len(later)}Rで累積あり")

    # 6) F2の値域と被覆(新馬戦は過去走が無いので被覆0が正常。全体で見る)
    tot = cov = 0
    for rid in list(idx.f2)[::7]:
        for v in idx.f2_of(rid).values():
            tot += 1
            cov += v["f2_wide_mean3"] is not None
            for k, x in v.items():
                assert x is None or -0.1 <= x <= 5.0, f"{rid} {k}={x} が想定域外"
    print(f"✅ F2: {tot}頭で値域OK・被覆 {cov/max(tot,1)*100:.1f}% (残りは新馬/未出走)")

    # 7) 同コース実績の被覆
    tot = cov = 0
    for f in files[::40]:
        d2 = json.load(open(f, encoding="utf-8"))
        for h in d2["race"]["horses"]:
            r = same_course_record(h, d2["race"])
            tot += 1
            cov += r["cs_top3"] is not None
    print(f"✅ 同コース実績(F4): {tot}頭で被覆 {cov/max(tot,1)*100:.1f}%")
    return idx


if __name__ == "__main__":
    _selftest()
