// app.js — UI グルー
import { parseHand, formatCounts, tileName, totalTiles, suitOf, rankOf, N_TILES } from './tiles.js';
import { shanten } from './shanten.js';
import { analyzeDiscards } from './analyze.js';
import { dealInProb, DANGER_CONFIG } from './danger.js';

const $ = (id) => document.getElementById(id);

// 直近の14枚解析の状態（EV解析で参照）
let lastAnalysis = null; // { counts, aka, calledMelds, omoteIndicators, seen, threats, results }

// 場の見え牌 counts（自分の手牌は含まない: 表ドラ表示 + 見え牌入力）。ウケイレ計算用。
function buildBoardSeen(omoteIndicators, seenStr) {
  const seen = new Array(N_TILES).fill(0);
  for (const t of omoteIndicators) seen[t]++;
  if (seenStr && seenStr.trim()) {
    const { tiles } = parseHand(seenStr.trim());
    for (const t of tiles) seen[t]++;
  }
  return seen;
}

// 危険度用の全見え牌（場の見え牌 + 自分の手牌）。相手が持てない枚数の推定に使う。
function combineSeen(boardSeen, counts) {
  const s = boardSeen.slice();
  for (let i = 0; i < N_TILES; i++) s[i] = Math.min(4, s[i] + counts[i]);
  return s;
}

const EXAMPLES = [
  { label: '2向聴の何切る', hand: '13m22456p13899s5z6z', dora: '4p' },
  { label: '1向聴の何切る', hand: '234m567m22p678p135s', dora: '' },
  { label: '赤5含み', hand: '0m345m678m234p88p24s', dora: '3s' },
  { label: '七対子1向聴', hand: '1122m3344p55s678s9s', dora: '' },
  { label: '国士1向聴', hand: '19m19p19s124567z11z', dora: '' },
];

// 牌1つを DOM 要素に
function tileEl(idx, opts = {}) {
  const el = document.createElement('span');
  const s = suitOf(idx);
  el.className = `tile ${s}` + (opts.small ? ' small' : '') + (opts.red ? ' red' : '');
  el.textContent = tileName(idx); // "3m" "東" など
  if (opts.red) el.title = '赤ドラ';
  return el;
}

function renderTiles(container, counts, akaBySuit = { m: 0, p: 0, s: 0 }) {
  container.innerHTML = '';
  const aka = { ...akaBySuit };
  for (let i = 0; i < 34; i++) {
    for (let k = 0; k < counts[i]; k++) {
      const s = suitOf(i);
      const isRedFive = i < 27 && rankOf(i) === 5 && aka[s] > 0;
      if (isRedFive) aka[s]--;
      container.appendChild(tileEl(i, { red: isRedFive }));
    }
  }
}

function parseIndicators(str) {
  if (!str.trim()) return [];
  const { tiles } = parseHand(str.trim());
  return tiles;
}

function run() {
  const err = $('err');
  err.textContent = '';
  try {
    const handStr = $('hand').value.trim();
    const { counts, aka } = parseHand(handStr);
    const n = totalTiles(counts);
    const calledMelds = Math.max(0, Math.min(4, parseInt($('melds').value || '0', 10) || 0));
    const expected = 13 - calledMelds * 3 + 0; // 13枚形（打牌前は14）
    if (n !== expected && n !== expected + 1) {
      throw new Error(`牌数が合いません（${n}枚）。鳴き${calledMelds}なら手牌は${expected}枚(解析は${expected + 1}枚)想定です。`);
    }
    const omoteIndicators = parseIndicators($('dora').value);
    const threats = Math.max(0, Math.min(3, parseInt($('threats').value || '0', 10) || 0));
    const boardSeen = buildBoardSeen(omoteIndicators, $('seen').value);
    const seenAll = combineSeen(boardSeen, counts); // 危険度用（手牌込み）

    $('resultPanel').style.display = '';

    if (n === expected + 1) {
      // 14枚 → 打牌解析（ウケイレは場の見え牌のみ、手牌は ukeire 内で加算）
      const results = analyzeDiscards({ counts, aka, calledMelds, omoteIndicators, seen: boardSeen });
      for (const r of results) {
        r.dealInProb = dealInProb(r.discard, seenAll, threats);
      }
      const sh = shanten(counts, calledMelds);
      $('shantenVal').textContent = fmtShanten(results[0].shanten) + ' 目標';
      renderTiles($('handTiles'), counts, aka);
      renderForms(sh);
      // renderDiscards は lastAnalysis.threats を参照するため先に確定させる
      lastAnalysis = { counts, aka, calledMelds, omoteIndicators, boardSeen, threats, results };
      renderDiscards(results);
      $('discardSection').style.display = '';
      $('goEV').disabled = false;
      $('progress').style.display = 'none';
    } else {
      // 13枚 → 向聴と受け入れのみ
      const sh = shanten(counts, calledMelds);
      $('shantenVal').textContent = fmtShanten(sh.value);
      renderTiles($('handTiles'), counts, aka);
      renderForms(sh);
      $('discardSection').style.display = 'none';
      lastAnalysis = null;
      $('goEV').disabled = true;
    }
  } catch (e) {
    err.textContent = '⚠ ' + e.message;
    $('resultPanel').style.display = 'none';
    lastAnalysis = null;
    $('goEV').disabled = true;
  }
}

function fmtShanten(v) {
  if (v <= -1) return 'アガリ';
  if (v === 0) return 'テンパイ';
  return v + '向聴';
}

function renderForms(sh) {
  const c = $('formTags');
  c.innerHTML = '';
  const names = { normal: '通常形', chiitoi: '七対子', kokushi: '国士無双' };
  for (const f of sh.forms) {
    const tag = document.createElement('span');
    tag.className = 'form-tag';
    tag.textContent = names[f] + '（' + fmtShanten(sh[f]) + '）';
    tag.style.marginRight = '8px';
    c.appendChild(tag);
  }
}

function renderDiscards(results, evMode = false) {
  const body = $('discardBody');
  body.innerHTML = '';
  const threats = lastAnalysis?.threats || 0;
  const useNet = evMode && threats > 0;
  const metric = (r) => useNet ? (r.netEv ?? -Infinity) : (r.ev ?? -Infinity);
  const bestVal = evMode ? Math.max(...results.map(metric)) : null;
  for (const r of results) {
    const tr = document.createElement('tr');
    tr.dataset.discard = r.discard;
    const isBest = evMode ? (metric(r) === bestVal) : r.isBest;
    if (isBest) tr.className = 'best';

    // 切る牌
    const tdD = document.createElement('td');
    const t = document.createElement('span'); t.className = 'tiles';
    t.appendChild(tileEl(r.discard, { small: true, red: r.discardsRed }));
    tdD.appendChild(t);
    if (r.discardsRed) {
      const p = document.createElement('span'); p.className = 'pill red'; p.textContent = '赤切り'; p.style.marginLeft = '6px';
      tdD.appendChild(p);
    }
    tr.appendChild(tdD);

    // 向聴
    const tdS = document.createElement('td'); tdS.textContent = fmtShanten(r.shanten); tr.appendChild(tdS);

    // 受け入れ枚数
    const tdU = document.createElement('td'); tdU.className = 'num';
    tdU.innerHTML = `<strong>${r.ukeireTotal}</strong>枚` +
      (r.ukeireLoss ? ` <span class="loss">(-${r.ukeireLoss})</span>` : '');
    tr.appendChild(tdU);

    // 有効牌
    const tdT = document.createElement('td'); tdT.className = 'tiles';
    for (const ut of r.ukeireTiles) {
      const wrap = document.createElement('span'); wrap.className = 'tiles';
      wrap.style.marginRight = '2px';
      wrap.appendChild(tileEl(ut.idx, { small: true }));
      const cnt = document.createElement('span'); cnt.style.fontSize = '.65rem'; cnt.style.color = 'var(--muted)';
      cnt.textContent = ut.count; wrap.appendChild(cnt);
      tdT.appendChild(wrap);
    }
    if (!r.ukeireTiles.length) tdT.textContent = '—';
    tr.appendChild(tdT);

    // ドラ
    const tdDora = document.createElement('td'); tdDora.className = 'num'; tdDora.textContent = r.dora; tr.appendChild(tdDora);

    // 放銃率
    const tdDanger = document.createElement('td'); tdDanger.className = 'num';
    if (threats > 0 && r.dealInProb != null) {
      const pct = r.dealInProb * 100;
      const cls = pct >= 12 ? 'danger-hi' : pct >= 6 ? 'danger-mid' : 'danger-lo';
      tdDanger.innerHTML = `<span class="${cls}">${pct.toFixed(1)}%</span>`;
    } else tdDanger.textContent = '–';
    tr.appendChild(tdDanger);

    // アガリ率 / 平均打点 / アガリEV / 正味EV（MC後のみ）
    const tdWin = document.createElement('td'); tdWin.className = 'num';
    const tdPts = document.createElement('td'); tdPts.className = 'num';
    const tdEv = document.createElement('td'); tdEv.className = 'num';
    const tdNet = document.createElement('td'); tdNet.className = 'num';
    if (r.ev != null) {
      tdWin.textContent = (r.winRate * 100).toFixed(1) + '%';
      tdPts.textContent = r.avgPoints.toFixed(1);
      const evBest = useNet ? false : isBest;
      tdEv.innerHTML = `<span class="${evBest ? 'ev-strong' : ''}">${r.ev.toFixed(2)}</span>`;
      if (threats > 0 && r.netEv != null) {
        const netLoss = bestVal != null && metric(r) < bestVal ? ` <span class="evloss">(-${(bestVal - r.netEv).toFixed(2)})</span>` : '';
        tdNet.innerHTML = `<span class="${isBest ? 'ev-strong' : ''}">${r.netEv.toFixed(2)}</span>${netLoss}`;
      } else tdNet.textContent = '–';
    } else {
      tdWin.textContent = tdPts.textContent = tdEv.textContent = tdNet.textContent = '–';
    }
    tr.appendChild(tdWin); tr.appendChild(tdPts); tr.appendChild(tdEv); tr.appendChild(tdNet);

    // 最善マーク
    const tdBest = document.createElement('td');
    if (isBest) {
      const p = document.createElement('span'); p.className = 'pill gold';
      p.textContent = evMode ? (useNet ? '正味最善' : 'EV最善') : '最善'; tdBest.appendChild(p);
    }
    tr.appendChild(tdBest);

    body.appendChild(tr);
  }
}

// 例題ボタン
function buildExamples() {
  const box = $('examples');
  for (const ex of EXAMPLES) {
    const b = document.createElement('button');
    b.textContent = ex.label;
    b.onclick = () => { $('hand').value = ex.hand; $('dora').value = ex.dora; run(); };
    box.appendChild(b);
  }
}

// ── EV解析（モンテカルロ, Web Worker）──
const ROLLOUTS = 500;      // 1候補あたり試行数
const MAX_CANDIDATES = 8;  // 上位いくつを解析するか
let evWorker = null;

function runEV() {
  if (!lastAnalysis) return;
  const { counts, aka, calledMelds, omoteIndicators, boardSeen, threats, results } = lastAnalysis;
  const turnsLeft = Math.max(1, Math.min(18, parseInt($('turns').value || '12', 10) || 12));
  const players = 4;

  // 山とみなす残り: 4枚 − 手牌 − 場の見え牌（表ドラ表示・相手の河など）
  const unseen = new Array(N_TILES).fill(4);
  for (let i = 0; i < N_TILES; i++) unseen[i] -= counts[i] + boardSeen[i];

  const cands = results.slice(0, MAX_CANDIDATES);
  const jobs = cands.map(r => {
    const c = counts.slice(); c[r.discard]--;
    const akaCount = (aka.m + aka.p + aka.s) - (r.discardsRed ? 1 : 0);
    return { discard: r.discard, hand13: c, akaCount };
  });

  // UI: 進捗表示・ボタン無効化
  $('goEV').disabled = true; $('go').disabled = true;
  const prog = $('progress'); prog.style.display = '';
  $('progressBar').style.width = '0%';
  $('progressText').textContent = `EV解析中… 0 / ${jobs.length}`;

  if (evWorker) evWorker.terminate();
  evWorker = new Worker(new URL('./mc-worker.js', import.meta.url), { type: 'module' });

  const byDiscard = new Map(results.map(r => [r.discard, r]));
  let done = 0;
  evWorker.onmessage = (e) => {
    const m = e.data;
    if (m.type === 'progress') {
      const r = byDiscard.get(m.discard);
      if (r) { r.ev = m.result.ev; r.winRate = m.result.winRate; r.avgPoints = m.result.avgPoints; r.tsumoRate = m.result.tsumoRate; }
      done++;
      const pct = Math.round((done / jobs.length) * 100);
      $('progressBar').style.width = pct + '%';
      $('progressText').textContent = `EV解析中… ${done} / ${jobs.length}`;
    } else if (m.type === 'done') {
      // 正味EV = アガリEV − 放銃率 × 平均失点
      for (const r of results) {
        if (r.ev != null) r.netEv = r.ev - (r.dealInProb || 0) * DANGER_CONFIG.avgLoss;
      }
      const key = threats > 0 ? (r => r.netEv ?? -Infinity) : (r => r.ev ?? -Infinity);
      const sorted = [...results].sort((a, b) => key(b) - key(a));
      lastAnalysis.results = sorted;
      renderDiscards(sorted, true);
      const best = sorted[0];
      const label = threats > 0 ? '正味EV ' : 'EV ';
      const val = threats > 0 ? best.netEv : best.ev;
      $('shantenVal').textContent = label + (val != null ? val.toFixed(2) : '–');
      $('progressText').textContent = `完了（各${ROLLOUTS}試行 / 残り${turnsLeft}巡 / 警戒${threats}人）`;
      $('progressBar').style.width = '100%';
      $('goEV').disabled = false; $('go').disabled = false;
      evWorker.terminate(); evWorker = null;
    }
  };
  evWorker.onerror = (err) => {
    $('err').textContent = '⚠ EV解析エラー: ' + err.message;
    $('goEV').disabled = false; $('go').disabled = false;
    prog.style.display = 'none';
  };
  evWorker.postMessage({
    type: 'run',
    jobs,
    common: { calledMelds, omoteIndicators, unseen, turnsLeft, rollouts: ROLLOUTS, players },
  });
}

$('go').onclick = run;
$('goEV').onclick = runEV;
$('goEV').disabled = true;
$('hand').addEventListener('keydown', (e) => { if (e.key === 'Enter') run(); });
buildExamples();
run();
