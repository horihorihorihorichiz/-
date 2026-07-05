// score.js — 韓麻の点数計算（差し替え可能なモジュール）
//
// 仕様は docs/rules.md 準拠。粗品「四兄弟韓国麻雀#21-1」(11:00-18:30) で実地確認済み。
//
// 基礎点:
//   ロン … 放銃者が 6点 支払い（1人）
//   ツモ … 全員が 2点ずつ 支払い（4人打ちなら計6点）
// 加点:
//   ドラ … 1枚 +1点（各支払いに加算 = ツモは各人に+1、ロンは放銃者に+1）
//   リーチ … +2点。ただし「合計に1回だけ」乗る（フラット）。
//            → ツモ計8点 / ロン計8点 になるのはこのため（2×3+2 = 8, 6+2 = 8）
//   国士無双 … 20点（各支払い）
// 上限:
//   1人の最大支払い = 20点（基礎+ドラ部分。ロンは放銃者の総額、ツモは各人の額）

import { doraFromIndicator } from './tiles.js';

export const CONFIG = {
  ronBase: 6,      // ロン基礎点（放銃者が支払う）
  tsumoBase: 2,    // ツモ基礎点（各人が支払う）
  perDora: 1,      // ドラ1枚あたり（各支払いに加算）
  riichi: 2,       // リーチ加点（合計に1回、フラット）
  kokushi: 20,     // 国士無双（各支払い）
  cap: 20,         // 1人あたり最大支払い（基礎+ドラ部分）
  // ⚠️ 未確認: ツモ時のドラが「各人+1」か「合計+1」か（動画未言及）。既定は各人+1。
  // ⚠️ 未確認: 3人打ちの精算、赤5と表ドラの重複計上。
};

// 手牌14枚(counts) から ドラ総数を数える
// omoteIndicators / uraIndicators: ドラ表示牌インデックスの配列
// akaCount: 手牌に含まれる赤5の枚数
export function countDora(counts, akaCount, omoteIndicators = [], uraIndicators = [], useUra = false) {
  let dora = 0;
  const add = (indicators) => {
    for (const ind of indicators) dora += counts[doraFromIndicator(ind)] || 0;
  };
  add(omoteIndicators);
  if (useUra) add(uraIndicators);
  dora += akaCount; // 全赤ドラ
  return dora;
}

// アガリの点数を計算
// opts: { win:'ron'|'tsumo', riichi:bool, dora:int, kokushi:bool, players:3|4 }
// 返り値: { total, perPayer, numPayers, riichiAdd, breakdown, capped }
export function score(opts) {
  const { win, riichi = false, dora = 0, kokushi = false, players = 4 } = opts;
  const numPayers = win === 'ron' ? 1 : players - 1;
  const breakdown = [];

  // 1人あたりの基礎+ドラ（上限20）
  let perRaw;
  if (kokushi) {
    perRaw = CONFIG.kokushi;
    breakdown.push(['国士無双', CONFIG.kokushi]);
  } else {
    const base = win === 'ron' ? CONFIG.ronBase : CONFIG.tsumoBase;
    perRaw = base + dora * CONFIG.perDora;
    breakdown.push([win === 'ron' ? 'ロン' : 'ツモ', base]);
    if (dora > 0) breakdown.push([`ドラ${dora}`, dora * CONFIG.perDora]);
  }
  const perPayer = Math.min(perRaw, CONFIG.cap);

  let total = perPayer * numPayers;

  // リーチはフラットで合計に1回だけ加算（国士には付かない想定）
  let riichiAdd = 0;
  if (riichi && !kokushi) {
    riichiAdd = CONFIG.riichi;
    total += riichiAdd;
    breakdown.push(['リーチ', riichiAdd]);
  }

  return {
    total,               // 獲得点数（合計）
    points: total,       // 互換エイリアス
    perPayer,            // 1人あたり支払い（基礎+ドラ、上限適用後）
    numPayers,
    riichiAdd,
    breakdown,
    capped: perRaw > CONFIG.cap,
  };
}
