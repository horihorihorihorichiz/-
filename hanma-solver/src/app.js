// app.js — UI グルー
import { parseHand, formatCounts, tileName, totalTiles, suitOf, rankOf } from './tiles.js';
import { shanten } from './shanten.js';
import { analyzeDiscards } from './analyze.js';

const $ = (id) => document.getElementById(id);

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
    } else {
      // 13枚 → 向聴と受け入れのみ
      const sh = shanten(counts, calledMelds);
      $('shantenVal').textContent = fmtShanten(sh.value);
      renderTiles($('handTiles'), counts, aka);
      renderForms(sh);
      $('discardSection').style.display = 'none';
    }
  } catch (e) {
    err.textContent = '⚠ ' + e.message;
    $('resultPanel').style.display = 'none';
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

function renderDiscards(results) {
  const body = $('discardBody');
  body.innerHTML = '';
  for (const r of results) {
    const tr = document.createElement('tr');
    if (r.isBest) tr.className = 'best';

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

    // 最善マーク
    const tdBest = document.createElement('td');
    if (r.isBest) { const p = document.createElement('span'); p.className = 'pill gold'; p.textContent = '最善'; tdBest.appendChild(p); }
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

$('go').onclick = run;
$('hand').addEventListener('keydown', (e) => { if (e.key === 'Enter') run(); });
buildExamples();
run();
