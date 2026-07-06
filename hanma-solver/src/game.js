// game.js — 韓麻の対局エンジン（ヘッドレス）
//
// 実装範囲(v1): 配牌・自摸・打牌・ポン・ツモ・ロン・リーチ・表/裏ドラ・点数・流局。
//   - チーなし（韓麻）、カンは v1 では未実装（次段）。
//   - 役なしでアガれる。フリテンなし（現物でもロン可）。
//   - 5は全部赤ドラ。ロンはダブロン時 頭ハネ（放銃者の下家側から近い者）。
//
// UI からは advance(state) を呼び、state.waiting に人間の入力要求が入ったら停止する。
// 人間の操作: humanDiscard / humanCall。

import { N_TILES, MAN, PIN, SOU, HONOR } from './tiles.js';
import { shanten } from './shanten.js';
import { score, countDora } from './score.js';

function shuffle(a) {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function emptyCounts() { return new Array(N_TILES).fill(0); }

// 全牌136枚（各4枚）
function buildWall() {
  const w = [];
  for (let i = 0; i < N_TILES; i++) for (let k = 0; k < 4; k++) w.push(i);
  return shuffle(w);
}

// concealed counts + melds から「全14枚相当」の counts を作る（ドラ計算用）
function fullCounts(hand, melds) {
  const c = hand.slice();
  for (const m of melds) c[m.tile] += (m.type === 'pon' ? 3 : 4); // カンは4枚
  return c;
}

// 面前を崩す（開いた）副露の数。暗槓は面前を保つ。
function openMelds(melds) { return melds.filter(m => m.type !== 'ankan').length; }

export function newGame(opts = {}) {
  const players = opts.players || 4;
  const humanIndex = opts.humanIndex ?? 0;
  const wall = buildWall();

  const deadWall = wall.splice(wall.length - 14, 14); // 王牌14枚
  const doraIndicators = [deadWall[0], deadWall[1]];  // 表ドラ2枚（カンドラは増やさない）
  const uraIndicators = [deadWall[2], deadWall[3]];   // 裏ドラ2枚（リーチ時のみ開示）

  const hands = [], melds = [], discards = [], riichi = [];
  for (let p = 0; p < players; p++) {
    hands.push(emptyCounts()); melds.push([]); discards.push([]); riichi.push(false);
    // riichiAt[p] は後段でまとめて初期化
    for (let k = 0; k < 13; k++) hands[p][wall.shift()]++;
  }

  const state = {
    players, humanIndex,
    hands, melds, discards, riichi,
    scores: new Array(players).fill(0),
    riichiAt: new Array(players).fill(-1), // リーチ宣言した河のインデックス
    pot: 0,                // リーチ供託
    wall,
    deadWall,
    doraIndicators, uraIndicators,
    rinshanPointer: 4,     // 王牌の嶺上牌ポインタ（0-3はドラ表示）
    kansDone: 0,           // 全員のカン回数（最大4）
    turn: 0,               // 東家=0 から
    drawnTile: null,
    lastDiscard: null,     // { tile, from }
    phase: 'draw',
    waiting: null,         // 人間の入力要求 { type:'discard' } | { type:'calls', options }
    log: [],
    result: null,          // { type:'win'|'draw', ... }
    riichiJustDeclared: -1,
  };
  return state;
}

// 手番 p が牌 t を加えてアガリ形か（t=null なら現在の手牌のまま）
function isWin(state, p, t = null) {
  const c = state.hands[p];
  if (t != null) c[t]++;
  const w = shanten(c, state.melds[p].length).value === -1;
  if (t != null) c[t]--;
  return w;
}

// テンパイ（アガリ牌が存在）か
function isTenpai(state, p) {
  return shanten(state.hands[p], state.melds[p].length).value === 0;
}

// p がロンできる牌か（フリテン無しなので河は無関係）
function canRon(state, p, tile) {
  return isWin(state, p, tile);
}

// p が tile をポンできるか（手牌に2枚以上、かつリーチしていない）
function canPon(state, p, tile) {
  return !state.riichi[p] && state.hands[p][tile] >= 2;
}

function nextPlayer(state, p) { return (p + 1) % state.players; }

// ── 内部: ドロー ──
// 自摸後の共通処理（ツモ判定 → 人間なら待ち、AIなら自動）
function afterDraw(state) {
  state.phase = 'discard';
  if (isWin(state, state.turn, null)) {
    if (state.turn === state.humanIndex) {
      state.waiting = { type: 'calls', options: [{ action: 'tsumo' }, { action: 'discardAny' }] };
    } else {
      resolveWin(state, state.turn, null, 'tsumo');
    }
    return;
  }
  state.waiting = state.turn === state.humanIndex ? { type: 'discard' } : null;
}

function doDraw(state) {
  if (state.wall.length === 0) { endDraw(state); return; }
  const t = state.wall.shift();
  state.hands[state.turn][t]++;
  state.drawnTile = t;
  afterDraw(state);
}

// 嶺上牌を引く（カン後）。王牌から取り、山末尾を1枚 dead wall へ回して枚数調整。
function drawRinshan(state, p) {
  const t = state.deadWall[state.rinshanPointer++];
  state.hands[p][t]++;
  state.drawnTile = t;
  if (state.wall.length > 0) state.wall.pop();
  state.kansDone++;
  state.turn = p;
  afterDraw(state);
}

// ── 打牌 ──
function doDiscard(state, p, tile) {
  state.hands[p][tile]--;
  state.discards[p].push(tile);
  state.drawnTile = null;
  state.lastDiscard = { tile, from: p };
  if (state.riichiJustDeclared === p) {
    state.riichi[p] = true;
    state.riichiAt[p] = state.discards[p].length - 1; // この河でリーチ宣言
    state.scores[p] -= 2;   // リーチ棒を供託
    state.pot += 2;
    state.riichiJustDeclared = -1;
  }
  resolveCalls(state);
}

// 打牌後: 他家のロン/ポンを集計
function resolveCalls(state) {
  const { players } = state;
  const from = state.lastDiscard.from;
  const tile = state.lastDiscard.tile;

  // ロン候補（頭ハネ: 放銃者の下家から順に最初の1人）
  const ronners = [];
  for (let k = 1; k < players; k++) {
    const p = (from + k) % players;
    if (canRon(state, p, tile)) ronners.push(p);
  }
  // ポン候補
  const ponners = [];
  for (let p = 0; p < players; p++) {
    if (p !== from && canPon(state, p, tile)) ponners.push(p);
  }

  // 人間が関与する選択があるか（大明槓は人間のみ v1）
  const h = state.humanIndex;
  const humanRon = ronners.includes(h);
  const humanPon = ponners.includes(h);
  const humanKan = h >= 0 && from !== h && state.hands[h][tile] === 3 &&
    !state.riichi[h] && state.kansDone < 4 && state.wall.length > 0;

  if (humanRon || humanPon || humanKan) {
    const options = [];
    if (humanRon) options.push({ action: 'ron' });
    if (humanKan) options.push({ action: 'kan' });
    if (humanPon) options.push({ action: 'pon' });
    options.push({ action: 'skip' });
    state.waiting = { type: 'calls', options, tile, from };
    state._pendingRonners = ronners;
    state._pendingPonners = ponners;
    return;
  }

  // 人間が絡まない → AI で解決
  finishCalls(state, ronners, ponners, null);
}

// AI/人間の選択を反映して打牌後処理を確定
function finishCalls(state, ronners, ponners, humanChoice) {
  const tile = state.lastDiscard.tile;
  const from = state.lastDiscard.from;

  // ロン優先（頭ハネ = ronners の先頭）
  const ron = ronners.filter(p => p !== state.humanIndex || humanChoice === 'ron');
  // 人間がロンを見送った場合は除外済み（呼び出し側で調整）
  if (ron.length > 0) { resolveWin(state, ron[0], tile, 'ron'); return; }

  // 大明槓（人間が選んだ場合のみ）
  if (humanChoice === 'kan') { doDaiminkan(state, state.humanIndex, tile, from); return; }

  // ポン（人間が選んだ or AI がポン方針を満たす）
  let ponner = -1;
  if (humanChoice === 'pon') ponner = state.humanIndex;
  else {
    for (const p of ponners) {
      if (p === state.humanIndex) continue;
      if (aiWantsPon(state, p, tile)) { ponner = p; break; }
    }
  }
  if (ponner >= 0) { doPon(state, ponner, tile, from); return; }

  // 誰も鳴かない → 次の手番へ
  state.turn = nextPlayer(state, from);
  state.phase = 'draw';
  state.waiting = null;
}

// ポン実行 → ponner の打牌へ
function doPon(state, p, tile, from) {
  state.hands[p][tile] -= 2;
  state.melds[p].push({ type: 'pon', tile, from });
  // 直前の河から鳴いた牌を取り除く（表示上）
  const dfrom = state.discards[from];
  if (dfrom[dfrom.length - 1] === tile) dfrom.pop();
  state.turn = p;
  state.phase = 'discard';
  state.lastDiscard = null;
  if (p === state.humanIndex) state.waiting = { type: 'discard' };
  else state.waiting = null;
}

// 大明槓実行 → 嶺上ツモ → その者の打牌へ
function doDaiminkan(state, p, tile, from) {
  state.hands[p][tile] -= 3;
  state.melds[p].push({ type: 'daiminkan', tile, from });
  const dfrom = state.discards[from];
  if (dfrom[dfrom.length - 1] === tile) dfrom.pop();
  state.lastDiscard = null;
  drawRinshan(state, p); // turn=p, 嶺上ツモ判定含む
}

// AI がポンするか（v1: ポンでテンパイになるなら鳴く）
function aiWantsPon(state, p, tile) {
  const c = state.hands[p].slice();
  c[tile] -= 2;
  const shAfter = shanten(c, state.melds[p].length + 1).value;
  return shAfter <= 0; // テンパイ or アガリ相当
}

// ── アガリ処理 ──
function resolveWin(state, winner, tile, kind) {
  const hand = state.hands[winner].slice();
  if (kind === 'tsumo' && state.drawnTile != null) {
    // drawnTile は既に hand に入っている
  } else if (kind === 'ron') {
    hand[tile]++;
  }
  const full = fullCounts(hand, state.melds[winner]);
  const useUra = state.riichi[winner];
  const dora = countDora(full, state.doraIndicators, state.uraIndicators, useUra);
  const shInfo = shanten(hand, state.melds[winner].length);
  const kokushi = state.melds[winner].length === 0 && shInfo.kokushi === -1;
  // 支払いは基礎+ドラのみ（リーチ分は供託の回収で表現し、ゼロサムを保つ）
  const s = score({ win: kind, riichi: false, dora, kokushi, players: state.players });

  // 精算（deltas は「このアガリ処理での増減」。リーチ供託は既に宣言時に各自から引かれている）
  const deltas = new Array(state.players).fill(0);
  if (kind === 'ron') {
    deltas[winner] += s.total;
    deltas[state.lastDiscard.from] -= s.total;
  } else {
    deltas[winner] += s.total;
    for (let p = 0; p < state.players; p++) if (p !== winner) deltas[p] -= s.perPayer;
  }
  const potGain = state.pot;
  deltas[winner] += potGain;         // 供託（リーチ棒）を総取り
  state.pot = 0;
  for (let p = 0; p < state.players; p++) state.scores[p] += deltas[p];

  state.phase = 'over';
  state.waiting = null;
  state.result = {
    type: 'win', winner, kind, tile,
    points: s.total, perPayer: s.perPayer, breakdown: s.breakdown,
    dora, riichi: state.riichi[winner], kokushi,
    potGain, totalGain: s.total + potGain,
    deltas, hand: full,
    winTile: kind === 'ron' ? tile : state.drawnTile,
  };
}

function endDraw(state) {
  state.phase = 'over';
  state.waiting = null;
  const tenpai = [];
  for (let p = 0; p < state.players; p++) if (isTenpai(state, p)) tenpai.push(p);
  // 流局: 供託リーチ棒は各宣言者に返却（ゼロサム維持。次局持ち越しは扱わない）
  for (let p = 0; p < state.players; p++) if (state.riichi[p]) state.scores[p] += 2;
  state.pot = 0;
  state.result = { type: 'draw', tenpai };
}

// ── AI 打牌方針（向聴最小→孤立牌）──
function connectivity(counts, i) {
  if (i >= HONOR) return counts[i] * 3;
  let s = counts[i] * 3;
  const r = i % 9, base = i - r;
  for (const d of [-2, -1, 1, 2]) { const j = r + d; if (j >= 0 && j <= 8) s += counts[base + j] * (3 - Math.abs(d)); }
  return s;
}
function aiChooseDiscard(state, p) {
  const c = state.hands[p];
  const called = state.melds[p].length;
  // リーチ中は自摸切り
  if (state.riichi[p]) return state.drawnTile;
  let bestSh = Infinity, cand = [];
  for (let i = 0; i < N_TILES; i++) {
    if (c[i] === 0) continue;
    c[i]--; const sh = shanten(c, called).value; c[i]++;
    if (sh < bestSh) { bestSh = sh; cand = [i]; } else if (sh === bestSh) cand.push(i);
  }
  let pick = cand[0], pc = Infinity;
  for (const i of cand) { const v = connectivity(c, i); if (v < pc) { pc = v; pick = i; } }
  return pick;
}

// AI がリーチするか（面前・テンパイ・未リーチ・山に余裕）
function aiWantsRiichi(state, p) {
  return openMelds(state.melds[p]) === 0 && !state.riichi[p] && isTenpai(state, p) && state.wall.length >= 4;
}

// ── 進行: 人間の入力が要るところまで自動で進める ──
export function advance(state) {
  let guard = 0;
  while (state.phase !== 'over' && guard++ < 10000) {
    if (state.phase === 'draw') {
      doDraw(state);
      if (state.waiting) return state; // 人間のツモ/打牌待ち
      // ツモ/ドローで over になったら抜ける
      if (state.phase === 'over') return state;
      // AI の打牌
      if (state.phase === 'discard' && state.turn !== state.humanIndex) {
        aiTurn(state);
        if (state.phase === 'over' || state.waiting) return state;
      }
    } else if (state.phase === 'discard') {
      if (state.turn === state.humanIndex) { state.waiting = { type: 'discard' }; return state; }
      aiTurn(state);
      if (state.phase === 'over' || state.waiting) return state;
    } else {
      return state;
    }
  }
  return state;
}

// AI の1手番（打牌 → 鳴き解決まで）
function aiTurn(state) {
  const p = state.turn;
  if (aiWantsRiichi(state, p)) state.riichiJustDeclared = p;
  const tile = aiChooseDiscard(state, p);
  doDiscard(state, p, tile);
}

// ── UI 補助 ──
export function tenpaiAfterDiscard(state, p, tile) {
  const c = state.hands[p];
  if (c[tile] <= 0) return false;
  c[tile]--;
  const t = shanten(c, state.melds[p].length).value === 0;
  c[tile]++;
  return t;
}
export function canDeclareRiichi(state) {
  const p = state.humanIndex;
  return state.phase === 'discard' && state.turn === p &&
    openMelds(state.melds[p]) === 0 && !state.riichi[p] &&
    state.wall.length >= 4 && shanten(state.hands[p], state.melds[p].length).value === 0;
}

// ── カン（人間）──
// 暗槓できる牌（手牌に4枚）。リーチ中は不可（v1）。
export function ankanOptions(state) {
  const p = state.humanIndex;
  if (state.phase !== 'discard' || state.turn !== p || state.riichi[p] ||
    state.kansDone >= 4 || state.wall.length === 0) return [];
  const out = [];
  for (let i = 0; i < N_TILES; i++) if (state.hands[p][i] === 4) out.push(i);
  return out;
}
// 加槓できる牌（自分のポンに手牌の1枚を足す）
export function shouminkanOptions(state) {
  const p = state.humanIndex;
  if (state.phase !== 'discard' || state.turn !== p || state.riichi[p] ||
    state.kansDone >= 4 || state.wall.length === 0) return [];
  const out = [];
  for (const m of state.melds[p]) if (m.type === 'pon' && state.hands[p][m.tile] >= 1) out.push(m.tile);
  return out;
}
export function humanAnkan(state, tile) {
  const p = state.humanIndex;
  if (state.hands[p][tile] !== 4) return state;
  state.hands[p][tile] -= 4;
  state.melds[p].push({ type: 'ankan', tile });
  drawRinshan(state, p);
  return state; // 人間の手番のまま（打牌 or 再カン / 嶺上ツモ待ち）
}
export function humanShouminkan(state, tile) {
  const p = state.humanIndex;
  const meld = state.melds[p].find(m => m.type === 'pon' && m.tile === tile);
  if (!meld || state.hands[p][tile] < 1) return state;
  state.hands[p][tile] -= 1;
  meld.type = 'shouminkan';
  drawRinshan(state, p);
  return state;
}

// ── 人間の操作 ──
export function humanDiscard(state, tile) {
  if (state.phase !== 'discard' || state.turn !== state.humanIndex) return state;
  if (state.hands[state.humanIndex][tile] <= 0) return state;
  doDiscard(state, state.humanIndex, tile);
  return advance(state);
}

export function humanRiichiDiscard(state, tile) {
  if (state.melds[state.humanIndex].length === 0 && isTenpai(state, state.humanIndex)) {
    state.riichiJustDeclared = state.humanIndex;
  }
  return humanDiscard(state, tile);
}

export function humanCall(state, choice) {
  const w = state.waiting;
  if (!w || w.type !== 'calls') return state;

  // ツモ選択
  if (choice === 'tsumo') { resolveWin(state, state.humanIndex, null, 'tsumo'); return state; }
  if (choice === 'discardAny') { state.waiting = { type: 'discard' }; return state; }

  // ロン/ポン/スキップ（打牌に対する反応）
  const ronners = state._pendingRonners || [];
  const ponners = state._pendingPonners || [];
  let ronList = ronners.slice();
  if (choice !== 'ron') ronList = ronList.filter(p => p !== state.humanIndex);
  finishCalls(state, ronList, ponners, choice);
  state._pendingRonners = state._pendingPonners = null;
  if (state.phase === 'over' || state.waiting) return state;
  return advance(state);
}
