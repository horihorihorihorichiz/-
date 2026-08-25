// guard.js — 麻雀 守りGTO（通常麻雀・相手の待ち読み）
// リーチした相手の河から「当たらない牌」を読む練習。フリテンありなので
// 現物＝100%安全・スジが効く。小学生にも分かる言葉で答え合わせする。

import { N_TILES, tileName, rankOf, isHonor, MAN, PIN, SOU } from './tiles.js';
import { shanten } from './shanten.js';
import { tileEl } from './tileview.js';

const $ = (id) => document.getElementById(id);
const RI = (n) => Math.floor(Math.random() * n);
const choice = (a) => a[RI(a.length)];
const sum = (c) => c.reduce((x, y) => x + y, 0);
const isWin = (c) => shanten(c, 0).value === -1;

let pos = null;      // 現在の問題
let answered = false;
let pick = -1;
let stats = { done: 0, good: 0 };

function shuffle(a) { for (let i = a.length - 1; i > 0; i--) { const j = RI(i + 1); [a[i], a[j]] = [a[j], a[i]]; } return a; }
function suitBase() { return choice([MAN, PIN, SOU]); }

function waitsOf(c) {
  const w = [];
  for (let t = 0; t < N_TILES; t++) { if (c[t] >= 4) continue; c[t]++; if (isWin(c)) w.push(t); c[t]--; }
  return w;
}

// 相手のテンパイ手を構築（3面子+雀頭+ターツ 等）
function buildTenpai() {
  for (let tries = 0; tries < 500; tries++) {
    const c = new Array(N_TILES).fill(0);
    let ok = true;
    const add = (t, n = 1) => { if (t < 0 || t >= N_TILES || c[t] + n > 4) { ok = false; return; } c[t] += n; };
    const meld = () => {
      if (Math.random() < 0.72) { const b = suitBase(), r = RI(7); add(b + r); add(b + r + 1); add(b + r + 2); }
      else { add(RI(N_TILES), 3); }
    };
    const wt = choice(['ryanmen', 'ryanmen', 'ryanmen', 'kanchan', 'penchan', 'shanpon', 'tanki']);
    if (wt === 'shanpon') { meld(); meld(); meld(); add(RI(N_TILES), 2); add(RI(N_TILES), 2); }
    else if (wt === 'tanki') { meld(); meld(); meld(); meld(); add(RI(N_TILES), 1); }
    else {
      meld(); meld(); meld(); add(RI(N_TILES), 2);
      if (wt === 'ryanmen') { const b = suitBase(), r = 1 + RI(6); add(b + r); add(b + r + 1); }
      else if (wt === 'kanchan') { const b = suitBase(), r = RI(7); add(b + r); add(b + r + 2); }
      else { const b = suitBase(); if (Math.random() < 0.5) { add(b + 0); add(b + 1); } else { add(b + 7); add(b + 8); } }
    }
    if (!ok || sum(c) !== 13 || shanten(c, 0).value !== 0) continue;
    const waits = waitsOf(c);
    if (waits.length === 0 || waits.length > 3) continue;
    return { hand: c, waits };
  }
  return null;
}

// 相手の河（フリテンなので待ち牌は捨てない）
function buildRiver(used, waits, len) {
  const waitSet = new Set(waits); const river = [];
  let guard = 0, mids = 0;
  while (river.length < len && guard++ < 900) {
    // スジ学習のため中張牌(3〜7)を少し混ぜる
    let t;
    if (mids < 3 && Math.random() < 0.5) { const b = suitBase(); t = b + 2 + RI(5); } else { t = RI(N_TILES); }
    if (waitSet.has(t) || used[t] >= 4) continue;
    used[t]++; river.push(t);
    if (!isHonor(t) && rankOf(t) >= 3 && rankOf(t) <= 7) mids++;
  }
  return river;
}

// あなたの手牌（現物・当たり牌・ランダムを混ぜる）
function buildPlayerHand(used, oppRiver, waits) {
  const hand = [];
  const take = (t) => { if (used[t] >= 4) return false; used[t]++; hand.push(t); return true; };
  const genb = shuffle([...new Set(oppRiver)]);
  let g = 0; for (const t of genb) { if (g >= 3) break; if (take(t)) g++; }
  const wl = shuffle([...waits]); let added = 0;
  for (const t of wl) { if (added >= 2) break; if (take(t)) added++; }
  let guard = 0;
  while (hand.length < 13 && guard++ < 900) take(RI(N_TILES));
  hand.sort((a, b) => a - b);
  return { hand, genbutsuCount: g };
}

function genPosition() {
  for (let attempt = 0; attempt < 40; attempt++) {
    const t = buildTenpai(); if (!t) continue;
    const used = t.hand.slice();
    const riverLen = 8 + RI(6);
    const river = buildRiver(used, t.waits, riverLen);
    if (river.length < 6) continue;
    const ph = buildPlayerHand(used, river, t.waits);
    if (ph.genbutsuCount === 0) continue; // 安全な正解が必ずある局面のみ
    return { oppHand: t.hand, waits: new Set(t.waits), waitList: t.waits, river, riverSet: new Set(river), hand: ph.hand };
  }
  return null;
}

// 知っている情報からの安全度分類
function safetyClass(t, riverSet) {
  if (riverSet.has(t)) return 'genbutsu';
  if (isHonor(t)) return 'honor';
  const r = rankOf(t); const base = t - (r - 1);
  const inR = (rk) => riverSet.has(base + (rk - 1));
  if (r === 1) return inR(4) ? 'suji' : 'nosuji';
  if (r === 2) return inR(5) ? 'suji' : 'nosuji';
  if (r === 3) return inR(6) ? 'suji' : 'nosuji';
  if (r === 7) return inR(4) ? 'suji' : 'nosuji';
  if (r === 8) return inR(5) ? 'suji' : 'nosuji';
  if (r === 9) return inR(6) ? 'suji' : 'nosuji';
  const pair = { 4: [1, 7], 5: [2, 8], 6: [3, 9] }[r];
  const a = inR(pair[0]), b = inR(pair[1]);
  return a && b ? 'suji' : (a || b) ? 'halfsuji' : 'nosuji';
}

const CLS_INFO = {
  genbutsu: { badge: '◎現物', cls: 'c-safe', word: '相手が捨てた牌＝100%当たらない' },
  suji: { badge: '○スジ', cls: 'c-ok', word: 'スジで両面には当たらない（たまにカンチャン等）' },
  honor: { badge: '○字牌', cls: 'c-ok', word: '字牌はシャンポン・単騎以外は当たらない' },
  halfsuji: { badge: '△片スジ', cls: 'c-mid', word: '片側だけスジ。少し危険' },
  nosuji: { badge: '△無スジ', cls: 'c-bad', word: 'ヒント無し。危険かも' },
};

function render() {
  // 相手の河
  const rv = $('oppRiver'); rv.innerHTML = '';
  pos.river.forEach((t) => rv.appendChild(tileEl(t, { small: true })));

  // あなたの手牌
  const hand = $('myHand'); hand.innerHTML = '';
  const safest = answered ? recommendSafe() : -1;
  pos.hand.forEach((t, i) => {
    const isPick = answered && i === pick;
    const isSafe = answered && t === safest && !isPick;
    const el = tileEl(t, { pick: isPick, safe: isSafe });
    if (answered) {
      const cls = pos.waits.has(t) ? 'hit' : safetyClass(t, pos.riverSet);
      el.classList.add('mark-' + (pos.waits.has(t) ? 'hit' : CLS_INFO[cls].cls));
      el.style.cursor = 'default';
    } else {
      el.onclick = () => onPick(i);
    }
    hand.appendChild(el);
  });

  $('result').style.display = answered ? '' : 'none';
  $('nextBtn').style.display = answered ? '' : 'none';
  $('scoreDisp').textContent = stats.done ? `正解 ${stats.good}/${stats.done}` : '';
  if (answered) renderResult();
}

// 手牌の中で一番安全な牌（現物優先）を薦める
function recommendSafe() {
  const order = { genbutsu: 0, suji: 1, honor: 1, halfsuji: 2, nosuji: 3, hit: 4 };
  let best = -1, bestRank = 99;
  for (const t of pos.hand) {
    const k = pos.waits.has(t) ? 'hit' : safetyClass(t, pos.riverSet);
    if (order[k] < bestRank) { bestRank = order[k]; best = t; }
  }
  return best;
}

function onPick(i) {
  pick = i; answered = true;
  const t = pos.hand[i];
  const good = !pos.waits.has(t) && (pos.riverSet.has(t) || ['suji', 'honor'].includes(safetyClass(t, pos.riverSet)));
  stats.done++; if (good) stats.good++;
  render();
}

function renderResult() {
  const box = $('result');
  const t = pos.hand[pick];
  const dealtIn = pos.waits.has(t);
  const cls = dealtIn ? 'hit' : safetyClass(t, pos.riverSet);

  let head;
  if (dealtIn) head = `<div class="verdict v-bad"><span class="vm">✗</span> ロン！ <b>${tileName(t)}</b>は当たり牌だった…（放銃）</div>`;
  else if (cls === 'genbutsu') head = `<div class="verdict v-good"><span class="vm">◎</span> 完璧！ <b>${tileName(t)}</b>は現物で100%安全</div>`;
  else if (cls === 'suji' || cls === 'honor') head = `<div class="verdict v-ok"><span class="vm">○</span> ナイス守り！ <b>${tileName(t)}</b>（${CLS_INFO[cls].badge.slice(1)}）で通った</div>`;
  else head = `<div class="verdict v-mid"><span class="vm">△</span> 通ったけど…<b>${tileName(t)}</b>は${CLS_INFO[cls].badge.slice(1)}で危険な選択だった</div>`;

  // 相手の待ち（正解）を公開
  const waitTiles = pos.waitList.map((w) => `${tileSpan(w, { small: true })} ${tileName(w)}`).join(' ');
  head += `<div class="reveal">相手の当たり牌（狙い牌）：<span class="wait-tiles">${waitTiles}</span></div>`;

  // 小学生向け 3ステップ
  head += `<div class="lesson"><div class="l-head">🛡 まもりの3ステップ（この順で探す）</div><ol>` +
    `<li><b>現物（げんぶつ）</b>を さがす：相手が<b>すでに捨てた牌</b>は ぜったい当たらない（フリテンのルール）。◎</li>` +
    `<li><b>スジ</b>：相手が「4」を捨ててたら「1・7」は だいたい安全（両面待ちが作れない）。○</li>` +
    `<li>どっちも無いなら：<b>字牌</b>や<b>1・9のはしっこ</b>が当たりにくい。△</li>` +
    `</ol></div>`;

  // あなたの手牌ごとの安全度
  head += `<div class="cards-head">あなたの牌の安全度</div><div class="tclass">`;
  const seen = new Set();
  for (const tt of pos.hand) {
    if (seen.has(tt)) continue; seen.add(tt);
    const k = pos.waits.has(tt) ? 'hit' : safetyClass(tt, pos.riverSet);
    const info = k === 'hit' ? { badge: '✗当たり', cls: 'c-hit', word: '相手の待ち牌。切ると放銃！' } : CLS_INFO[k];
    head += `<div class="tc ${info.cls}">${tileSpan(tt, { small: true })} <b>${info.badge}</b><span class="tc-word">${info.word}</span></div>`;
  }
  head += `</div><div class="rnote">正解 ${stats.good}/${stats.done}。◎現物→○スジ→△字牌/端 の順で安全。水色枠が今回の最善（一番安全）。</div>`;
  box.innerHTML = head;
}

function tileSpan(idx, opts) { return tileEl(idx, opts || {}).outerHTML; }

function next() {
  const p = genPosition();
  if (!p) { $('result').style.display = ''; $('result').innerHTML = '<div class="verdict v-mid">局面生成に失敗。もう一度。</div>'; return; }
  pos = p; answered = false; pick = -1;
  render();
}

$('newTop').onclick = next;
$('nextBtn').onclick = next;
next();
