// play.js — 韓麻 実戦UI（対AI）
import { N_TILES, tileName, rankOf, doraFromIndicator, MAN, PIN, SOU } from './tiles.js';
import {
  newGame, advance, humanDiscard, humanRiichiDiscard, humanCall,
  canDeclareRiichi, tenpaiAfterDiscard,
  ankanOptions, shouminkanOptions, humanAnkan, humanShouminkan,
} from './game.js';
import { analyzeDiscards } from './analyze.js';
import { tileEl, backsInto, faceHTML } from './tileview.js';

const $ = (id) => document.getElementById(id);
let state = null;
let riichiArmed = false;
let myLog = []; // 自分の打牌レビュー用（リーチ宣言前の打牌のみ記録）

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
    state.discards[p].forEach((t, i) => {
      const el = tileEl(t, { small: true });
      if (i === state.riichiAt[p]) el.classList.add('riichi-tile');
      riverEl.appendChild(el);
    });
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
  // ドラ（黄色がけ用）: 赤5は常にドラ扱い＋表ドラ表示牌から求めたドラ
  const doraSet = new Set([MAN + 4, PIN + 4, SOU + 4]);
  for (const ind of state.doraIndicators) doraSet.add(doraFromIndicator(ind));
  const mk = (idx, isDrawn) => {
    const disabled = clickable && riichiArmed && !tenpaiAfterDiscard(state, p, idx);
    const el = tileEl(idx, { drawn: isDrawn, disabled, dora: doraSet.has(idx) });
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
  if (myLog.length) html += renderReview();
  html += `<button class="btn" id="nextGame" style="margin-top:12px">次の局へ</button>`;
  panel.innerHTML = html;

  if (r.type === 'win') tilesInto($('winHand'), r.hand, { small: true });
  $('nextGame').onclick = startGame;

  // 勝敗をハンド上部にも
}

// 牌1枚のHTML文字列（結果パネルは innerHTML 一括なので DOM でなく文字列で組む）
function tileHTML(idx, opts = {}) {
  const red = idx < 27 && rankOf(idx) === 5;
  const cls = 'tile t-sm' + (red ? ' red' : '') + (opts.dora ? ' is-dora' : '') +
    (opts.best ? ' best' : '') + (opts.pick ? ' pick' : '');
  return `<span class="${cls}">${faceHTML(idx)}</span>`;
}

// 対局後の打牌レビュー（リーチ宣言前の自分の打牌を牌効率で採点）
function renderReview() {
  const doraSet = new Set([MAN + 4, PIN + 4, SOU + 4]);
  for (const ind of state.doraIndicators) doraSet.add(doraFromIndicator(ind));
  const correct = myLog.filter((l) => l.tie).length;
  const total = myLog.length;

  let h = `<div class="review">`;
  h += `<div class="rv-head">🔍 打牌レビュー <span class="rv-score">${correct}/${total} 最善一致</span>` +
    `<span class="rv-note">（牌効率ベース：向聴・受け入れ・ドラ。安全度は含みません）</span></div>`;
  h += `<div class="rv-table-wrap"><table class="rv-table"><thead><tr>` +
    `<th>打</th><th>あなた</th><th>最善</th><th>あなたの結果</th><th>評価</th></tr></thead><tbody>`;
  const fmtSh = (s) => s <= -1 ? 'アガリ' : s === 0 ? 'テンパイ' : `${s}向聴`;
  for (const l of myLog) {
    let verdict;
    if (l.chosenTile === l.bestTile) verdict = '<span class="rv-ok">✓ 最善</span>';
    else if (l.tie) verdict = '<span class="rv-ok">✓ 同着</span>';
    else {
      let delta;
      if (l.chosenSh > l.bestSh) delta = `向聴 ${l.chosenSh - l.bestSh} 遠回り`;
      else if (l.chosenUke < l.bestUke) delta = `受け入れ −${l.bestUke - l.chosenUke}枚`;
      else if (l.chosenDora < l.bestDora) delta = `ドラ −${l.bestDora - l.chosenDora}`;
      else delta = 'やや損';
      verdict = `<span class="rv-bad">✗ ${delta}</span>`;
    }
    const bestCell = l.chosenTile === l.bestTile
      ? '<span class="rv-num">—</span>'
      : `${tileHTML(l.bestTile, { dora: doraSet.has(l.bestTile), best: true })} ${tileName(l.bestTile)}` +
        (l.bestSh < l.chosenSh ? ` <span class="rv-num">(${fmtSh(l.bestSh)}・受${l.bestUke})</span>` : '');
    h += `<tr class="${l.tie ? '' : 'rv-row-bad'}">` +
      `<td class="rv-num">${l.turn}</td>` +
      `<td>${tileHTML(l.chosenTile, { dora: doraSet.has(l.chosenTile), pick: true })} ${tileName(l.chosenTile)}` +
      `${l.riichi ? ' <span class="riichi-tag">リーチ</span>' : ''}</td>` +
      `<td>${bestCell}</td>` +
      `<td class="rv-num">${fmtSh(l.chosenSh)}・受${l.chosenUke}枚</td>` +
      `<td>${verdict}</td></tr>`;
  }
  h += `</tbody></table></div>`;
  h += `<div class="rv-note">※「最善」は牌効率で最も手が広い打牌。相手の河・放銃リスクは含みません（それは何切るクイズで確認できます）。</div>`;
  h += `</div>`;
  return h;
}

function fmtScore(s) { return (s > 0 ? '+' : '') + s; }

// ── 操作 ──
function onDiscard(tile) {
  const p = state.humanIndex;
  // リーチ後はツモ切り強制なので採点対象外。宣言前の打牌のみ記録。
  if (!state.riichi[p]) recordMyDiscard(p, tile);
  if (riichiArmed) { state = humanRiichiDiscard(state, tile); }
  else { state = humanDiscard(state, tile); }
  riichiArmed = false;
  render();
}

function recordMyDiscard(p, tile) {
  const res = analyzeDiscards({
    counts: state.hands[p], calledMelds: state.melds[p].length, omoteIndicators: state.doraIndicators,
  });
  const best = res[0];
  const chosen = res.find((r) => r.discard === tile) || best;
  myLog.push({
    turn: state.discards[p].length + 1,
    riichi: riichiArmed,
    chosenTile: tile, chosenSh: chosen.shanten, chosenUke: chosen.ukeireTotal, chosenDora: chosen.dora,
    bestTile: best.discard, bestSh: best.shanten, bestUke: best.ukeireTotal, bestDora: best.dora,
    tie: chosen.shanten === best.shanten && chosen.ukeireTotal === best.ukeireTotal,
  });
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
  myLog = [];
  render();
}

$('newGame').onclick = startGame;
$('showHint').onchange = render;
startGame();
