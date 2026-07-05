// app.js — UI グルー
import { parseHand, formatCounts, tileName, totalTiles, suitOf, rankOf, N_TILES } from './tiles.js';
import { shanten } from './shanten.js';
import { analyzeDiscards } from './analyze.js';

const $ = (id) => document.getElementById(id);

// 直近の14枚解析の状態（EV解析で参照）
let lastAnalysis = null; // { counts, aka, calledMelds, omoteIndicators, results }

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

    $('resultPanel').style.display = '';

    if (n === expected + 1) {
      // 14枚 → 打牌解析
      const results = analyzeDiscards({ counts, aka, calledMelds, omoteIndicators });
      const sh = shanten(counts, calledMelds);
      $('shantenVal').textContent = fmtShanten(results[0].shanten) + ' 目標';
      renderTiles($('handTiles'), counts, aka);
      renderForms(sh);
      renderDiscards(results);
      $('discardSection').style.display = '';
      lastAnalysis = { counts, aka, calledMelds, omoteIndicators, results };
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
  const bestEv = evMode ? Math.max(...results.map(r => r.ev ?? -Infinity)) : null;
  for (const r of results) {
    const tr = document.createElement('tr');
    tr.dataset.discard = r.discard;
    const isBest = evMode ? (r.ev === bestEv) : r.isBest;
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

    // アガリ率 / 平均打点 / EV（MC後のみ）
    const tdWin = document.createElement('td'); tdWin.className = 'num win';
    const tdPts = document.createElement('td'); tdPts.className = 'num pts';
    const tdEv = document.createElement('td'); tdEv.className = 'num ev';
    if (r.ev != null) {
      tdWin.textContent = (r.winRate * 100).toFixed(1) + '%';
      tdPts.textContent = r.avgPoints.toFixed(1);
      const evLoss = bestEv != null && r.ev < bestEv ? ` <span class="evloss">(-${(bestEv - r.ev).toFixed(2)})</span>` : '';
      tdEv.innerHTML = `<span class="${isBest ? 'ev-strong' : ''}">${r.ev.toFixed(2)}</span>${evLoss}`;
    } else {
      tdWin.textContent = tdPts.textContent = tdEv.textContent = '–';
    }
    tr.appendChild(tdWin); tr.appendChild(tdPts); tr.appendChild(tdEv);

    // 最善マーク
    const tdBest = document.createElement('td');
    if (isBest) {
      const p = document.createElement('span'); p.className = 'pill gold';
      p.textContent = evMode ? 'EV最善' : '最善'; tdBest.appendChild(p);
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
  const { counts, aka, calledMelds, omoteIndicators, results } = lastAnalysis;
  const turnsLeft = Math.max(1, Math.min(18, parseInt($('turns').value || '12', 10) || 12));
  const players = 4;

  // 場に見えている牌: 自分の手牌14枚 + 表ドラ表示牌 を除いた残りを山とみなす（v1近似）
  const unseen = new Array(N_TILES).fill(4);
  for (let i = 0; i < N_TILES; i++) unseen[i] -= counts[i];
  for (const t of omoteIndicators) unseen[t]--;

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
      // 解析した候補を EV 降順、未解析は末尾へ
      const sorted = [...results].sort((a, b) => (b.ev ?? -Infinity) - (a.ev ?? -Infinity));
      lastAnalysis.results = sorted;
      renderDiscards(sorted, true);
      const best = sorted[0];
      $('shantenVal').textContent = 'EV ' + (best.ev != null ? best.ev.toFixed(2) : '–');
      $('progressText').textContent = `完了（各${ROLLOUTS}試行 / 残り${turnsLeft}巡）`;
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
