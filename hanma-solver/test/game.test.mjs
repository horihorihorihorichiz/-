// 対局エンジンの自動対局テスト: node hanma-solver/test/game.test.mjs
import { newGame, advance, humanAnkan, humanShouminkan, ankanOptions } from '../src/game.js';

let pass = 0, fail = 0;
function ok(name, cond) { console.log(`${cond ? '✅' : '❌'} ${name}`); cond ? pass++ : fail++; }

function playAuto(players) {
  const state = newGame({ players, humanIndex: -1 }); // 人間なし = 全AI
  advance(state);
  return state;
}

let wins = 0, draws = 0, kokushi = 0, riichiWins = 0, maxPts = 0;
let scoreImbalance = 0, badHand = 0, notOver = 0, exceptions = 0;
const N = 400;
for (let i = 0; i < N; i++) {
  let st;
  try { st = playAuto(i % 2 === 0 ? 4 : 3); }
  catch (e) { exceptions++; if (exceptions <= 3) console.log('EXC:', e.message); continue; }

  if (st.phase !== 'over' || !st.result) { notOver++; continue; }
  // 点数収支は0
  const sum = st.scores.reduce((a, b) => a + b, 0);
  if (sum !== 0) scoreImbalance++;
  // 各家の牌数整合: concealed + melds*3 が 13（打牌後）
  for (let p = 0; p < st.players; p++) {
    const conceal = st.hands[p].reduce((a, b) => a + b, 0);
    const total = conceal + st.melds[p].length * 3;
    if (total !== 13 && total !== 14) badHand++;
  }
  if (st.result.type === 'win') {
    wins++;
    if (st.result.kokushi) kokushi++;
    if (st.result.riichi) riichiWins++;
    maxPts = Math.max(maxPts, st.result.points);
  } else draws++;
}

console.log(`\n対局 ${N}: アガリ${wins} 流局${draws} / 例外${exceptions} 未終了${notOver}`);
console.log(`  リーチアガリ${riichiWins} 国士${kokushi} 最高打点${maxPts}`);
ok('全対局が例外なく終了', exceptions === 0 && notOver === 0);
ok('点数収支が常に0', scoreImbalance === 0);
ok('牌数整合が常に正しい', badHand === 0);
ok('アガリが発生している', wins > 0);
ok('流局も発生しうる（>=0）', draws >= 0);
ok('最高打点が上限20以下×人数の範囲', maxPts > 0 && maxPts <= 60);

// ── カン（暗槓）の機構テスト ──
{
  const st = newGame({ players: 4, humanIndex: 0 });
  advance(st); // 人間の打牌手番へ
  // 手牌に4枚ある牌を用意（テスト用に強制）
  const tile = 4; // 5m
  st.hands[0] = new Array(34).fill(0);
  st.hands[0][tile] = 4; // 5m×4
  st.hands[0][9] = 3; st.hands[0][12] = 3; st.hands[0][27] = 2; st.hands[0][30] = 2; // 適当に埋める
  st.phase = 'discard'; st.turn = 0; st.drawnTile = tile; st.waiting = { type: 'discard' };
  const opts = ankanOptions(st);
  ok('暗槓候補に5mが出る', opts.includes(tile));
  const before = st.kansDone, ptrBefore = st.rinshanPointer;
  humanAnkan(st, tile);
  ok('暗槓後 面子に ankan が入る', st.melds[0].some(m => m.type === 'ankan' && m.tile === tile));
  ok('暗槓後 kansDone +1', st.kansDone === before + 1);
  ok('暗槓後 嶺上ポインタ +1', st.rinshanPointer === ptrBefore + 1);
  ok('暗槓後 嶺上牌を自摸（drawnTile あり）', st.drawnTile != null);
}

// ── カン（加槓）の機構テスト ──
{
  const st = newGame({ players: 4, humanIndex: 0 });
  advance(st);
  const tile = 13; // 5p
  st.hands[0] = new Array(34).fill(0);
  st.hands[0][tile] = 1;
  st.hands[0][0] = 3; st.hands[0][3] = 3; st.hands[0][27] = 3; st.hands[0][30] = 2;
  st.melds[0] = [{ type: 'pon', tile, from: 1 }];
  st.phase = 'discard'; st.turn = 0; st.drawnTile = tile; st.waiting = { type: 'discard' };
  humanShouminkan(st, tile);
  ok('加槓後 ポンが shouminkan に昇格', st.melds[0].some(m => m.type === 'shouminkan' && m.tile === tile));
  ok('加槓後 嶺上牌を自摸', st.drawnTile != null && st.kansDone === 1);
}

console.log(`\n=== ${pass} passed, ${fail} failed ===`);
process.exit(fail ? 1 : 0);
