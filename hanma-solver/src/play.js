// play.js — 韓麻 実戦UI（対AI）
import { N_TILES, tileName } from './tiles.js';
import {
  newGame, advance, humanDiscard, humanRiichiDiscard, humanCall,
  canDeclareRiichi, tenpaiAfterDiscard,
  ankanOptions, shouminkanOptions, humanAnkan, humanShouminkan,
} from './game.js';
import { analyzeDiscards } from './analyze.js';
import { tileEl, backsInto } from './tileview.js';

const $ = (id) => document.getElementById(id);
let state = null;
let riichiArmed = false;

function tilesInto(container, counts, opts = {}) {
  container.innerHTML = '';
  for (let i = 0; i < N_TILES; i++) for (let k = 0; k < counts[i]; k++) container.appendChild(tileEl(i, opts));
}

function meldEl(meld) {
  const el = document.createElement('span'); el.className = 'meld';
  const n = meld.type === 'pon' ? 3 : 4;
  for (let x = 0; x < n; x++) el.appendChild(tileEl(meld.tile, { small: true }));
  const tag = document.createElement('span'); tag.style.fontSize = '.6rem'; tag.style.color = 'var(--muted)'; tag.style.alignSelf = 'center';
  tag.textContent = { pon: '', ankan: '暗槓', daiminkan: '大明槓', shouminkan: '加槓' }[meld.type] || '';
  if (tag.textContent) el.appendChild(tag);
  return el;
}

const SEAT_MAP = {
  4: { 1: 'Right', 2: 'Top', 3: 'Left' },
  3: { 1: 'Right', 2: 'Left' },
};
function seatOf(state, p) {
  const rel = (p - state.humanIndex + state.players) % state.players;
  if (rel === 0) return 'Bottom';
  return SEAT_MAP[state.players][rel];
}
function seatLabel(state, p) {
  const rel = (p - state.humanIndex + state.players) % state.players;
  const nm = { 1: '下家', 2: state.players === 4 ? '対面' : '上家', 3: '上家' };
  return rel === 0 ? 'あなた' : `AI・${nm[rel]}`;
}

function render() {
  // 中央（ドラ表示・残り・供託）
  const pc = $('pondCenter');
  pc.innerHTML = '<div class="dora-wall"></div>' +
    `<div class="pc-info"><span>残 <b>${state.wall.length}</b></span>` +
    (state.pot ? `<span class="pot">供託 <b>${state.pot}</b></span>` : '') + '</div>';
  const dw = pc.querySelector('.dora-wall');
  for (const d of state.doraIndicators) dw.appendChild(tileEl(d, { small: true }));

  for (const s of ['Top', 'Left', 'Right', 'Bottom']) { $('seat' + s).innerHTML = ''; $('river' + s).innerHTML = ''; }

  for (let p = 0; p < state.players; p++) {
    const seat = seatOf(state, p);
    const seatEl = $('seat' + seat), riverEl = $('river' + seat);
    const isTurn = state.turn === p && state.phase !== 'over';
    seatEl.classList.toggle('turn-now', isTurn);

    const info = document.createElement('div'); info.className = 'seat-info';
    info.innerHTML = `<span class="seat-name">${seatLabel(state, p)}</span>` +
      `<span class="seat-score">${fmtScore(state.scores[p])}</span>` +
      (state.riichi[p] ? '<span class="riichi-tag">リーチ</span>' : '') +
      (isTurn ? '<span class="turn-dot">●</span>' : '');
    seatEl.appendChild(info);

    if (p !== state.humanIndex) {
      const bk = document.createElement('div'); bk.className = 'backs';
      backsInto(bk, state.hands[p].reduce((a, b) => a + b, 0), true);
      seatEl.appendChild(bk);
    }
    if (state.melds[p].length) {
      const m = document.createElement('div'); m.className = 'seat-melds';
      for (const md of state.melds[p]) m.appendChild(meldEl(md));
      seatEl.appendChild(m);
    }
    for (const t of state.discards[p]) riverEl.appendChild(tileEl(t, { small: true }));
  }

  // 自分の副露・手牌
  const mm = $('myMelds'); mm.innerHTML = '';
  for (const meld of state.melds[state.humanIndex]) mm.appendChild(meldEl(meld));

  renderHand();
  renderActions();
  renderHint();
  renderResult();
}

function renderHand() {
  const hand = $('myHand'); hand.innerHTML = '';
  const p = state.humanIndex;
  const c = state.hands[p].slice();
  const isMyDiscard = state.phase === 'discard' && state.turn === p && state.waiting?.type === 'discard';
  let drawn = null;
  if (state.drawnTile != null && c[state.drawnTile] > 0 && isMyDiscard) { c[state.drawnTile]--; drawn = state.drawnTile; }

  const clickable = isMyDiscard;
  const mk = (idx, isDrawn) => {
    const disabled = clickable && riichiArmed && !tenpaiAfterDiscard(state, p, idx);
    const el = tileEl(idx, { drawn: isDrawn, disabled });
    if (clickable && !disabled) el.onclick = () => onDiscard(idx);
    return el;
  };
  for (let i = 0; i < N_TILES; i++) for (let k = 0; k < c[i]; k++) hand.appendChild(mk(i, false));
  if (drawn != null) hand.appendChild(mk(drawn, true));
}

function renderActions() {
  const box = $('actions'); box.innerHTML = '';
  if (state.phase === 'over') return;
  const w = state.waiting;
  if (!w) return;

  if (w.type === 'calls') {
    for (const opt of w.options) {
      if (opt.action === 'discardAny') continue; // ツモ見送りは「スルー」で表現
      const b = document.createElement('button');
      b.className = 'btn ' + ({ ron: 'act-ron', tsumo: 'act-tsumo', pon: 'act-pon', kan: 'act-pon', skip: 'act-skip' }[opt.action] || 'act-skip');
      b.textContent = { ron: 'ロン', tsumo: 'ツモ', pon: 'ポン', kan: 'カン', skip: 'スルー' }[opt.action] || opt.action;
      b.onclick = () => onCall(opt.action);
      box.appendChild(b);
    }
    // ツモ選択時に「ツモらず打牌」= discardAny
    if (w.options.some(o => o.action === 'tsumo')) {
      const b = document.createElement('button'); b.className = 'btn act-skip'; b.textContent = 'ツモらず打つ';
      b.onclick = () => onCall('discardAny'); box.appendChild(b);
    }
    return;
  }

  if (w.type === 'discard') {
    if (canDeclareRiichi(state)) {
      const lab = document.createElement('label'); lab.className = 'riichi-arm';
      const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = riichiArmed;
      cb.onchange = () => { riichiArmed = cb.checked; renderHand(); };
      lab.appendChild(cb); lab.appendChild(document.createTextNode('リーチして打つ（テンパイ牌のみ選択可）'));
      box.appendChild(lab);
    }
    // カン（暗槓・加槓）
    if (!riichiArmed) {
      for (const t of ankanOptions(state)) {
        const b = document.createElement('button'); b.className = 'btn act-pon';
        b.textContent = `暗槓 ${tileName(t)}`; b.onclick = () => onAnkan(t); box.appendChild(b);
      }
      for (const t of shouminkanOptions(state)) {
        const b = document.createElement('button'); b.className = 'btn act-pon';
        b.textContent = `加槓 ${tileName(t)}`; b.onclick = () => onShouminkan(t); box.appendChild(b);
      }
    }
    const note = document.createElement('span');
    note.style.color = 'var(--muted)'; note.style.fontSize = '.8rem';
    note.textContent = riichiArmed ? '　切る牌を選択（リーチ宣言）' : '　切る牌をクリック';
    box.appendChild(note);
  }
}

function renderHint() {
  const box = $('hint');
  const on = $('showHint').checked;
  const isMyDiscard = state.phase === 'discard' && state.turn === state.humanIndex && state.waiting?.type === 'discard';
  if (!on || !isMyDiscard) { box.style.display = 'none'; return; }
  const res = analyzeDiscards({
    counts: state.hands[state.humanIndex],
    calledMelds: state.melds[state.humanIndex].length,
    omoteIndicators: state.doraIndicators,
  });
  const best = res[0];
  const shTxt = best.shanten <= 0 ? (best.shanten === 0 ? 'テンパイ' : 'アガリ') : best.shanten + '向聴';
  box.style.display = '';
  box.innerHTML = `お手本: <span class="rec">${tileName(best.discard)}</span> 切り` +
    ` → ${shTxt}・受け入れ<strong>${best.ukeireTotal}</strong>枚・ドラ${best.dora}` +
    (best.discardsRed ? '（※5切りは赤ドラ損）' : '');
}

function renderResult() {
  const panel = $('resultPanel');
  if (state.phase !== 'over') { panel.style.display = 'none'; return; }
  panel.style.display = '';
  const r = state.result;
  let html = '';
  if (r.type === 'win') {
    const meWin = r.winner === state.humanIndex;
    const who = meWin ? 'あなた' : seatLabel(state, r.winner);
    html += `<div class="rhead ${meWin ? 'win' : 'lose'}">${who}の${r.kind === 'tsumo' ? 'ツモ' : 'ロン'}和了！ ${r.totalGain}点</div>`;
    html += `<div class="tiles" id="winHand"></div>`;
    const parts = r.breakdown.map(([k, v]) => `${k} ${v}`).join(' ／ ');
    const extra = (r.riichi && r.potGain ? ` ／ リーチ供託 +${r.potGain}` : '') + (r.kokushi ? ' ／ 国士無双' : '');
    html += `<div style="color:var(--muted);font-size:.85rem;margin-top:6px">内訳: ${parts}${extra}</div>`;
  } else {
    html += `<div class="rhead">流局</div>`;
    html += `<div style="color:var(--muted);font-size:.85rem">テンパイ: ${r.tenpai.length ? r.tenpai.map(p => p === state.humanIndex ? 'あなた' : seatLabel(state, p)).join('、') : 'なし'}</div>`;
  }
  html += `<div class="deltas">` + state.scores.map((s, p) => {
    const d = r.deltas ? r.deltas[p] : 0;
    const nm = p === state.humanIndex ? 'あなた' : seatLabel(state, p);
    const dc = d > 0 ? 'up' : d < 0 ? 'down' : '';
    return `<span>${nm}: <span class="${dc}">${d > 0 ? '+' : ''}${d}</span> → ${fmtScore(s)}</span>`;
  }).join('') + `</div>`;
  html += `<button class="btn" id="nextGame" style="margin-top:12px">次の局へ</button>`;
  panel.innerHTML = html;

  if (r.type === 'win') tilesInto($('winHand'), r.hand, { small: true });
  $('nextGame').onclick = startGame;

  // 勝敗をハンド上部にも
}

function fmtScore(s) { return (s > 0 ? '+' : '') + s; }

// ── 操作 ──
function onDiscard(tile) {
  if (riichiArmed) { state = humanRiichiDiscard(state, tile); }
  else { state = humanDiscard(state, tile); }
  riichiArmed = false;
  render();
}
function onCall(choice) {
  state = humanCall(state, choice);
  render();
}
function onAnkan(tile) { state = humanAnkan(state, tile); render(); }
function onShouminkan(tile) { state = humanShouminkan(state, tile); render(); }

function startGame() {
  const players = parseInt($('playerCount').value, 10) || 4;
  state = newGame({ players, humanIndex: 0 });
  advance(state);
  riichiArmed = false;
  render();
}

$('newGame').onclick = startGame;
$('showHint').onchange = render;
startGame();
