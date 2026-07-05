// shanten.js — 向聴数（シャンテン）計算
//
// 韓麻のアガリ形: 4面子1雀頭 / 七対子 / 国士無双。
// 向聴数 = アガリまであと何枚有効牌を引けばテンパイになるかの手前の指標。
//   -1 = アガリ, 0 = テンパイ, 1 = 1向聴, ...
//
// counts[34] は「手の中の伏せ牌（暗牌）」の枚数。鳴いた面子は melds で枚数指定。
//
// 通常形の公式:
//   value = 2*mentsu + min(taatsu, 4 - mentsu)  （面子スロットは4つ）
//   head を1つ確保できれば -1 追加
//   shanten = 8 - value - (hasHead ? 1 : 0)
// mentsu には鳴いた面子（calledMelds）を含める。

import { N_TILES, HONOR, TERMINALS_AND_HONORS } from './tiles.js';

// ── 高速版: スート別に分解し、スート結果をメモ化して組み合わせる ──
// 各スートを独立に (melds, taatsu) のパレート集合へ分解 → 4スートを合成。
// 雀頭は「あるスートの対子を1つ抜いて head にする」パターンを別途試す。

const _suitMemo = new Map();

// スートの counts（長さ9 or 7）→ 到達可能な [melds, taatsu] のパレート集合
function suitFrontier(cnt, isHonor) {
  const key = (isHonor ? 'h' : 'n') + cnt.join(',');
  const cached = _suitMemo.get(key);
  if (cached) return cached;

  const L = cnt.length;
  const c = cnt.slice();
  const bestT = new Map(); // melds -> max taatsu
  function rec(i, m, t) {
    while (i < L && c[i] === 0) i++;
    if (i >= L) { const p = bestT.get(m); if (p === undefined || t > p) bestT.set(m, t); return; }
    if (c[i] >= 3) { c[i] -= 3; rec(i, m + 1, t); c[i] += 3; }                       // 刻子
    if (!isHonor && i <= L - 3 && c[i + 1] > 0 && c[i + 2] > 0) {                    // 順子
      c[i]--; c[i + 1]--; c[i + 2]--; rec(i, m + 1, t); c[i]++; c[i + 1]++; c[i + 2]++;
    }
    if (c[i] >= 2) { c[i] -= 2; rec(i, m, t + 1); c[i] += 2; }                       // 対子
    if (!isHonor && i <= L - 2 && c[i + 1] > 0) {                                    // 両面/辺張
      c[i]--; c[i + 1]--; rec(i, m, t + 1); c[i]++; c[i + 1]++;
    }
    if (!isHonor && i <= L - 3 && c[i + 2] > 0) {                                    // 嵌張
      c[i]--; c[i + 2]--; rec(i, m, t + 1); c[i]++; c[i + 2]++;
    }
    c[i]--; rec(i, m, t); c[i]++;                                                    // 浮き牌
  }
  rec(0, 0, 0);

  // パレート集合化（melds も taatsu も大きいほど良い）
  const pts = [...bestT.entries()].map(([m, t]) => [m, t]);
  const frontier = pts.filter(([m, t]) =>
    !pts.some(([m2, t2]) => (m2 > m && t2 >= t) || (m2 >= m && t2 > t)));
  _suitMemo.set(key, frontier);
  return frontier;
}

// 4スートのフロンティアを合成して最大 value を返す。baseM = 既定の面子数（鳴き）
function combineValue(frontiers, baseM) {
  let best = 0;
  function go(k, M, T) {
    if (k === frontiers.length) {
      const m = Math.min(M, 4);
      const v = 2 * m + Math.min(T, 4 - m);
      if (v > best) best = v;
      return;
    }
    for (const [m, t] of frontiers[k]) go(k + 1, M + m, T + t);
  }
  go(0, baseM, 0);
  return best;
}

export function normalShanten(counts, calledMelds = 0) {
  const suits = [counts.slice(0, 9), counts.slice(9, 18), counts.slice(18, 27), counts.slice(27, 34)];
  const isH = [false, false, false, true];
  const fr = suits.map((s, i) => suitFrontier(s, isH[i]));

  let best = 8 - combineValue(fr, calledMelds); // 雀頭なし
  // 雀頭を各スートの対子から確保
  for (let si = 0; si < 4; si++) {
    const s = suits[si];
    for (let r = 0; r < s.length; r++) {
      if (s[r] >= 2) {
        const s2 = s.slice(); s2[r] -= 2;
        const fr2 = fr.slice(); fr2[si] = suitFrontier(s2, isH[si]);
        const sh = 8 - (combineValue(fr2, calledMelds) + 1);
        if (sh < best) best = sh;
      }
    }
  }
  return best;
}

// 七対子（鳴きがあると不可）
export function chiitoiShanten(counts, calledMelds = 0) {
  if (calledMelds > 0) return Infinity;
  let pairs = 0, kinds = 0;
  for (let i = 0; i < N_TILES; i++) {
    if (counts[i] >= 1) kinds++;
    if (counts[i] >= 2) pairs++;
  }
  return 6 - pairs + Math.max(0, 7 - kinds);
}

// 国士無双（鳴きがあると不可）
export function kokushiShanten(counts, calledMelds = 0) {
  if (calledMelds > 0) return Infinity;
  let kinds = 0, hasPair = 0;
  for (const idx of TERMINALS_AND_HONORS) {
    if (counts[idx] >= 1) kinds++;
    if (counts[idx] >= 2) hasPair = 1;
  }
  return 13 - kinds - hasPair;
}

// 総合向聴数（3種の最小）と、どの形が最小かを返す
export function shanten(counts, calledMelds = 0) {
  const n = normalShanten(counts, calledMelds);
  const c = chiitoiShanten(counts, calledMelds);
  const k = kokushiShanten(counts, calledMelds);
  const min = Math.min(n, c, k);
  const forms = [];
  if (n === min) forms.push('normal');
  if (c === min) forms.push('chiitoi');
  if (k === min) forms.push('kokushi');
  return { value: min, normal: n, chiitoi: c, kokushi: k, forms };
}
