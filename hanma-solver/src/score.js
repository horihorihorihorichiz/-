// score.js — 韓麻の点数計算（差し替え可能なモジュール）
//
// 仕様は docs/rules.md 準拠。ソース間で揺れている項目は CONFIG で切替可能にしてある。
// 点数 = 基礎点(ロン/ツモ) + リーチ + ドラ枚数 + (国士は固定20)。
// 精算額は 点数 × レート で、UI 側で掛ける。

import { doraFromIndicator } from './tiles.js';

export const CONFIG = {
  ron: 6,          // ロン基礎点
  tsumo: 2,        // ツモ基礎点
  riichi: 2,       // リーチ加点（既定: ツモ・ロン問わず加算）
  perDora: 1,      // ドラ1枚あたり（表・裏・赤 共通）
  kokushi: 20,     // 国士無双 固定
  cap: 20,         // 1人1局あたり支払い上限
  riichiOnTsumo: true,   // ⚠️要確認: ツモ時にリーチ+2を乗せるか
  allowAkaOmoteStack: true, // ⚠️要確認: 赤5が表ドラと重なった時に重複計上するか
};

// 手牌14枚(counts) + 赤枚数 + ドラ表示牌配列 から ドラ総数を数える
// omoteIndicators / uraIndicators: ドラ表示牌インデックスの配列
// akaCount: 手牌に含まれる赤5の枚数
export function countDora(counts, akaCount, omoteIndicators = [], uraIndicators = [], useUra = false) {
  let dora = 0;
  const add = (indicators) => {
    for (const ind of indicators) {
      const d = doraFromIndicator(ind);
      dora += counts[d] || 0;
    }
  };
  add(omoteIndicators);
  if (useUra) add(uraIndicators);
  dora += akaCount; // 赤ドラ
  // allowAkaOmoteStack=false の場合、赤5が表ドラでもある分を1回に抑える調整は
  // 呼び出し側で必要になるが、既定(true)では単純合算。
  return dora;
}

// アガリの点数を計算
// opts: { win:'ron'|'tsumo', riichi:bool, dora:int, kokushi:bool, players:3|4 }
// 返り値: { points, breakdown, perPayer, totalGain }
export function score(opts) {
  const { win, riichi = false, dora = 0, kokushi = false, players = 4 } = opts;
  const breakdown = [];
  let points;

  if (kokushi) {
    points = CONFIG.kokushi;
    breakdown.push(['国士無双', CONFIG.kokushi]);
  } else {
    const base = win === 'ron' ? CONFIG.ron : CONFIG.tsumo;
    points = base;
    breakdown.push([win === 'ron' ? 'ロン' : 'ツモ', base]);
    if (riichi && (win === 'ron' || CONFIG.riichiOnTsumo)) {
      points += CONFIG.riichi;
      breakdown.push(['リーチ', CONFIG.riichi]);
    }
    if (dora > 0) {
      points += dora * CONFIG.perDora;
      breakdown.push([`ドラ${dora}`, dora * CONFIG.perDora]);
    }
  }

  const capped = Math.min(points, CONFIG.cap);
  const numPayers = win === 'ron' ? 1 : (players - 1);
  const perPayer = capped;               // ツモは全員同額（親子区別なし）
  const totalGain = perPayer * numPayers;

  return {
    points: capped,
    raw: points,
    capped: points > CONFIG.cap,
    breakdown,
    perPayer,
    numPayers,
    totalGain,
  };
}
