// quiz.js — 何切るクイズ（相手の河から放銃リスクも加味）
//
// 対局エンジンでリアルな局面を生成 → 「何を切る？」を出題 →
// ソルバー（牌効率＋ドラ＋放銃リスク）で採点し、最善打と評価を表示 → 次の局面へ。

import { N_TILES, tileName } from './tiles.js';
import { newGame, advance, humanDiscard, humanCall } from './game.js';
import { analyzeDiscards } from './analyze.js';
import { dealInProb } from './danger.js';
import { tileEl, backsInto } from './tileview.js';

const $ = (id) => document.getElementById(id);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

let st = null;
let answered = false;
let graded = null;
let autoTimer = null;
let autoAdvancing = false;

// ── 局面生成: 数手進めた人間の打牌局面を返す ──
function effDiscard(state) {
  const r = analyzeDiscards({
    counts: state.hands[0], calledMelds: state.melds[0].length,
    omoteIndicators: state.doraIndicators,
  });
  return r[0].discard;
}
function genQuiz(players) {
  for (let attempt = 0; attempt < 60; attempt++) {
    const state = newGame({ players, humanIndex: 0 });
    const target = 4 + Math.floor(Math.random() * 12);
    let humanTurns = 0, guard = 0;
    while (state.phase !== 'over' && guard++ < 600) {
      advance(state);
      if (state.phase === 'over') break;
      const w = state.waiting;
      if (!w) break;
      if (w.type === 'calls') {
        const acts = w.options.map(o => o.action);
        if (acts.includes('tsumo')) humanCall(state, 'discardAny');
        else if (acts.includes('skip')) humanCall(state, 'skip');
        else humanCall(state, acts[0]);
        continue;
      }
      if (w.type === 'discard') {
        humanTurns++;
        // 出題: target 手目、かつ手が2〜4向聴くらいで「考えどころ」のとき優先
        const sh = analyzeDiscards({ counts: state.hands[0], calledMelds: state.melds[0].length, omoteIndicators: state.doraIndicators })[0].shanten;
        if (humanTurns >= target && sh >= 0) return state;
        humanDiscard(state, effDiscard(state));
      }
    }
  }
  return null;
}

// ── 採点 ──
function cap4(arr) { for (let i = 0; i < N_TILES; i++) arr[i] = Math.min(4, arr[i]); return arr; }

function grade(state) {
  const counts = state.hands[0];
  const omote = state.doraIndicators;
  const calledMelds = state.melds[0].length;

  // 場に見えている牌（自分の手牌以外）: 全員の河＋副露＋表ドラ表示
  const boardSeen = new Array(N_TILES).fill(0);
  for (let p = 0; p < state.players; p++) {
    for (const t of state.discards[p]) boardSeen[t]++;
    for (const m of state.melds[p]) boardSeen[m.tile] += (m.type === 'pon' ? 3 : 4);
  }
  for (const d of omote) boardSeen[d]++;
  cap4(boardSeen);
  const seenAll = boardSeen.slice();
  for (let i = 0; i < N_TILES; i++) seenAll[i] = Math.min(4, seenAll[i] + counts[i]);

  // 警戒度: 相手の河の長さ＋リーチから「テンパイ濃厚な相手数」を推定
  let threats = 0;
  const oppInfo = [];
  for (let p = 1; p < state.players; p++) {
    const t = state.riichi[p] ? 1 : clamp((state.discards[p].length - 6) / 9, 0, 0.6);
    threats += t;
    oppInfo.push({ p, riichi: state.riichi[p], discards: state.discards[p].length, threat: t });
  }

  const results = analyzeDiscards({ counts, calledMelds, omoteIndicators: omote, seen: boardSeen });
  for (const r of results) {
    r.dealIn = dealInProb(r.discard, seenAll, threats);
    // 評価値: 向聴を最優先、同向聴内で「手広さ＋打点」を放銃リスクで割り引く
    const value = (r.ukeireTotal + r.dora * 3) * (1 - 0.85 * r.dealIn);
    r.score = -r.shanten * 100000 + value * 10;
  }
  results.sort((a, b) => b.score - a.score || a.dealIn - b.dealIn);
  return { results, threats, oppInfo };
}

function evalValue(r) { return (r.ukeireTotal + r.dora * 3) * (1 - 0.85 * r.dealIn); }

// tier: 'perfect' | 'small'（自動で次へ）| 'mid' | 'big'（STOPして確認）
function verdict(pick, best) {
  if (pick.discard === best.discard) return { tier: 'perfect', mark: '◎', text: '正解！最善手です', cls: 'v-good', loss: 0 };
  if (pick.shanten > best.shanten)
    return { tier: 'big', mark: '🛑', text: `向聴が落ちる大きなミス（最善は ${tileName(best.discard)}）`, cls: 'v-bad', loss: 1 };
  const bv = evalValue(best), pv = evalValue(pick);
  const lossFrac = bv > 0 ? 1 - pv / bv : 0;
  const dangerJump = pick.dealIn - best.dealIn; // 放銃率の増加
  if (lossFrac > 0.25 || dangerJump > 0.08)
    return { tier: 'big', mark: '🛑', text: `大きなロス（最善は ${tileName(best.discard)}）`, cls: 'v-bad', loss: lossFrac, dangerJump };
  if (lossFrac > 0.08)
    return { tier: 'mid', mark: '△', text: `もう少し（最善は ${tileName(best.discard)}）`, cls: 'v-mid', loss: lossFrac, dangerJump };
  return { tier: 'small', mark: '○', text: `ほぼ最善（最善は ${tileName(best.discard)}）`, cls: 'v-ok', loss: lossFrac, dangerJump };
}

// ── 描画 ──
function fmtSh(v) { return v <= -1 ? 'アガリ' : v === 0 ? 'テンパイ' : v + '向聴'; }

function render() {
  // 状況
  const g = graded || grade(st);
  $('turnInfo').textContent = `${st.players}人打ち／残り ${st.wall.length}枚／あなたの捨て牌 ${st.discards[0].length}`;
  const dora = $('doraDisp'); dora.innerHTML = '';
  for (const d of st.doraIndicators) dora.appendChild(tileEl(d, { small: true }));

  // 相手（河＋リーチ）
  const opp = $('opps'); opp.innerHTML = '';
  const rel = { 1: '下家', 2: st.players === 4 ? '対面' : '上家', 3: '上家' };
  for (let p = 1; p < st.players; p++) {
    const div = document.createElement('div'); div.className = 'oppq';
    const dangerBadge = g.oppInfo.find(o => o.p === p)?.threat >= 0.5 ? '<span class="warn-tag">警戒</span>' : '';
    div.innerHTML = `<div class="oppq-head">AI・${rel[(p - 0)]} ${st.riichi[p] ? '<span class="riichi-tag">リーチ</span>' : ''}${dangerBadge}<span class="oppq-cnt">河${st.discards[p].length}</span></div>`;
    const river = document.createElement('div'); river.className = 'river';
    for (const t of st.discards[p]) river.appendChild(tileEl(t, { small: true }));
    if (st.melds[p].length) {
      const m = document.createElement('span'); m.className = 'oppq-melds';
      for (const md of st.melds[p]) for (let k = 0; k < (md.type === 'pon' ? 3 : 4); k++) m.appendChild(tileEl(md.tile, { small: true }));
      river.appendChild(m);
    }
    div.appendChild(river);
    opp.appendChild(div);
  }

  // 自分の副露
  const mm = $('myMelds'); mm.innerHTML = '';
  for (const md of st.melds[0]) { const el = document.createElement('span'); el.className = 'meld'; for (let k = 0; k < (md.type === 'pon' ? 3 : 4); k++) el.appendChild(tileEl(md.tile, { small: true })); mm.appendChild(el); }

  // 手牌（クリックで解答）
  const hand = $('quizHand'); hand.innerHTML = '';
  const best = g.results[0];
  const pickMap = new Map(g.results.map(r => [r.discard, r]));
  const c = st.hands[0];
  for (let i = 0; i < N_TILES; i++) {
    for (let k = 0; k < c[i]; k++) {
      const isBest = answered && i === best.discard;
      const isPick = answered && st._pick === i;
      const el = tileEl(i, { best: isBest, pick: isPick });
      if (!answered) el.onclick = () => onPick(i);
      else el.style.cursor = 'default';
      hand.appendChild(el);
    }
  }

  renderResult(g);
}

function renderResult(g) {
  const box = $('quizResult');
  if (!answered) { box.style.display = 'none'; $('nextBtn').style.display = 'none'; return; }
  box.style.display = '';
  $('nextBtn').style.display = '';
  const best = g.results[0];
  const pick = g.results.find(r => r.discard === st._pick);
  const v = st._verdict;

  let html = '';
  if (v.tier === 'big') {
    html += `<div class="stop-banner">🛑 STOP — 大きなロスです。最善手を確認してください。</div>`;
  } else if (autoAdvancing) {
    html += `<div class="auto-note">${v.mark} ${v.tier === 'perfect' ? 'ナイス！' : 'OK'} 自動で次の問題へ…（クリックで止めてレビュー）</div>`;
  }
  html += `<div class="verdict ${v.cls}"><span class="vmark">${v.mark}</span> ${v.text}` +
    (v.loss > 0 && v.loss < 1 ? `<span class="lossnum">評価ロス ${(v.loss * 100).toFixed(0)}%</span>` : '') +
    (v.dangerJump > 0.03 ? `<span class="lossnum warn">放銃率 +${(v.dangerJump * 100).toFixed(0)}%</span>` : '') +
    `</div>`;
  html += `<div class="rtable-wrap"><table class="rtable"><thead><tr>` +
    `<th>切る</th><th>向聴</th><th>受け入れ</th><th>ドラ</th><th>放銃率</th></tr></thead><tbody>`;
  const show = g.results.slice(0, 7);
  if (!show.some(r => r.discard === st._pick)) show.push(pick); // 自分の選択は必ず表示
  for (const r of show) {
    const tags = (r.discard === best.discard ? '<span class="pill gold">最善</span>' : '') +
      (r.discard === st._pick ? '<span class="pill blue">あなた</span>' : '');
    html += `<tr class="${r.discard === best.discard ? 'row-best' : ''}${r.discard === st._pick ? ' row-pick' : ''}">` +
      `<td>${tileName(r.discard)} ${tags}</td><td>${fmtSh(r.shanten)}</td>` +
      `<td>${r.ukeireTotal}枚</td><td>${r.dora}</td>` +
      `<td>${g.threats > 0.05 ? (r.dealIn * 100).toFixed(1) + '%' : '—'}</td></tr>`;
  }
  html += `</tbody></table></div>`;
  html += `<div class="rnote">評価 = 手広さ(受け入れ)＋打点(ドラ) を放銃リスクで割り引いた値。${g.threats > 0 ? `相手のテンパイ濃厚度 約${g.threats.toFixed(1)}人ぶんを加味。` : '危険な相手がいないため純粋な牌効率で判定。'}</div>`;
  box.innerHTML = html;
}

// ── 操作 ──
function cancelAuto() {
  if (!autoAdvancing) return;
  autoAdvancing = false; clearTimeout(autoTimer);
  render(); // 自動ノートを消す
}
function onPick(tile) {
  if (answered) return;
  st._pick = tile;
  graded = grade(st);
  answered = true;
  st._verdict = verdict(graded.results.find(r => r.discard === tile), graded.results[0]);
  clearTimeout(autoTimer);
  // 小さいロスは自動で次へ、大きいロス（大ミス）はストップ
  autoAdvancing = (st._verdict.tier === 'perfect' || st._verdict.tier === 'small');
  render();
  if (autoAdvancing) {
    const delay = st._verdict.tier === 'perfect' ? 1300 : 2100;
    autoTimer = setTimeout(() => { if (autoAdvancing) newQuiz(); }, delay);
  }
}
function newQuiz() {
  clearTimeout(autoTimer); autoAdvancing = false;
  const players = parseInt($('playerCount').value, 10) || 4;
  const s = genQuiz(players);
  if (!s) { $('quizHand').textContent = '局面生成に失敗しました。もう一度お試しください。'; return; }
  st = s; st._pick = null; answered = false; graded = null;
  render();
}

$('quizResult').addEventListener('click', cancelAuto);
$('nextBtn').onclick = newQuiz;
$('newQuizTop').onclick = newQuiz;
$('playerCount').onchange = newQuiz;
newQuiz();
