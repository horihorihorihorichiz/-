// quiz.js — 何切るクイズ（相手の河から放銃リスクも加味）
//
// 対局エンジンでリアルな局面を生成 → 「何を切る？」を出題 →
// ソルバー（牌効率＋ドラ＋放銃リスク）で採点し、最善打と評価を表示 → 次の局面へ。

import { N_TILES, tileName, doraFromIndicator, MAN, PIN, SOU } from './tiles.js';
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

  // ドラ牌の集合（表示牌から＋5は全部ドラ）
  const doraTiles = new Set();
  for (const ind of omote) doraTiles.add(doraFromIndicator(ind));
  [MAN + 4, PIN + 4, SOU + 4].forEach(i => doraTiles.add(i));
  // ドラそば（同じスートでドラと2つ以内＝ドラ入り順子を作れる牌）の枚数
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
    // 評価値: 向聴を最優先、同向聴内で「手広さ＋打点(実ドラ＋ドラそばの伸び)」を放銃リスクで割り引く
    const value = (r.ukeireTotal + r.dora * 3 + r.soba * 0.7) * (1 - 0.85 * r.dealIn);
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

// あなたの選択 vs 最善 の直接比較
function renderCompare(best, pick, g) {
  if (!pick || pick.discard === best.discard) return '';
  const cmp = (label, pRaw, bRaw, betterHigh, disp) => {
    const worse = betterHigh ? pRaw < bRaw : pRaw > bRaw;
    return `<tr><td class="cl">${label}</td>` +
      `<td class="${worse ? 'worse' : 'same'}">${disp(pRaw)}</td>` +
      `<td class="pick-best">${disp(bRaw)}</td></tr>`;
  };
  let rows = '';
  rows += cmp('向聴（アガリまで）', pick.shanten, best.shanten, false, v => fmtSh(v));
  rows += cmp('受け入れ（手広さ）', pick.ukeireTotal, best.ukeireTotal, true, v => v + '枚');
  rows += cmp('ドラ（打点）', pick.dora, best.dora, true, v => v + '枚');
  if (g.threats > 0.05) rows += cmp('放銃率（危険）', pick.dealIn, best.dealIn, false, v => (v * 100).toFixed(1) + '%');
  if (pick.ev != null && best.ev != null) rows += cmp('得点期待値', pick.ev, best.ev, true, v => v.toFixed(2) + '点');
  else rows += `<tr><td class="cl">得点期待値</td><td colspan="2" class="ev-wait">計算中…</td></tr>`;

  return `<div class="compare"><div class="cmp-head">📊 あなた と 最善 の比較</div>` +
    `<table class="cmp-table"><thead><tr><th></th>` +
    `<th class="th-pick">あなた ${tileName(pick.discard)}</th>` +
    `<th class="th-best">最善 ${tileName(best.discard)}</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

// 「なぜこれが最善か」の解説（高校生向けの文章）
function explainWhy(best, pick, g) {
  const bt = tileName(best.discard);
  const P = [];
  let formTxt = '4面子1雀頭のふつうの形';
  if (best.forms.includes('chiitoi') && !best.forms.includes('normal')) formTxt = '七対子（対子を7組そろえる形）';
  else if (best.forms.includes('kokushi')) formTxt = '国士無双';
  else if (best.forms.includes('chiitoi')) formTxt = '通常形と七対子の両にらみ';

  P.push(`<b>${bt}切り</b>は向聴を落とさず <b>${fmtSh(best.shanten)}</b> を保ち、受け入れも <b>${best.ukeireTotal}枚</b> と広い。アガリまで最短で、狙う形は${formTxt}。`);
  if (best.dora > 0) P.push(`ドラを <b>${best.dora}枚</b> 確保できるため打点も見込める。韓麻は5がすべて赤ドラなので、5そのものと周辺の価値が大きい。`);
  const menzen = st.melds[0].length === 0;
  const pts = score({ win: 'ron', riichi: menzen, dora: best.dora, players: st.players }).total;
  P.push(`アガった場合の打点は約 <b>${pts}点</b>（役・飜は無く、ロン6＋ドラ${best.dora}${menzen ? '＋リーチ2' : ''}）。`);
  if (best.ev != null) P.push(`これらを総合した<b>得点期待値は約 ${best.ev.toFixed(2)}点</b>（アガリ率 ${(best.winRate * 100).toFixed(0)}% × 平均打点 ${best.avgPoints.toFixed(1)}点）で、これが「実戦で平均どれだけ得か」の指標になる。`);

  if (pick && pick.discard !== best.discard) {
    let bad;
    if (pick.shanten > best.shanten) bad = `${tileName(pick.discard)}切りは向聴が ${fmtSh(pick.shanten)} に後退し、アガリから遠ざかってしまう。`;
    else if (g.threats > 0.1 && pick.dealIn > best.dealIn + 0.02) bad = `${tileName(pick.discard)} は放銃率 ${(pick.dealIn * 100).toFixed(0)}% と危険で、当たれば失点が大きい。${bt}なら相手に刺さりにくく、期待値の目減りを抑えられる。`;
    else if (pick.soba < best.soba) bad = `${tileName(pick.discard)}を切るとドラそばを手放し、打点の伸びしろが減る。`;
    else if (pick.dora < best.dora) bad = `${tileName(pick.discard)}切りはドラが ${best.dora - pick.dora}枚 少なく、打点が下がる。`;
    else bad = `${bt}のほうが受け入れが広く、アガリやすい。`;
    P.push(`<span class="bad">あなたの選択について：${bad}</span>`);
  }
  return `<div class="why"><div class="why-head">📘 解説</div>` + P.map(t => `<p>${t}</p>`).join('') + `</div>`;
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

  // あなたの選択 と 最善 の直接比較
  html += renderCompare(best, pick, g);

  const evReady = g._evDone;
  html += `<div class="rank-caption">🏆 切る牌ランキング（上ほど総合的に良い＝おすすめ順）</div>`;
  html += `<div class="rtable-wrap"><table class="rtable"><thead><tr>` +
    `<th>順位</th><th>切る</th><th>向聴</th><th>受け入れ</th><th>ドラ</th><th>放銃率</th>` +
    `<th>得点期待値${evReady ? '' : ' ⏳'}</th></tr></thead><tbody>`;
  const bestEv = evReady ? Math.max(...shownRows(g).map(r => r.ev ?? -1)) : null;
  for (const r of shownRows(g)) {
    const rank = g.results.findIndex(x => x.discard === r.discard) + 1;
    const tags = (r.discard === best.discard ? '<span class="pill gold">最善</span>' : '') +
      (r.discard === st._pick ? '<span class="pill blue">あなた</span>' : '');
    const evCell = r.ev != null
      ? `<span class="${r.ev === bestEv ? 'ev-top' : ''}">${r.ev.toFixed(2)}点</span>`
      : '<span class="ev-wait">計算中…</span>';
    html += `<tr class="${r.discard === best.discard ? 'row-best' : ''}${r.discard === st._pick ? ' row-pick' : ''}">` +
      `<td class="rank-cell">${rank}位</td>` +
      `<td>${tileName(r.discard)} ${tags}</td><td>${fmtSh(r.shanten)}${formTag(r)}</td>` +
      `<td>${r.ukeireTotal}枚</td><td>${r.dora}</td>` +
      `<td>${g.threats > 0.05 ? (r.dealIn * 100).toFixed(1) + '%' : '—'}</td>` +
      `<td class="num">${evCell}</td></tr>`;
  }
  html += `</tbody></table></div>`;
  html += `<div class="rnote" style="margin-top:6px">この順位は<strong>総合評価</strong>（向聴＝アガリまでの近さ・受け入れ＝手広さ・ドラ＝打点・放銃率＝危険度 を合わせた総合点）の高い順。<strong>得点期待値</strong>＝アガリ率×平均打点をモンテカルロで実測した「平均でどれだけ得するか」の目安。</div>`;

  // 放銃率の理由説明（警戒相手がいるとき）: どの相手の河がどうか まで踏み込む
  if (g.threats > 0.1) {
    const rel = { 1: '下家', 2: st.players === 4 ? '対面' : '上家', 3: '上家' };
    // 警戒すべき相手の状況（河・リーチ）を列挙
    const threatLines = [];
    for (const o of g.oppInfo) {
      if (o.riichi) {
        const after = st.discards[o.p].length - 1 - (st.riichiAt[o.p] ?? 0);
        threatLines.push(`<li><span class="riichi-tag">リーチ</span> <b>AI・${rel[o.p]}</b>：${st.riichiAt[o.p] + 1}巡目に横向きの牌でリーチ宣言。以降${after}巡ぶんは無スジでも押してきた＝手変わりせずテンパイ継続中。当然テンパイなので放銃に直結。`);
      } else if (o.threat >= 0.4) {
        threatLines.push(`<li><b>AI・${rel[o.p]}</b>：河が${o.discards}枚と伸びていて、テンパイしている可能性が高い（警戒）。`);
      }
    }
    const ctxHead = threatLines.length
      ? `<div class="de-ctx">🀫 いま警戒すべき相手：</div><ul class="threat-list">${threatLines.join('')}</ul>`
      : `<div class="de-ctx">🀫 相手の河が伸びていて、テンパイ濃厚な相手が約${g.threats.toFixed(1)}人。放銃に注意。</div>`;
    const furiten = `<div class="de-note">※韓麻は<strong>フリテンが無い</strong>ので、相手の河に切れている牌（＝いわゆる現物）でも当たります。安全牌は「4枚見え」など物理的に待ちに使えない牌だけ。</div>`;

    const reasonBlock = (r, label, cls) => {
      const rs = dangerReasons(r.discard, g.seenAll, g.threats);
      if (!rs.length) return '';
      const items = rs.map(x => `<li class="${x.t}">${x.t === 'risk' ? '⚠' : '✓'} ${x.s}</li>`).join('');
      return `<div class="reason-card ${cls}"><div class="rc-head">${label}：${tileName(r.discard)}（放銃率 ${(r.dealIn * 100).toFixed(1)}%）</div><ul>${items}</ul></div>`;
    };
    html += `<div class="danger-explain">${ctxHead}${furiten}`;
    if (pick.discard !== best.discard && pick.dealIn > best.dealIn + 0.02) {
      html += reasonBlock(pick, 'あなたの選択が危険な理由', 'risk');
      html += reasonBlock(best, '最善が安全な理由', 'safe');
    } else {
      const mostRisk = g.results.slice().sort((a, b) => b.dealIn - a.dealIn)[0];
      if (mostRisk && mostRisk.dealIn > 0.05) html += reasonBlock(mostRisk, 'この手で一番危険な牌', 'risk');
    }
    html += `</div>`;
  }

  // 解説は文末に置く（高校生向けの文章）
  html += explainWhy(best, pick, g);

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
