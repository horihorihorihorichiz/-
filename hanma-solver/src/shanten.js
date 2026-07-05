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

// 面子＋塔子の最大 value（head は含めない）。counts は破壊しない。
function bestMeldTaatsu(counts, calledMelds) {
  const c = counts.slice();
  let best = 0;
  function evaluate(mentsu, taatsu) {
    const total = mentsu + calledMelds;
    const val = 2 * Math.min(total, 4) + Math.min(taatsu, Math.max(0, 4 - total));
    if (val > best) best = val;
  }
  function rec(i, mentsu, taatsu) {
    while (i < N_TILES && c[i] === 0) i++;
    if (i >= N_TILES) { evaluate(mentsu, taatsu); return; }
    const inSuit = i < HONOR;
    const rank = i % 9; // 数牌スート内の位置 0-8
    // 刻子
    if (c[i] >= 3) { c[i] -= 3; rec(i, mentsu + 1, taatsu); c[i] += 3; }
    // 順子
    if (inSuit && rank <= 6 && c[i + 1] > 0 && c[i + 2] > 0) {
      c[i]--; c[i + 1]--; c[i + 2]--;
      rec(i, mentsu + 1, taatsu);
      c[i]++; c[i + 1]++; c[i + 2]++;
    }
    // 対子（塔子扱い）
    if (c[i] >= 2) { c[i] -= 2; rec(i, mentsu, taatsu + 1); c[i] += 2; }
    // 両面/辺張（隣接）
    if (inSuit && rank <= 7 && c[i + 1] > 0) {
      c[i]--; c[i + 1]--; rec(i, mentsu, taatsu + 1); c[i]++; c[i + 1]++;
    }
    // 嵌張（1つ飛び）
    if (inSuit && rank <= 6 && c[i + 2] > 0) {
      c[i]--; c[i + 2]--; rec(i, mentsu, taatsu + 1); c[i]++; c[i + 2]++;
    }
    // 浮き牌として1枚落とす
    c[i]--; rec(i, mentsu, taatsu); c[i]++;
  }
  rec(0, 0, 0);
  return best;
}

export function normalShanten(counts, calledMelds = 0) {
  let best = 8;
  // head なし
  best = Math.min(best, 8 - bestMeldTaatsu(counts, calledMelds));
  // 各対子を head に確保するパターン
  const c = counts.slice();
  for (let i = 0; i < N_TILES; i++) {
    if (c[i] >= 2) {
      c[i] -= 2;
      const sh = 8 - bestMeldTaatsu(c, calledMelds) - 1;
      if (sh < best) best = sh;
      c[i] += 2;
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
