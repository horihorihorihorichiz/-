// analyze.js — 打牌解析（14枚から何を切るべきか）
//
// スノーウィー的な「打牌アドバイザー」の中核。
// 14枚（暗牌 counts + 赤 aka{m,p,s} + 鳴き calledMelds）に対し、
// 切れる各牌について「切った後の向聴・受け入れ・ドラ・赤ロス」を計算し、
// 良い順（向聴↑ → 受け入れ↑ → ドラ↑ → 赤温存）に並べて返す。

import { N_TILES, tileName, rankOf, suitOf, MAN, PIN, SOU } from './tiles.js';
import { shanten } from './shanten.js';
import { ukeire } from './ukeire.js';
import { countDora } from './score.js';

const FIVE = { m: MAN + 4, p: PIN + 4, s: SOU + 4 };

function akaTotal(aka) { return (aka.m || 0) + (aka.p || 0) + (aka.s || 0); }

// opts: { counts, aka:{m,p,s}, calledMelds, omoteIndicators, uraIndicators, seen }
export function analyzeDiscards(opts) {
  const {
    counts, aka = { m: 0, p: 0, s: 0 }, calledMelds = 0,
    omoteIndicators = [], uraIndicators = [], seen = null,
  } = opts;

  const results = [];
  for (let i = 0; i < N_TILES; i++) {
    if (counts[i] <= 0) continue;
    const c = counts.slice();
    c[i]--;

    // 赤5を切らざるを得ないか判定（通常5が無ければ赤が減る）
    let akaAfter = { ...aka };
    let discardsRed = false;
    const suit = suitOf(i);
    if (i < 27 && rankOf(i) === 5 && aka[suit] > 0) {
      const normalFives = counts[i] - aka[suit];
      if (normalFives <= 0) { akaAfter[suit] = aka[suit] - 1; discardsRed = true; }
    }

    const uk = ukeire(c, calledMelds, seen);
    const dora = countDora(c, akaTotal(akaAfter), omoteIndicators, uraIndicators, false);

    results.push({
      discard: i,
      discardName: tileName(i),
      discardsRed,
      shanten: uk.shanten,
      ukeireTotal: uk.total,
      ukeireTiles: uk.tiles.map(t => ({ name: tileName(t.idx), count: t.count, idx: t.idx })),
      dora,
    });
  }

  // 並べ替え: 向聴↑ → 受け入れ↑ → ドラ↑ → 赤を切らない
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
