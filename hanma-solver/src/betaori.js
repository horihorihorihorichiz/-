// betaori.js — ベタおり練習（防御ドリル）
// 危険な相手がいて自分は手が遠い局面を出題 →「一番安全な牌は？」を当てる →
// 放銃率ランキングと理由・シンプルなロジックで答え合わせ → 次の局面へ。

import { N_TILES, tileName } from './tiles.js';
import { newGame, advance, humanDiscard, humanCall } from './game.js';
import { analyzeDiscards } from './analyze.js';
import { dealInProb, dangerReasons } from './danger.js';
import { tileEl } from './tileview.js';

const $ = (id) => document.getElementById(id);
let st = null;
let answered = false;
let info = null;
let pick = -1;
let stats = { done: 0, good: 0 };

function humanShanten(state) {
  return analyzeDiscards({ counts: state.hands[0], calledMelds: state.melds[0].length, omoteIndicators: state.doraIndicators })[0].shanten;
}
function effDiscard(state) {
  return analyzeDiscards({ counts: state.hands[0], calledMelds: state.melds[0].length, omoteIndicators: state.doraIndicators })[0].discard;
}
function threatsOf(state) {
  let t = 0;
  for (let p = 1; p < state.players; p++) t += state.riichi[p] ? 1 : Math.max(0, Math.min(0.6, (state.discards[p].length - 6) / 9));
  return t;
}

// 危険な相手（リーチ or 河が伸びてテンパイ気配）が居て、自分は2向聴以上で遠い局面
function genBetaori(players) {
  for (let attempt = 0; attempt < 250; attempt++) {
    const state = newGame({ players, humanIndex: 0 });
    let guard = 0;
    while (state.phase !== 'over' && guard++ < 800) {
      advance(state);
      if (state.phase === 'over') break;
      const w = state.waiting;
      if (!w) break;
      if (w.type === 'calls') {
        const a = w.options.map((o) => o.action);
        if (a.includes('tsumo')) humanCall(state, 'discardAny');
        else if (a.includes('skip')) humanCall(state, 'skip');
        else humanCall(state, a[0]);
        continue;
      }
      if (w.type === 'discard') {
        if (threatsOf(state) >= 0.4 && humanShanten(state) >= 2) return state;
        humanDiscard(state, effDiscard(state));
      }
    }
  }
  return null;
}

function computeInfo(state) {
  const counts = state.hands[0];
  const boardSeen = new Array(N_TILES).fill(0);
  for (let p = 0; p < state.players; p++) {
    for (const t of state.discards[p]) boardSeen[t]++;
    for (const m of state.melds[p]) boardSeen[m.tile] += (m.type === 'pon' ? 3 : 4);
  }
  for (const d of state.doraIndicators) boardSeen[d]++;
  for (let i = 0; i < N_TILES; i++) boardSeen[i] = Math.min(4, boardSeen[i]);
  const seenAll = boardSeen.slice();
  for (let i = 0; i < N_TILES; i++) seenAll[i] = Math.min(4, seenAll[i] + counts[i]);
  const threats = threatsOf(state);
  const tiles = [];
  for (let i = 0; i < N_TILES; i++) if (counts[i] > 0) tiles.push({ tile: i, dealIn: dealInProb(i, seenAll, threats) });
  tiles.sort((a, b) => a.dealIn - b.dealIn);
  return { tiles, seenAll, threats, shanten: humanShanten(state) };
}

const relName = (p) => ({ 1: '下家', 2: st.players === 4 ? '対面' : '上家', 3: '上家' }[p]);

function render() {
  info = computeInfo(st);

  // 表ドラ
  const dora = $('doraDisp'); dora.innerHTML = '';
  for (const d of st.doraIndicators) dora.appendChild(tileEl(d, { small: true }));
  $('turnInfo').textContent = `${st.players}人打ち／残り ${st.wall.length}枚／あなた ${info.shanten}向聴（手が遠い）`;

  // 相手（河＋リーチ）
  const opp = $('opps'); opp.innerHTML = '';
  for (let p = 1; p < st.players; p++) {
    const div = document.createElement('div'); div.className = 'oppq';
    const rc = st.discards[p].length;
    const danger = st.riichi[p] ? '<span class="riichi-tag">リーチ</span>' : (rc >= 9 ? '<span class="warn-tag">テンパイ気配</span>' : '');
    div.innerHTML = `<div class="oppq-head">AI・${relName(p)} ${danger}<span class="oppq-cnt">河${rc}</span></div>`;
    const river = document.createElement('div'); river.className = 'river';
    st.discards[p].forEach((t, i) => {
      const el = tileEl(t, { small: true });
      if (i === st.riichiAt[p]) el.classList.add('riichi-tile');
      river.appendChild(el);
    });
    div.appendChild(river);
    opp.appendChild(div);
  }

  // 自分の手牌（クリックで解答）
  const hand = $('quizHand'); hand.innerHTML = '';
  const safest = info.tiles[0].tile;
  const c = st.hands[0];
  for (let i = 0; i < N_TILES; i++) {
    for (let k = 0; k < c[i]; k++) {
      const isPick = answered && i === pick;
      const isSafe = answered && i === safest;
      const el = tileEl(i, { pick: isPick && !isSafe, safe: isSafe });
      if (!answered) el.onclick = () => onPick(i);
      else el.style.cursor = 'default';
      hand.appendChild(el);
    }
  }

  $('quizResult').style.display = answered ? '' : 'none';
  $('nextBtn').style.display = answered ? '' : 'none';
  if (answered) renderResult();
}

function onPick(i) {
  pick = i; answered = true;
  const rankOf = info.tiles.findIndex((t) => t.tile === i);
  const safest = info.tiles[0];
  const chosen = info.tiles[rankOf];
  stats.done++;
  if (chosen.dealIn - safest.dealIn <= 0.005) stats.good++;
  render();
}

function verdict(chosen, safest) {
  if (chosen.dealIn - safest.dealIn <= 0.005) return { m: '◎', t: '正解！ 一番安全な牌', cls: 'v-good' };
  if (chosen.dealIn - safest.dealIn <= 0.03) return { m: '○', t: 'ほぼOK。ただし最安全はもう一枚', cls: 'v-ok' };
  if (chosen.dealIn - safest.dealIn <= 0.08) return { m: '△', t: 'もっと安全な牌があった', cls: 'v-mid' };
  return { m: '✗', t: '危険牌。ベタおりならもっと安全に', cls: 'v-bad' };
}

function tileSpan(idx, opts) { const el = tileEl(idx, opts || {}); return el.outerHTML; }

function renderResult() {
  const box = $('quizResult');
  const safest = info.tiles[0];
  const chosen = info.tiles.find((t) => t.tile === pick);
  const rank = info.tiles.findIndex((t) => t.tile === pick) + 1;
  const v = verdict(chosen, safest);

  let h = `<div class="verdict ${v.cls}"><span class="vmark">${v.m}</span> ${v.t}` +
    `<span class="lossnum">あなた: ${tileName(pick)} 放銃率${(chosen.dealIn * 100).toFixed(0)}%（安全${rank}位）</span>` +
    `<span class="best-badge">最安全: <b>${tileName(safest.tile)}</b> ${(safest.dealIn * 100).toFixed(0)}%</span></div>`;

  // シンプルなロジック（3原則）
  h += `<div class="logic3"><div class="l3-head">🛡 ベタおりの3原則（韓麻）</div><ol>` +
    `<li><b>フリテンが無い</b> → 現物・スジも当たる。頼れるのは<b>「壁」と「見え枚数」</b>だけ。</li>` +
    `<li>安全な牌の順番：<b>字牌 ＞ 端(1・9) ＞ 中張(4〜6)</b>。</li>` +
    `<li>場に<b>多く見えている牌</b>ほど安全（残りが少ない＝待ちに使われにくい）。</li>` +
    `</ol></div>`;

  // 理由（最安全＝なぜ安全 / あなた＝なぜ危険）
  const safeR = dangerReasons(safest.tile, info.seenAll, info.threats).filter((x) => x.t === 'safe');
  const li = (arr, cls, mark) => arr.length ? `<ul>${arr.map((x) => `<li class="${cls}">${mark} ${x.s}</li>`).join('')}</ul>` : '';
  h += `<div class="reason-card safe"><div class="rc-head">✓ 最安全 ${tileName(safest.tile)} が安全な理由</div>${li(safeR, 'safe', '✓') || '<ul><li class="safe">✓ この局面で最も放銃率が低い牌。</li></ul>'}</div>`;
  if (pick !== safest.tile) {
    const riskR = dangerReasons(pick, info.seenAll, info.threats).filter((x) => x.t === 'risk');
    if (riskR.length) h += `<div class="reason-card risk"><div class="rc-head">⚠ あなたの ${tileName(pick)} が危険な理由</div>${li(riskR, 'risk', '⚠')}</div>`;
  }

  // 放銃率ランキング（安全な順）
  h += `<div class="rank-caption">🀫 安全な順（放銃率が低い順）</div>`;
  h += `<div class="rtable-wrap"><table class="rtable"><thead><tr><th>順</th><th>牌</th><th>放銃率</th><th></th></tr></thead><tbody>`;
  info.tiles.forEach((t, idx) => {
    const tag = (t.tile === safest.tile ? '<span class="pill gold">最安全</span>' : '') + (t.tile === pick ? '<span class="pill blue">あなた</span>' : '');
    h += `<tr class="${t.tile === safest.tile ? 'row-best' : ''}${t.tile === pick ? ' row-pick' : ''}">` +
      `<td class="rank-cell">${idx + 1}</td>` +
      `<td>${tileSpan(t.tile, { small: true })} ${tileName(t.tile)} ${tag}</td>` +
      `<td class="num">${(t.dealIn * 100).toFixed(0)}%</td><td></td></tr>`;
  });
  h += `</tbody></table></div>`;
  h += `<div class="rnote">正解数 ${stats.good}/${stats.done}。放銃率は牌種・見え枚数・壁・警戒人数からの目安（韓麻はフリテン無しで現物も当たる点に注意）。</div>`;
  box.innerHTML = h;
}

function newQuiz() {
  const players = parseInt($('playerCount').value, 10) || 4;
  const s = genBetaori(players);
  if (!s) { $('quizResult').style.display = ''; $('quizResult').innerHTML = '<div class="verdict v-mid">局面生成に失敗しました。もう一度お試しください。</div>'; return; }
  st = s; answered = false; pick = -1;
  render();
}

$('newQuizTop').onclick = newQuiz;
$('nextBtn').onclick = newQuiz;
$('playerCount').onchange = newQuiz;
newQuiz();
