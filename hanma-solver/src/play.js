// play.js — 韓麻 実戦UI（対AI）
import { N_TILES, tileName, rankOf, doraFromIndicator, MAN, PIN, SOU } from './tiles.js';
import {
  newGame, advance, humanDiscard, humanRiichiDiscard, humanCall,
  canDeclareRiichi, tenpaiAfterDiscard,
  ankanOptions, shouminkanOptions, humanAnkan, humanShouminkan,
} from './game.js';
import { analyzeDiscards } from './analyze.js';
import { dealInProb } from './danger.js';
import { tileEl, backsInto, faceHTML } from './tileview.js';

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

const $ = (id) => document.getElementById(id);
let state = null;
let riichiArmed = false;
let myLog = []; // 自分の打牌レビュー用（リーチ宣言前の打牌のみ記録）
let reviewEntry = null; // レビューで局面を再現中の myLog エントリ（null＝通常表示）
let savedOverState = null; // レビュー突入時に退避した対局終了状態

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

  const clickable = isMyDiscard && !reviewEntry;
  // ドラ（黄色がけ用）: 赤5は常にドラ扱い＋表ドラ表示牌から求めたドラ
  const doraSet = new Set([MAN + 4, PIN + 4, SOU + 4]);
  for (const ind of state.doraIndicators) doraSet.add(doraFromIndicator(ind));
  const mk = (idx, isDrawn) => {
    const disabled = clickable && riichiArmed && !tenpaiAfterDiscard(state, p, idx);
    // レビュー中は最善（緑）とあなたの選択（青）をハイライト
    const isBest = reviewEntry && idx === reviewEntry.bestTile;
    const isPick = reviewEntry && idx === reviewEntry.chosenTile && idx !== reviewEntry.bestTile;
    const el = tileEl(idx, { drawn: isDrawn, disabled, dora: doraSet.has(idx), best: isBest, pick: isPick });
    if (clickable && !disabled) el.onclick = () => onDiscard(idx);
    return el;
  };
  for (let i = 0; i < N_TILES; i++) for (let k = 0; k < c[i]; k++) hand.appendChild(mk(i, false));
  if (drawn != null) hand.appendChild(mk(drawn, true));
}

function renderActions() {
  const box = $('actions'); box.innerHTML = '';
  if (reviewEntry) {
    const b = document.createElement('button'); b.className = 'btn act-skip';
    b.textContent = '← 結果に戻る'; b.onclick = exitReview; box.appendChild(b);
    return;
  }
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
  if (reviewEntry) {
    const l = reviewEntry;
    box.style.display = '';
    box.innerHTML = `🔍 <strong>${l.turn}手目の局面</strong>　` +
      `お手本（1位）: <span class="rec">${tileName(l.bestTile)}</span> 切り　／　` +
      `あなた: ${tileName(l.chosenTile)}（総合 ${l.rank}位／${l.total}）` +
      (l.top ? ' <span class="rv-ok">✓ 最善</span>' : ` <span class="rv-bad">${reviewReason(l)}</span>`);
    return;
  }
  const on = $('showHint').checked;
  const isMyDiscard = state.phase === 'discard' && state.turn === state.humanIndex && state.waiting?.type === 'discard';
  if (!on || !isMyDiscard) { box.style.display = 'none'; return; }
  // お手本は対局後レビューと同じ「総合評価」の1位（向聴・受け入れ・ドラ・放銃リスク込み）
  const { results, threats } = rankDiscards(state);
  const best = results[0];
  const shTxt = best.shanten <= 0 ? (best.shanten === 0 ? 'テンパイ' : 'アガリ') : best.shanten + '向聴';
  box.style.display = '';
  box.innerHTML = `お手本（総合1位）: <span class="rec">${tileName(best.discard)}</span> 切り` +
    ` → ${shTxt}・受け入れ<strong>${best.ukeireTotal}</strong>枚・ドラ${best.dora}` +
    (threats > 0.05 ? `・放銃率${(best.dealIn * 100).toFixed(0)}%` : '') +
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
  panel.querySelectorAll('.rv-jump').forEach((btn) => {
    btn.onclick = () => enterReview(parseInt(btn.dataset.rev, 10));
  });
}

// 局面レビュー: その打牌時点の盤面を再現表示（操作不可・最善/自分をハイライト）
function enterReview(i) {
  if (!myLog[i]) return;
  savedOverState = state;
  reviewEntry = myLog[i];
  state = reviewEntry.snap;
  render();
  $('table').scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function exitReview() {
  if (savedOverState) state = savedOverState;
  reviewEntry = null; savedOverState = null;
  render();
  $('resultPanel').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// 牌1枚のHTML文字列（結果パネルは innerHTML 一括なので DOM でなく文字列で組む）
function tileHTML(idx, opts = {}) {
  const red = idx < 27 && rankOf(idx) === 5;
  const cls = 'tile t-sm' + (red ? ' red' : '') + (opts.dora ? ' is-dora' : '') +
    (opts.best ? ' best' : '') + (opts.pick ? ' pick' : '');
  return `<span class="${cls}">${faceHTML(idx)}</span>`;
}

// レビュー行の「ひとこと」（なぜ最善でなかったか）
function reviewReason(l) {
  if (l.top) return '';
  if (l.chosenSh > l.bestSh) return 'アガリから遠回り';
  if (l.threats > 0.05 && l.chosenDealIn > l.bestDealIn + 0.03)
    return `放銃リスク高（${(l.chosenDealIn * 100).toFixed(0)}%→${(l.bestDealIn * 100).toFixed(0)}%）`;
  if (l.chosenUke < l.bestUke) return `手が狭い（受け入れ −${l.bestUke - l.chosenUke}枚）`;
  if (l.chosenDora < l.bestDora) return `打点減（ドラ −${l.bestDora - l.chosenDora}）`;
  return 'わずかに劣る';
}

// 対局後の打牌レビュー（リーチ宣言前の自分の打牌を「総合評価」で採点）
function renderReview() {
  const doraSet = new Set([MAN + 4, PIN + 4, SOU + 4]);
  for (const ind of state.doraIndicators) doraSet.add(doraFromIndicator(ind));
  const topCnt = myLog.filter((l) => l.top).length;
  const total = myLog.length;

  // 気になった手番（最善から外れた打牌）だけを対象に。正解手番は省略。
  const misses = myLog.map((l, i) => ({ l, i })).filter((x) => !x.l.top);

  let h = `<div class="review">`;
  h += `<div class="rv-head">🔍 打牌レビュー（総合評価）<span class="rv-score">最善一致 ${topCnt}/${total}</span></div>`;

  if (misses.length === 0) {
    h += `<div class="rv-allbest">🎉 リーチ前の${total}手すべてが総合1位（最善）でした。文句なしの打ち回り！</div>`;
    h += `<div class="rv-note">※採点は向聴・受け入れ・ドラ・相手の河からの放銃リスクを合わせた総合評価（リーチ前の打牌のみ）。</div>`;
    h += `</div>`;
    return h;
  }

  h += `<div class="rv-note">最善から外れた<strong>${misses.length}手</strong>だけ表示（正解手は省略）。「局面 →」でその盤面に戻れます。</div>`;
  h += `<div class="rv-table-wrap"><table class="rv-table"><thead><tr>` +
    `<th>打</th><th>あなたの打牌</th><th>総合順位</th><th>推奨（1位）</th><th>ひとこと</th><th></th></tr></thead><tbody>`;
  for (const { l, i } of misses) {
    const rankCls = l.rank <= 3 ? 'rv-rk-mid' : 'rv-rk-bad';
    const rankCell = `<span class="${rankCls}">${l.rank}位<span class="rv-num"> / ${l.total}</span></span>`;
    const recCell = `${tileHTML(l.bestTile, { dora: doraSet.has(l.bestTile), best: true })} ${tileName(l.bestTile)}`;
    h += `<tr class="rv-row-bad">` +
      `<td class="rv-num">${l.turn}</td>` +
      `<td>${tileHTML(l.chosenTile, { dora: doraSet.has(l.chosenTile), pick: true })} ${tileName(l.chosenTile)}` +
      `${l.riichi ? ' <span class="riichi-tag">リーチ</span>' : ''}</td>` +
      `<td>${rankCell}</td>` +
      `<td>${recCell}</td>` +
      `<td class="rv-reason"><span class="rv-bad">${reviewReason(l)}</span></td>` +
      `<td><button class="btn rv-jump" data-rev="${i}">局面 →</button></td></tr>`;
  }
  h += `</tbody></table></div>`;
  h += `<div class="rv-note">※「総合順位」＝相手の河・放銃リスクまで加味した全打牌候補中の順位。</div>`;
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

// 何切るクイズと同じ「総合評価」で全打牌候補をランキング。
// 総合 = 向聴優先、同向聴で（受け入れ＋ドラ＋ドラそば）を放銃リスクで割り引く。
function rankDiscards(state) {
  const p = state.humanIndex;
  const counts = state.hands[p];
  const omote = state.doraIndicators;
  const calledMelds = state.melds[p].length;

  // 場に見えている牌（自分の手牌以外）: 全員の河＋副露＋表ドラ
  const boardSeen = new Array(N_TILES).fill(0);
  for (let q = 0; q < state.players; q++) {
    for (const t of state.discards[q]) boardSeen[t]++;
    for (const m of state.melds[q]) boardSeen[m.tile] += (m.type === 'pon' ? 3 : 4);
  }
  for (const d of omote) boardSeen[d]++;
  for (let i = 0; i < N_TILES; i++) boardSeen[i] = Math.min(4, boardSeen[i]);
  const seenAll = boardSeen.slice();
  for (let i = 0; i < N_TILES; i++) seenAll[i] = Math.min(4, seenAll[i] + counts[i]);

  // 警戒度（テンパイ濃厚な相手数）: 相手の河の長さ＋リーチ
  let threats = 0;
  for (let q = 0; q < state.players; q++) {
    if (q === p) continue;
    threats += state.riichi[q] ? 1 : clamp((state.discards[q].length - 6) / 9, 0, 0.6);
  }

  // ドラ集合とドラそば
  const doraTiles = new Set([MAN + 4, PIN + 4, SOU + 4]);
  for (const ind of omote) doraTiles.add(doraFromIndicator(ind));
  const sobaCount = (c) => {
    let s = 0;
    for (let i = 0; i < 27; i++) {
      if (!c[i]) continue;
      const suit = Math.floor(i / 9), r = i % 9;
      for (const D of doraTiles) {
        if (D < 27 && Math.floor(D / 9) === suit) {
          const d = Math.abs(r - (D % 9));
          if (d >= 1 && d <= 2) { s += c[i]; break; }
        }
      }
    }
    return s;
  };

  const results = analyzeDiscards({ counts, calledMelds, omoteIndicators: omote, seen: boardSeen });
  for (const r of results) {
    r.dealIn = dealInProb(r.discard, seenAll, threats);
    const c = counts.slice(); c[r.discard]--;
    r.soba = sobaCount(c);
    const value = (r.ukeireTotal + r.dora * 3 + r.soba * 0.7) * (1 - 0.85 * r.dealIn);
    r.score = -r.shanten * 100000 + value * 10;
  }
  results.sort((a, b) => b.score - a.score || a.dealIn - b.dealIn);
  return { results, threats };
}

function recordMyDiscard(p, tile) {
  const { results, threats } = rankDiscards(state);
  const best = results[0];
  const chosen = results.find((r) => r.discard === tile) || best;
  const rank = results.findIndex((r) => r.discard === tile) + 1;
  myLog.push({
    turn: state.discards[p].length + 1,
    riichi: riichiArmed,
    snap: structuredClone(state), // 打牌直前（この牌がまだ手にある）の盤面
    threats,
    rank, total: results.length,
    top: Math.abs(chosen.score - best.score) < 1e-6, // 総合スコアが最善と同点＝最善級
    chosenTile: tile, chosenSh: chosen.shanten, chosenUke: chosen.ukeireTotal, chosenDora: chosen.dora, chosenDealIn: chosen.dealIn,
    bestTile: best.discard, bestSh: best.shanten, bestUke: best.ukeireTotal, bestDora: best.dora, bestDealIn: best.dealIn,
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
  reviewEntry = null; savedOverState = null;
  render();
}

$('newGame').onclick = startGame;
$('showHint').onchange = render;
startGame();
