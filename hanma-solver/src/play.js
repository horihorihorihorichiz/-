// play.js — 韓麻 実戦UI（対AI）
import { N_TILES, tileName, rankOf, doraFromIndicator, MAN, PIN, SOU, HONOR } from './tiles.js';
import {
  newGame, advance, humanDiscard, humanRiichiDiscard, humanCall,
  canDeclareRiichi, tenpaiAfterDiscard,
  ankanOptions, shouminkanOptions, humanAnkan, humanShouminkan,
} from './game.js';
import { analyzeDiscards } from './analyze.js';
import { dealInProb, dangerReasons } from './danger.js';
import { tileEl, backsInto, faceHTML } from './tileview.js';

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
// 打牌レビューで「ミス」とみなす期待値ロスのしきい値（最善に対する割合）。
// これ未満なら期待値ほぼ互角＝誤差とみなして上げない。
const EV_TOLERANCE = 0.10;

const $ = (id) => document.getElementById(id);
let state = null;
let riichiArmed = false;
let myLog = []; // 自分の打牌レビュー用（リーチ宣言前の打牌のみ記録）
let reviewEntry = null; // レビューで局面を再現中の myLog エントリ（null＝通常表示）
let savedOverState = null; // レビュー突入時に退避した対局終了状態
let announcedRiichi = new Set(); // リーチ告知済みの家（重複告知防止）
let toastTimer = null;

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

// いまの自分の打牌判断（1回だけ計算して各描画で共有）。ベタおりモード判定を含む。
let curDecision = null;
function computeDecision() {
  const p = state.humanIndex;
  const isMyDiscard = state.phase === 'discard' && state.turn === p && state.waiting?.type === 'discard';
  if (reviewEntry || !isMyDiscard || state.riichi[p]) return null;
  const { results, threats } = rankDiscards(state);
  const riichiOpps = [];
  for (let q = 0; q < state.players; q++) if (q !== p && state.riichi[q]) riichiOpps.push(q);
  const myShanten = Math.min(...results.map((r) => r.shanten));
  // 完全に降りるべき局面: 危険な相手(リーチ/テンパイ濃厚) がいて、自分が2向聴以上で遠い
  const fold = (riichiOpps.length > 0 || threats >= 0.5) && myShanten >= 2;
  const safe = [...results].sort((a, b) => a.dealIn - b.dealIn); // 放銃率の低い順
  return { fold, results, threats, riichiOpps, myShanten, safe, effBest: results[0], safeBest: safe[0] };
}

function render() {
  curDecision = computeDecision();
  document.body.classList.toggle('betaori', !!curDecision?.fold);
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
  renderDefense();
  renderHint();
  renderResult();
  checkRiichiAnnounce();
  scheduleAutoRiichiDiscard();
}

// リーチ宣言の瞬間にトースト告知（1家1回）
function showToast(text) {
  const el = $('toast');
  el.textContent = text;
  el.style.display = '';
  el.style.animation = 'none'; void el.offsetWidth; el.style.animation = '';
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.style.display = 'none'; }, 2200);
}
function checkRiichiAnnounce() {
  if (reviewEntry) return;
  for (let p = 0; p < state.players; p++) {
    if (state.riichi[p] && !announcedRiichi.has(p)) {
      announcedRiichi.add(p);
      showToast(`🀄 ${seatLabel(state, p)} リーチ！`);
    }
  }
}

// ベタおりモードのバナー: 「完全に降りるべき局面」だけ発動し、放銃率の低い牌＝正解として提示
function renderDefense() {
  const box = $('defense');
  const d = curDecision;
  if (!d || !d.fold) { box.style.display = 'none'; return; }
  const { safe, riichiOpps, threats, myShanten } = d;
  const bestSafe = safe[0];
  box.className = 'defense-box';

  const who = riichiOpps.length
    ? riichiOpps.map((q) => `${seatLabel(state, q)}<span class="riichi-tag">リーチ</span>`).join('・')
    : `テンパイ気配の相手（約${threats.toFixed(1)}人）`;
  let h = `<div class="def-head"><span class="def-mode">🛡 ベタおりモード</span> ${who}／あなた${myShanten}向聴で遠い</div>`;

  if ($('showHint').checked) {
    // お手本ON: 答え（安全牌）を提示
    const nearSafe = bestSafe.dealIn < 0.02;
    h += `<div class="def-safe"><span style="color:var(--muted)">正解＝放銃率の低い牌:</span>` +
      safe.slice(0, 5).map((r, i) =>
        `<span class="st ${i === 0 ? 's0' : ''}">${tileHTML(r.discard)} ${tileName(r.discard)} <span class="pct">${(r.dealIn * 100).toFixed(0)}%</span></span>`
      ).join('') + `</div>`;
    h += `<div class="def-note">韓麻は<strong>フリテン無し＝現物でも当たる</strong>ので「完全安全」は4枚見え等だけ。${nearSafe ? '通りやすい牌から丁寧に。' : '水色枠（最安全）から切ろう。'}</div>`;
  } else {
    // お手本OFF: 状況だけ伝えて答えは隠す（自分で考える）
    h += `<div class="def-note">手が遠いのでアガリを諦めて<strong>放銃を避けよう</strong>。どれが一番安全か自分で考えて選んでみて（答え合わせは対局後レビュー、または上の「お手本」ON）。韓麻は<strong>フリテン無し＝現物でも当たる</strong>ので要注意。</div>`;
  }
  box.innerHTML = h;
  box.style.display = '';
}

// リーチ後は自動ツモ切り（ツモ和了・カンの選択が無い＝打牌だけの局面のみ）
let autoTimer = null;
function scheduleAutoRiichiDiscard() {
  if (autoTimer) return;
  const p = state.humanIndex;
  const auto = !reviewEntry && state.phase === 'discard' && state.turn === p &&
    state.riichi[p] && state.waiting?.type === 'discard' && state.drawnTile != null;
  if (!auto) return;
  const tile = state.drawnTile;
  autoTimer = setTimeout(() => { autoTimer = null; onDiscard(tile); }, 500);
}

function renderHand() {
  const hand = $('myHand'); hand.innerHTML = '';
  const p = state.humanIndex;
  const c = state.hands[p].slice();
  const isMyDiscard = state.phase === 'discard' && state.turn === p && state.waiting?.type === 'discard';
  let drawn = null;
  if (state.drawnTile != null && c[state.drawnTile] > 0 && isMyDiscard) { c[state.drawnTile]--; drawn = state.drawnTile; }

  // リーチ中は自動ツモ切りなので手牌はクリック不可（他の牌を切れないように）
  const clickable = isMyDiscard && !reviewEntry && !state.riichi[p];
  // ドラ（黄色がけ用）: 赤5は常にドラ扱い＋表ドラ表示牌から求めたドラ
  const doraSet = new Set([MAN + 4, PIN + 4, SOU + 4]);
  for (const ind of state.doraIndicators) doraSet.add(doraFromIndicator(ind));
  // ベタおりモード中の「最安全牌」ハイライトは、お手本ON時だけ（答えを見たい人向け）
  const safeTile = (curDecision?.fold && $('showHint').checked) ? curDecision.safeBest.discard : null;
  const mk = (idx, isDrawn) => {
    const disabled = clickable && riichiArmed && !tenpaiAfterDiscard(state, p, idx);
    // レビュー中は最善（緑）とあなたの選択（青）をハイライト
    const isBest = reviewEntry && idx === reviewEntry.bestTile;
    const isPick = reviewEntry && idx === reviewEntry.chosenTile && idx !== reviewEntry.bestTile;
    const isSafe = !reviewEntry && idx === safeTile;
    const el = tileEl(idx, { drawn: isDrawn, disabled, dora: doraSet.has(idx), best: isBest, pick: isPick, safe: isSafe });
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
    note.textContent = state.riichi[state.humanIndex] ? '　リーチ中：自動でツモ切り'
      : riichiArmed ? '　切る牌を選択（リーチ宣言）' : '　切る牌をクリック';
    box.appendChild(note);
  }
}

function renderHint() {
  const box = $('hint');
  if (reviewEntry) {
    const l = reviewEntry;
    box.style.display = '';
    const modeLbl = l.mode === 'fold' ? '🛡ベタおり・最安全' : '総合1位';
    box.innerHTML = `🔍 <strong>${l.turn}手目の局面</strong>　` +
      `お手本（${modeLbl}）: <span class="rec">${tileName(l.bestTile)}</span> 切り　／　` +
      `あなた: ${tileName(l.chosenTile)}（${l.mode === 'fold' ? '安全' : '総合'} ${l.rank}位／${l.total}）` +
      (l.ok ? ' <span class="rv-ok">✓ 問題なし</span>' : ` <span class="rv-bad">${reviewReason(l)}</span>`);
    return;
  }
  const on = $('showHint').checked;
  // ベタおりモード中は防御パネルが正解（最安全牌）を出すので、攻めのお手本は隠す
  if (!on || !curDecision || curDecision.fold) { box.style.display = 'none'; return; }
  box.style.display = '';
  // 通常は総合評価の1位（向聴・受け入れ・ドラ・放銃リスク込み）
  const best = curDecision.effBest;
  const shTxt = best.shanten <= 0 ? (best.shanten === 0 ? 'テンパイ' : 'アガリ') : best.shanten + '向聴';
  box.innerHTML = `お手本（総合1位）: <span class="rec">${tileName(best.discard)}</span> 切り` +
    ` → ${shTxt}・受け入れ<strong>${best.ukeireTotal}</strong>枚・ドラ${best.dora}` +
    (curDecision.threats > 0.05 ? `・放銃率${(best.dealIn * 100).toFixed(0)}%` : '') +
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

// 相手の河をどう読むか（韓麻版）— ベタおり解説に添える
function riverReadNote(l) {
  const st = l.snap;
  const h = st.humanIndex;
  const opps = [];
  for (let q = 0; q < st.players; q++) {
    if (q === h) continue;
    const rc = st.discards[q].length;
    if (st.riichi[q] || rc >= 8) opps.push({ q, rc, riichi: st.riichi[q] });
  }
  const genbutsu = opps.some((o) => st.discards[o.q].includes(l.bestTile));
  let s = `<div class="rvd-river"><b>🀫 相手の河の読み方（韓麻）</b><ul>`;
  s += `<li><strong>フリテンが無い</strong>ので、相手の河に切れている牌（＝現物）でも当たる。普通のリーチ麻雀の「現物・スジは安全」が<strong>通用しない</strong>のが韓麻最大の注意点。</li>`;
  s += `<li>だから河から使える安全材料は主に2つ：<b>壁</b>（同じ数牌が3〜4枚見え→その牌を使うリャンメンが物理的に作れない）と、<b>見え枚数</b>（場に多く出ている牌ほど残りが少なく、待ちに使われにくい）。</li>`;
  if (opps.length) {
    s += `<li>この局面の警戒相手：${opps.map((o) => `${seatLabel(st, o.q)}（河${o.rc}枚${o.riichi ? '・リーチ' : ''}）`).join('、')}。河が伸びている＝テンパイ濃厚。</li>`;
  }
  s += `<li>推奨 ${tileName(l.bestTile)} は${genbutsu ? '相手の河にも切れている（現物）が、韓麻では油断せず' : '場に見えている枚数を確認しつつ'}、字牌・端牌・壁の裏など「待ちに使いにくい牌」を選ぶのが軸。序盤に切られた牌の周りは相手の本命から遠いことが多い（弱い手掛かり）。</li>`;
  s += `</ul></div>`;
  return s;
}

// レビュー行の「ひとこと」（なぜ最善でなかったか）
function reviewReason(l) {
  if (l.ok) return '';
  if (l.mode === 'fold') {
    return `危険牌を押した（放銃率 ${(l.chosenDealIn * 100).toFixed(0)}% → 最安全 ${(l.bestDealIn * 100).toFixed(0)}%）`;
  }
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
  const okCnt = myLog.filter((l) => l.ok).length;
  const total = myLog.length;

  // 「ミス」は期待値が明確に落ちた手番だけ（誤差レベルの差は上げない）。
  const misses = myLog.map((l, i) => ({ l, i })).filter((x) => !x.l.ok);

  let h = `<div class="review">`;
  h += `<div class="rv-head">🔍 打牌レビュー<span class="rv-score">問題なし ${okCnt}/${total}</span></div>`;

  if (misses.length === 0) {
    h += `<div class="rv-allbest">🎉 リーチ前の${total}手すべて、期待値でみて最善とほぼ互角。文句なしの打ち回り！</div>`;
    h += `<div class="rv-note">※採点は向聴・受け入れ・ドラ・相手の河からの放銃リスクを合わせた総合評価。最善との期待値差が誤差（${Math.round(EV_TOLERANCE * 100)}%未満）なら「問題なし」として省略（リーチ前の打牌のみ）。</div>`;
    h += `</div>`;
    return h;
  }

  const foldMiss = misses.filter((x) => x.l.mode === 'fold').length;
  h += `<div class="rv-note">気になった<strong>${misses.length}手</strong>だけ表示（誤差レベルの手は省略）。` +
    `${foldMiss ? `うち<strong>${foldMiss}手</strong>は🛡ベタおり局面で危険牌を押した手。` : ''}「局面 →」でその盤面に戻れます。</div>`;
  h += `<div class="rv-table-wrap"><table class="rv-table"><thead><tr>` +
    `<th>打</th><th>あなたの打牌</th><th>ロス</th><th>推奨</th><th>ひとこと</th><th></th></tr></thead><tbody>`;
  for (const { l, i } of misses) {
    let lossCell;
    if (l.mode === 'fold') {
      // ベタおり局面: 放銃率で評価
      const big = l.chosenDealIn >= 0.15;
      lossCell = `<span class="${big ? 'rv-rk-bad' : 'rv-rk-mid'}">🛡放銃${(l.chosenDealIn * 100).toFixed(0)}%<span class="rv-num"> (安全${l.rank}位/${l.total})</span></span>`;
    } else {
      const shWorse = l.chosenSh > l.bestSh;
      const lossTxt = shWorse ? `向聴+${l.chosenSh - l.bestSh}` : `−${Math.max(0, Math.round(l.lossFrac * 100))}%`;
      const big = shWorse || l.lossFrac >= 0.30;
      lossCell = `<span class="${big ? 'rv-rk-bad' : 'rv-rk-mid'}">${lossTxt}<span class="rv-num"> (${l.rank}位/${l.total})</span></span>`;
    }
    const recCell = `${tileHTML(l.bestTile, { dora: doraSet.has(l.bestTile), best: true })} ${tileName(l.bestTile)}` +
      (l.mode === 'fold' ? ` <span class="rv-num">${(l.bestDealIn * 100).toFixed(0)}%</span>` : '');
    h += `<tr class="rv-row-bad">` +
      `<td class="rv-num">${l.turn}</td>` +
      `<td>${tileHTML(l.chosenTile, { dora: doraSet.has(l.chosenTile), pick: true })} ${tileName(l.chosenTile)}` +
      `${l.riichi ? ' <span class="riichi-tag">リーチ</span>' : ''}</td>` +
      `<td>${lossCell}</td>` +
      `<td>${recCell}</td>` +
      `<td class="rv-reason"><span class="rv-bad">${reviewReason(l)}</span></td>` +
      `<td><button class="btn rv-jump" data-rev="${i}">局面 →</button></td></tr>`;
  }
  h += `</tbody></table></div>`;

  // 各ミスに「なぜ推奨の方がいいか」を詳しく解説（最大4手分）
  const details = misses.slice(0, 4);
  for (const { l } of details) {
    if (l.mode === 'fold') {
      // ベタおり: 放銃理由（字牌/端/壁/見え枚数）で安全・危険を説明
      const safeR = (l.seen ? dangerReasons(l.bestTile, l.seen, l.threats) : []).filter((x) => x.t === 'safe');
      const riskR = (l.seen ? dangerReasons(l.chosenTile, l.seen, l.threats) : []).filter((x) => x.t === 'risk');
      const li = (arr, cls, mark) => arr.length
        ? `<ul>${arr.map((x) => `<li class="${cls}">${mark} ${x.s}</li>`).join('')}</ul>`
        : `<ul><li class="${cls}">${mark} （特筆する要素なし）</li></ul>`;
      h += `<div class="rv-detail">` +
        `<div class="rvd-head">🛡 ${l.turn}手目：なぜ <b>${tileName(l.bestTile)}</b>（放銃率${(l.bestDealIn * 100).toFixed(0)}%）が正解で、<b>${tileName(l.chosenTile)}</b>（${(l.chosenDealIn * 100).toFixed(0)}%）が危険か</div>` +
        `<div class="reason-card safe"><div class="rc-head">✓ 推奨 ${tileName(l.bestTile)} が安全な理由</div>${li(safeR, 'safe', '✓')}</div>` +
        `<div class="reason-card risk"><div class="rc-head">⚠ あなたの ${tileName(l.chosenTile)} が危険な理由</div>${li(riskR, 'risk', '⚠')}</div>` +
        riverReadNote(l) +
        `<div class="rvd-logic">▶ ロジック：狙うのは「相手が待ちに使えない牌」。<b>字牌＞端牌＞中張牌</b>の順に当たりにくく、<b>場に多く見えている牌・壁の裏</b>ほど安全。手が遠いこの局面はアガリ価値より放銃回避が優先なので、最も放銃率が低い ${tileName(l.bestTile)} が正解。</div>` +
        `</div>`;
    } else {
      // 攻め: なぜ推奨が良いか（向聴・受け入れ・ドラ・安全）を理由化
      const pros = [];
      if (l.bestSh < l.chosenSh) pros.push(`<li class="safe">✓ 向聴が<b>${l.chosenSh - l.bestSh}つ近い</b>：アガリまで速く、無駄が少ない</li>`);
      if (l.bestUke > l.chosenUke) pros.push(`<li class="safe">✓ 受け入れが<b>${l.bestUke - l.chosenUke}枚広い</b>：手を進める有効牌が多く残る（良形が崩れない）</li>`);
      if (l.bestDora > l.chosenDora) pros.push(`<li class="safe">✓ ドラを<b>${l.bestDora - l.chosenDora}枚多く残せる</b>：同じアガリでも打点が高い</li>`);
      if (l.bestDealIn < l.chosenDealIn - 0.02) pros.push(`<li class="safe">✓ 放銃率が<b>${((l.chosenDealIn - l.bestDealIn) * 100).toFixed(0)}%低い</b>：より安全</li>`);
      if (!pros.length) pros.push(`<li class="safe">✓ 総合評価（向聴・受け入れ・ドラ・放銃率）でわずかに上</li>`);
      h += `<div class="rv-detail">` +
        `<div class="rvd-head">🎯 ${l.turn}手目：なぜ <b>${tileName(l.bestTile)}</b> が推奨か（あなたは ${tileName(l.chosenTile)}）</div>` +
        `<div class="reason-card safe"><div class="rc-head">推奨 ${tileName(l.bestTile)} 切りの利点</div><ul>${pros.join('')}</ul></div>` +
        `<div class="rvd-logic">▶ ロジック：向聴（アガリまでの近さ）を最優先に、同じ向聴なら<b>受け入れの広さ＋打点（ドラ）</b>を放銃リスクで割り引いた総合期待値で比較。${tileName(l.bestTile)} 切りがこの局面で最も期待値が高い。</div>` +
        `<div class="rvd-shape">📐 <b>牌効率の考え方（かぶり形の捌き）</b><ul>` +
        `<li>手牌を「面子＋ターツ＋浮き牌」に分解し、<b>5ブロック</b>（4面子＋雀頭）を意識する。</li>` +
        `<li><b>弱いターツ（ペンチャン89・カンチャン46）や余った重複</b>から先に払い、<b>両面や複合形</b>を残すのがコツ。</li>` +
        `<li>複合形＝<b>1枚で2役</b>の形は受けが広く強い。例：<b>44556</b>（面子＋両面）、<b>3455</b>（面子＋雀頭）、<b>357</b>（リャンカン＝4・6両受け）。</li>` +
        `<li>韓麻は<b>5が全部赤ドラ</b>。5絡みの形（455・556など）は同じ広さなら優先。</li>` +
        `</ul></div>` +
        `</div>`;
    }
  }
  if (misses.length > details.length) {
    h += `<div class="rv-note">（詳しい解説は最初の${details.length}手分のみ表示）</div>`;
  }

  h += `<div class="rv-note">※攻めの手番は<strong>総合期待値</strong>の低下率、🛡ベタおり局面は<strong>放銃率</strong>で採点。誤差は省略。</div>`;
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

  // 字牌の持ちすぎ補正: 字牌は順子が作れず、対子→刻子も2枚待ちで遅い。
  // 受け入れ枚数だと過大評価しがちなので、残した字牌を軽く割り引く（完成刻子は減点しない）。
  const honorHoldPenalty = (c) => {
    let pen = 0;
    for (let i = HONOR; i < N_TILES; i++) {
      if (c[i] === 2) pen += 3.5;      // 字牌対子: 遅い・伸びない
      else if (c[i] === 1) pen += 0.8; // 孤立字牌: ほぼ価値なし
      // c[i] >= 3 は完成刻子なので減点しない
    }
    return pen;
  };

  const results = analyzeDiscards({ counts, calledMelds, omoteIndicators: omote, seen: boardSeen });
  for (const r of results) {
    r.dealIn = dealInProb(r.discard, seenAll, threats);
    const c = counts.slice(); c[r.discard]--;
    r.soba = sobaCount(c);
    // 七対子・国士を狙える手では字牌（対子・単騎）が必要なので割り引かない
    const chiiKokushi = r.forms.includes('chiitoi') || r.forms.includes('kokushi');
    const hPen = chiiKokushi ? 0 : honorHoldPenalty(c);
    r.value = (r.ukeireTotal + r.dora * 3 + r.soba * 0.7) * (1 - 0.85 * r.dealIn) - hPen;
    r.score = -r.shanten * 100000 + r.value * 10;
  }
  results.sort((a, b) => b.score - a.score || a.dealIn - b.dealIn);
  return { results, threats, seenAll };
}

function recordMyDiscard(p, tile) {
  const { results, threats, seenAll } = rankDiscards(state);
  const chosen = results.find((r) => r.discard === tile) || results[0];
  // ベタおりモード判定（renderと同じ基準）
  let riichiN = 0;
  for (let q = 0; q < state.players; q++) if (q !== p && state.riichi[q]) riichiN++;
  const myShanten = Math.min(...results.map((r) => r.shanten));
  const fold = (riichiN > 0 || threats >= 0.5) && myShanten >= 2;

  const base = {
    turn: state.discards[p].length + 1,
    riichi: riichiArmed,
    snap: structuredClone(state), // 打牌直前（この牌がまだ手にある）の盤面
    threats, total: results.length,
    chosenTile: tile, chosenSh: chosen.shanten, chosenUke: chosen.ukeireTotal, chosenDora: chosen.dora, chosenDealIn: chosen.dealIn,
  };

  if (fold) {
    // ベタおり局面: 正解＝放銃率の低い牌。安全に切れたか（放銃率）で採点。
    const safe = [...results].sort((a, b) => a.dealIn - b.dealIn);
    const best = safe[0];
    myLog.push({
      ...base, mode: 'fold',
      rank: safe.findIndex((r) => r.discard === tile) + 1,
      ok: (chosen.dealIn - best.dealIn) <= 0.03, // 最安全から放銃率+3%以内なら許容
      bestTile: best.discard, bestDealIn: best.dealIn,
      seen: seenAll, // 放銃理由の説明用（見え牌）
    });
    return;
  }

  // 通常（攻め）: 総合期待値(value)の差で採点。誤差(EV_TOLERANCE未満)は許容。
  const best = results[0];
  const lossFrac = best.value > 0 ? (best.value - chosen.value) / best.value : 0;
  myLog.push({
    ...base, mode: 'eff',
    rank: results.findIndex((r) => r.discard === tile) + 1,
    ok: chosen.shanten === best.shanten && lossFrac <= EV_TOLERANCE,
    lossFrac,
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
  announcedRiichi = new Set();
  render();
}

$('newGame').onclick = startGame;
$('showHint').onchange = render;
startGame();
