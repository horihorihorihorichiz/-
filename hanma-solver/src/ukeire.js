// ukeire.js — 受け入れ（有効牌）計算
//
// 手牌（暗牌 counts、鳴き calledMelds）が 3k+1 枚（13枚など）の状態で、
// 「引くと向聴数が下がる牌」の種類と枚数を求める。
// 枚数は 4 - (手牌内の枚数) - (場に見えている枚数) で計算。

import { N_TILES } from './tiles.js';
import { shanten } from './shanten.js';

// seen[34] = 場に見えている枚数（自分の手牌以外。ドラ表示・河・自分の副露牌など）。省略可。
export function ukeire(counts, calledMelds = 0, seen = null) {
  const cur = shanten(counts, calledMelds).value;
  const tiles = [];
  let total = 0;
  const c = counts.slice();
  for (let i = 0; i < N_TILES; i++) {
    const used = c[i] + (seen ? seen[i] : 0);
    if (used >= 4) continue;         // もう引けない
    if (c[i] >= 4) continue;
    c[i]++;
    const after = shanten(c, calledMelds).value;
    c[i]--;
    if (after < cur) {
      const avail = 4 - used;
      tiles.push({ idx: i, count: avail });
      total += avail;
    }
  }
  return { shanten: cur, tiles, total };
}
