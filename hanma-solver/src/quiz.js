// quiz.js — 何切るクイズ（相手の河から放銃リスクも加味）
//
// 対局エンジンでリアルな局面を生成 → 「何を切る？」を出題 →
// ソルバー（牌効率＋ドラ＋放銃リスク）で採点し、最善打と評価を表示 → 次の局面へ。

import { N_TILES, tileName } from './tiles.js';
import { newGame, advance, humanDiscard, humanCall } from './game.js';
import { analyzeDiscards } from './analyze.js';
import { dealInProb, dangerReasons } from './danger.js';
import { score } from './score.js';
import { monteCarloDiscard } from './mc.js';
import { tileEl, backsInto } from './tileview.js';

const $ = (id) => document.getElementById(id);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

let st = null;
let answered = false;
let graded = null;

const FORM_JP = { normal: '通常形', chiitoi: '七対子', kokushi: '国士無双' };

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
        // 分かりやすい「何切る」にするため 1〜2向聴（テンパイ〜2向聴）で出題
        if (humanTurns >= target && sh >= 0 && sh <= 2) return state;
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
  return { results, threats, oppInfo, seenAll, boardSeen };
}

// 表示する行（上位7＋自分の選択）
function shownRows(g) {
  const show = g.results.slice(0, 7);
  const pick = g.results.find(r => r.discard === st._pick);
  if (pick && !show.some(r => r.discard === st._pick)) show.push(pick);
  return show;
}

// 得点期待値（アガリ率×打点）をモンテカルロで実測して各行に付与
function computeEVs() {
  const g = graded;
  const unseen = new Array(N_TILES).fill(4);
  for (let i = 0; i < N_TILES; i++) unseen[i] -= st.hands[0][i] + g.boardSeen[i];
  const turnsLeft = Math.max(2, Math.floor(st.wall.length / st.players));
  setTimeout(() => {
    for (const r of shownRows(g)) {
      if (r.ev != null) continue;
      const c = st.hands[0].slice(); c[r.discard]--;
      const mc = monteCarloDiscard({
        hand13: c, calledMelds: st.melds[0].length, omoteIndicators: st.doraIndicators,
        unseen, turnsLeft, rollouts: 250, players: st.players,
      });
      r.ev = mc.ev; r.winRate = mc.winRate; r.avgPoints = mc.avgPoints;
    }
    g._evDone = true;
    if (answered) render();
  }, 30);
}

function evalValue(r) { return (r.ukeireTotal + r.dora * 3) * (1 - 0.85 * r.dealIn); }

// tier: 'perfect' | 'small' | 'mid' | 'big'
function verdict(pick, best) {
  if (pick.discard === best.discard) return { tier: 'perfect', mark: '◎', text: '大正解！ ベストな一打です', cls: 'v-good', loss: 0 };
  if (pick.shanten > best.shanten)
    return { tier: 'big', mark: '🛑', text: 'これは大きなミス。アガリから遠ざかる牌でした', cls: 'v-bad', loss: 1 };
  const bv = evalValue(best), pv = evalValue(pick);
  const lossFrac = bv > 0 ? 1 - pv / bv : 0;
  const dangerJump = pick.dealIn - best.dealIn;
  if (lossFrac > 0.25 || dangerJump > 0.08)
    return { tier: 'big', mark: '🛑', text: 'これは大きなミス。もっと良い切り牌があります', cls: 'v-bad', loss: lossFrac, dangerJump };
  if (lossFrac > 0.08)
    return { tier: 'mid', mark: '△', text: 'おしい！ あと一歩でした', cls: 'v-mid', loss: lossFrac, dangerJump };
  return { tier: 'small', mark: '○', text: 'ほぼ正解。ベストとほぼ互角です', cls: 'v-ok', loss: lossFrac, dangerJump };
}

// 狙っている形のタグ（七対子・国士のとき表示）
function formTag(r) {
  if (r.forms.includes('kokushi')) return ' <span class="ftag">国士</span>';
  if (r.forms.includes('chiitoi') && !r.forms.includes('normal')) return ' <span class="ftag">七対子</span>';
  if (r.forms.includes('chiitoi')) return ' <span class="ftag">七対子も可</span>';
  return '';
}

// 中学生でも分かる「なぜこれが最善か」の説明
function explainWhy(best, pick, g) {
  const bt = tileName(best.discard);
  const lines = [];
  // 形（通常/七対子/国士）
  let formTxt = 'ふつうの形（4つのメンツ＋1つの対子）';
  if (best.forms.includes('chiitoi') && !best.forms.includes('normal')) formTxt = '七対子（ペアを7つ集める形）';
  else if (best.forms.includes('kokushi')) formTxt = '国士無双';
  else if (best.forms.includes('chiitoi')) formTxt = 'ふつうの形／七対子どちらも狙える';

  lines.push(`<li><b>${bt}</b> を切ると、アガリに一番近い <b>${fmtSh(best.shanten)}</b> をキープできる（目標は${formTxt}）。</li>`);
  lines.push(`<li>切ったあと、手を進めてくれる牌が <b>${best.ukeireTotal}枚</b> 残っている（＝手が広い＝アガリやすい）。</li>`);
  if (best.dora > 0) lines.push(`<li>ドラを <b>${best.dora}枚</b> 残せる（＝アガれたときの点が高い）。5は全部ドラなので大事。</li>`);
  // 韓麻の打点（役・飜は無いので点数で表す）
  const menzen = st.melds[0].length === 0;
  const pts = score({ win: 'ron', riichi: menzen, dora: best.dora, players: st.players }).total;
  lines.push(`<li>この手はアガれれば <b>約${pts}点</b>（韓麻に役・飜は無く、ロン6＋ドラ${best.dora}${menzen ? '＋リーチ2' : ''}）。</li>`);
  if (best.ev != null) lines.push(`<li><b>得点期待値 約${best.ev.toFixed(2)}点</b>（アガリ率${(best.winRate * 100).toFixed(0)}% × 平均打点${best.avgPoints.toFixed(1)}点）。これが「実際どれだけ得か」の目安。</li>`);

  if (pick && pick.discard !== best.discard) {
    if (pick.shanten > best.shanten)
      lines.push(`<li class="bad">あなたの <b>${tileName(pick.discard)}</b> を切ると <b>${fmtSh(pick.shanten)}</b> になり、アガリから1歩遠ざかってしまう。</li>`);
    else if (g.threats > 0.1 && pick.dealIn > best.dealIn + 0.02)
      lines.push(`<li class="bad">あなたの <b>${tileName(pick.discard)}</b> は相手に当たりやすい危険牌（放銃率 ${(pick.dealIn * 100).toFixed(0)}%）。${bt} なら安全。</li>`);
    else if (pick.dora < best.dora)
      lines.push(`<li class="bad">あなたの選択はドラが ${best.dora - pick.dora} 枚少なく、アガったときの点が下がる。</li>`);
    else
      lines.push(`<li class="bad">あなたの選択より <b>${bt}</b> のほうが手が広い（受け入れが多い）。</li>`);
  }
  return `<div class="why"><div class="why-head">📘 かんたん解説</div><ul>${lines.join('')}</ul></div>`;
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
    st.discards[p].forEach((t, i) => {
      const el = tileEl(t, { small: true });
      if (i === st.riichiAt[p]) el.classList.add('riichi-tile');
      river.appendChild(el);
    });
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
    html += `<div class="stop-banner">🛑 STOP — 大きなミスです。下の解説で最善手を確認しよう。</div>`;
  }
  html += `<div class="verdict ${v.cls}"><span class="vmark">${v.mark}</span> ${v.text}` +
    `<span class="best-badge">最善は <b>${tileName(best.discard)}</b></span></div>`;

  // 中学生向けのやさしい解説
  html += explainWhy(best, pick, g);

  const evReady = g._evDone;
  html += `<div class="rtable-wrap"><table class="rtable"><thead><tr>` +
    `<th>切る</th><th>向聴</th><th>受け入れ</th><th>ドラ</th><th>放銃率</th>` +
    `<th>得点期待値${evReady ? '' : ' ⏳'}</th></tr></thead><tbody>`;
  const bestEv = evReady ? Math.max(...shownRows(g).map(r => r.ev ?? -1)) : null;
  for (const r of shownRows(g)) {
    const tags = (r.discard === best.discard ? '<span class="pill gold">最善</span>' : '') +
      (r.discard === st._pick ? '<span class="pill blue">あなた</span>' : '');
    const evCell = r.ev != null
      ? `<span class="${r.ev === bestEv ? 'ev-top' : ''}">${r.ev.toFixed(2)}点</span>`
      : '<span class="ev-wait">計算中…</span>';
    html += `<tr class="${r.discard === best.discard ? 'row-best' : ''}${r.discard === st._pick ? ' row-pick' : ''}">` +
      `<td>${tileName(r.discard)} ${tags}</td><td>${fmtSh(r.shanten)}${formTag(r)}</td>` +
      `<td>${r.ukeireTotal}枚</td><td>${r.dora}</td>` +
      `<td>${g.threats > 0.05 ? (r.dealIn * 100).toFixed(1) + '%' : '—'}</td>` +
      `<td class="num">${evCell}</td></tr>`;
  }
  html += `</tbody></table></div>`;
  html += `<div class="rnote" style="margin-top:6px">得点期待値 ＝ アガリ率 × 平均打点（残り山からモンテカルロで実測）。「もしアガれたら」ではなく「平均でどれだけ得するか」。</div>`;

  // 放銃率の理由説明（警戒相手がいるとき）
  if (g.threats > 0.1) {
    const riichiOpps = g.oppInfo.filter(o => o.riichi).length;
    const ctx = riichiOpps > 0
      ? `<strong>${riichiOpps}人がリーチ</strong>しており放銃の危険が高い局面です。`
      : `相手の河が伸びていて<strong>テンパイ濃厚な相手が約${g.threats.toFixed(1)}人</strong>。放銃に注意。`;
    const reasonBlock = (r, label, cls) => {
      const rs = dangerReasons(r.discard, g.seenAll, g.threats);
      if (!rs.length) return '';
      const items = rs.map(x => `<li class="${x.t}">${x.t === 'risk' ? '⚠' : '✓'} ${x.s}</li>`).join('');
      return `<div class="reason-card ${cls}"><div class="rc-head">${label}：${tileName(r.discard)}（放銃率 ${(r.dealIn * 100).toFixed(1)}%）</div><ul>${items}</ul></div>`;
    };
    html += `<div class="danger-explain"><div class="de-ctx">🀫 ${ctx}</div>`;
    // 危険な選択をしたら、その理由を強調
    if (pick.discard !== best.discard && pick.dealIn > best.dealIn + 0.02) {
      html += reasonBlock(pick, 'あなたの選択が危険な理由', 'risk');
      html += reasonBlock(best, '最善が安全な理由', 'safe');
    } else {
      // そうでなければ手牌中で最も危険な牌を教材として説明
      const mostRisk = g.results.slice().sort((a, b) => b.dealIn - a.dealIn)[0];
      if (mostRisk && mostRisk.dealIn > 0.05) html += reasonBlock(mostRisk, 'この手で一番危険な牌', 'risk');
    }
    html += `</div>`;
  }

  html += `<div class="rnote">評価 = 手広さ(受け入れ)＋打点(ドラ) を放銃リスクで割り引いた値。${g.threats > 0 ? `相手のテンパイ濃厚度 約${g.threats.toFixed(1)}人ぶんを加味。` : '危険な相手がいないため純粋な牌効率で判定。'}</div>`;
  box.innerHTML = html;
}

// ── 操作 ──
function onPick(tile) {
  if (answered) return;
  st._pick = tile;
  graded = grade(st);
  answered = true;
  st._verdict = verdict(graded.results.find(r => r.discard === tile), graded.results[0]);
  render(); // 自動で次へは行かない。ユーザーが「次の問題へ」を押すまで結果を表示。
  computeEVs(); // 得点期待値をモンテカルロで実測 → 完了後に再描画
}
function newQuiz() {
  const players = parseInt($('playerCount').value, 10) || 4;
  const s = genQuiz(players);
  if (!s) { $('quizHand').textContent = '局面生成に失敗しました。もう一度お試しください。'; return; }
  st = s; st._pick = null; answered = false; graded = null;
  render();
}

$('nextBtn').onclick = newQuiz;
$('newQuizTop').onclick = newQuiz;
$('playerCount').onchange = newQuiz;
newQuiz();
