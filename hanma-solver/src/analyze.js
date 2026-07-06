// analyze.js — 打牌解析（14枚から何を切るべきか）
//
// スノーウィー的な「打牌アドバイザー」の中核。
// 14枚（暗牌 counts + 鳴き calledMelds）に対し、切れる各牌について
// 「切った後の向聴・受け入れ・ドラ」を計算し、良い順に並べて返す。
// 韓麻は5が全部赤ドラなので、5を切るとドラを1枚失う（discardsFive で警告）。

import { N_TILES, tileName, rankOf, suitOf } from './tiles.js';
import { shanten } from './shanten.js';
import { ukeire } from './ukeire.js';
import { countDora } from './score.js';

function isFive(idx) { return idx < 27 && rankOf(idx) === 5; }

// opts: { counts, calledMelds, omoteIndicators, uraIndicators, seen }
export function analyzeDiscards(opts) {
  const {
    counts, calledMelds = 0,
    omoteIndicators = [], uraIndicators = [], seen = null,
  } = opts;

  const results = [];
  for (let i = 0; i < N_TILES; i++) {
    if (counts[i] <= 0) continue;
    const c = counts.slice();
    c[i]--;

    const uk = ukeire(c, calledMelds, seen);
    const shInfo = shanten(c, calledMelds); // 狙える形（通常/七対子/国士）
    const dora = countDora(c, omoteIndicators, uraIndicators, false);

    results.push({
      discard: i,
      discardName: tileName(i),
      discardsRed: isFive(i), // 5切り=赤ドラを1枚失う
      shanten: uk.shanten,
      forms: shInfo.forms,     // ['normal'|'chiitoi'|'kokushi', ...]
      ukeireTotal: uk.total,
      ukeireTiles: uk.tiles.map(t => ({ name: tileName(t.idx), count: t.count, idx: t.idx })),
      dora,
    });
  }

  // 並べ替え: 向聴↑ → 受け入れ↑ → ドラ↑ → 赤(5)を切らない
  results.sort((a, b) =>
    a.shanten - b.shanten ||
    b.ukeireTotal - a.ukeireTotal ||
    b.dora - a.dora ||
    (a.discardsRed - b.discardsRed)
  );

  const best = results[0];
  for (const r of results) {
    r.isBest =
      r.shanten === best.shanten &&
      r.ukeireTotal === best.ukeireTotal &&
      !r.discardsRed === !best.discardsRed;
    r.ukeireLoss = best.shanten === r.shanten ? best.ukeireTotal - r.ukeireTotal : null;
  }
  return results;
}
