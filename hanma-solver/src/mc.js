// mc.js — モンテカルロによる打牌EV推定
//
// 韓麻は役が無いので、最適打はほぼ「アガリ率 × 打点」の期待値で決まる。
// 残り山からランダムに自摸り、貪欲な打牌方針でアガリまで回す試行を多数走らせ、
// アガリ率・平均打点・アガリEV を実測する。
//
// v1 の割り切り（docs参照）:
//  - 相手の手は未モデル化（放銃リスクは含めない = 「アガリ側EV」）。
//    相手の自摸切りに自分の当たり牌が出たらロン、という簡易ロンのみ考慮。
//  - 赤5は「アガリ時も手に残っている」と近似（5は中張で切られにくい）。
//  - 面前テンパイなら常にリーチ宣言したものとして加点（裏ドラは未計上）。

import { N_TILES, HONOR } from './tiles.js';
import { shanten } from './shanten.js';
import { countDora, score } from './score.js';

function shuffle(a) {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
}

// 切り牌選択の安手ヒューリスティック: 近接牌が少ない（孤立している）ほど切りやすい
function connectivity(counts, i) {
  if (i >= HONOR) return counts[i] * 3;
  let s = counts[i] * 3;
  const r = i % 9, base = i - r;
  for (const d of [-2, -1, 1, 2]) {
    const j = r + d;
    if (j >= 0 && j <= 8) s += counts[base + j] * (3 - Math.abs(d));
  }
  return s;
}

// 貪欲な打牌: 向聴が最小になる切り、同点なら最も孤立した牌
function chooseDiscard(counts, calledMelds) {
  let bestSh = Infinity, cand = [];
  for (let i = 0; i < N_TILES; i++) {
    if (counts[i] === 0) continue;
    counts[i]--;
    const sh = shanten(counts, calledMelds).value;
    counts[i]++;
    if (sh < bestSh) { bestSh = sh; cand = [i]; }
    else if (sh === bestSh) cand.push(i);
  }
  let pick = cand[0], pc = Infinity;
  for (const i of cand) { const c = connectivity(counts, i); if (c < pc) { pc = c; pick = i; } }
  return pick;
}

// テンパイ手の当たり牌 bool[34]
function winningTiles(counts, calledMelds, unseen) {
  const w = new Array(N_TILES).fill(false);
  for (let i = 0; i < N_TILES; i++) {
    if (counts[i] >= 4 || (unseen && unseen[i] <= 0)) continue;
    counts[i]++;
    if (shanten(counts, calledMelds).value === -1) w[i] = true;
    counts[i]--;
  }
  return w;
}

// 1つの打牌候補についてEVを推定
// opts: { hand13:Int[34], calledMelds, omoteIndicators, unseen:Int[34],
//         turnsLeft, rollouts, players }
export function monteCarloDiscard(opts) {
  const {
    hand13, calledMelds = 0, omoteIndicators = [],
    unseen, turnsLeft = 16, rollouts = 400, players = 4,
  } = opts;

  let wins = 0, tsumo = 0, ptsSum = 0, turnsToWinSum = 0;

  for (let n = 0; n < rollouts; n++) {
    const wall = [];
    for (let i = 0; i < N_TILES; i++) for (let k = 0; k < unseen[i]; k++) wall.push(i);
    shuffle(wall);

    const c = hand13.slice();
    let won = false, byTsumo = false, winCounts = null, winTurn = 0;
    let p = 0;

    for (let turn = 0; turn < turnsLeft && p < wall.length; turn++) {
      // 自摸
      const t = wall[p++]; c[t]++;
      if (shanten(c, calledMelds).value === -1) { won = true; byTsumo = true; winCounts = c.slice(); winTurn = turn; break; }
      const d = chooseDiscard(c, calledMelds); c[d]--;

      // テンパイならロン待ち
      const sh = shanten(c, calledMelds).value;
      if (sh === 0) {
        const wt = winningTiles(c, calledMelds, null);
        let ronned = false;
        for (let o = 0; o < players - 1 && p < wall.length; o++) {
          const od = wall[p++];
          if (wt[od]) { c[od]++; won = true; byTsumo = false; winCounts = c.slice(); c[od]--; winTurn = turn; ronned = true; break; }
        }
        if (ronned) break;
      } else {
        p += (players - 1); // 相手の自摸切りぶん山を消費（テンパイでなければ無関係）
      }
    }

    if (won) {
      wins++; if (byTsumo) tsumo++; turnsToWinSum += winTurn;
      const dora = countDora(winCounts, omoteIndicators, [], false);
      const menzen = calledMelds === 0;
      const s = score({ win: byTsumo ? 'tsumo' : 'ron', riichi: menzen, dora, players });
      ptsSum += s.total;
    }
  }

  const winRate = wins / rollouts;
  const avgPoints = wins ? ptsSum / wins : 0;
  return {
    winRate,
    tsumoRate: tsumo / rollouts,
    avgPoints,
    ev: winRate * avgPoints,
    avgWinTurn: wins ? turnsToWinSum / wins : null,
    rollouts,
  };
}
