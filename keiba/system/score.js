#!/usr/bin/env node
'use strict';
/**
 * 堀川システム — スコア計算（Ver.99.27 / hori52）
 *
 * 設計図（Artifact「堀川システム設計図」, 2026-08-23版）に記載された
 * 手順2〜5 を Node.js に移植したもの。重みは weights.json（hori52_w.json 由来）。
 *
 * 手順1（16成分そのものの算出）は calc.py 側の定義であり、ここには含まれない。
 * 本実装は「16成分が算出済み」の状態を入力として受け取る。
 *
 * 使い方:
 *   const { scoreRace } = require('./score');
 *   scoreRace({ place:'中山', surf:'芝', band:'M', cls:'t6', horses:[...] })
 *
 *   $ node score.js race.json     レースJSONを採点して表示
 *   $ node score.js --selftest    内蔵の検算を実行
 */

const fs = require('fs');
const path = require('path');

const W = JSON.parse(fs.readFileSync(path.join(__dirname, 'weights.json'), 'utf8'));
const NAMES = W.names;
const IDX = new Map(NAMES.map((n, i) => [n, i]));

/* ------------------------------------------------------------------ *
 * 設計図に数値が書かれていない箇所。すべてここに集約する。
 * 変更する場合はこの定数だけを触ること。
 * ------------------------------------------------------------------ */
const PROVISIONAL = {
  // 距離帯 S/M/L の境界。暫定ではなく確定値。
  // horikawa_v3/hk/features.py:66 が同じ境界を使っている:
  //   return "S" if d <= 1400 else ("M" if d <= 2000 else "L")
  // なお HORIKAWA_FULL.md は「M=1500-1700 / L=1800以上」と書いており実装と矛盾する。
  // 実装側を正とする（logic.md「距離帯の境界」参照）。
  distBand: { S_max: 1400, M_max: 2000 },
  // 得点表示の平行移動。設計図は「見やすさのため100前後に平行移動」とのみ。
  displayCenter: 100,
  // PWin の softmax 温度。設計図に記載なし。
  softmaxTemperature: 1.0,
  // 形（1強/2強/3強/階段/混戦）の判定しきい値。設計図は g12/g23/g34 の
  // 定義のみを示し、しきい値を示していない。下記は暫定値。
  shape: { strong: 1.0, step: 0.5 },
};

const PWIN_CAP = 0.30; // 「上限30%でクリップ後に再正規化」— 設計図に明記あり

/* ------------------------------------------------------------------ *
 * 手順3: 配点ベクトルの解決（2層合成 + フォールバック）
 * ------------------------------------------------------------------ */

/** 全体1本のフォールバック。正本に単独ベクトルが無いため w6 の単純平均で代用する。 */
function globalVector() {
  const cells = Object.values(W.w6);
  return NAMES.map((_, i) => cells.reduce((s, v) => s + v[i], 0) / cells.length);
}

function distBand(meters) {
  if (!Number.isFinite(meters)) throw new Error('distBand: 距離が数値でない');
  if (meters <= PROVISIONAL.distBand.S_max) return 'S';
  if (meters <= PROVISIONAL.distBand.M_max) return 'M';
  return 'L';
}

/**
 * w = 0.5 × w52[場+芝ダ+距離帯] + 0.5 × w30[芝ダ+距離帯+クラス]
 *     ↓ w52が無い → w30のみ ／ w30も無い → w6[芝ダ×距離帯] ／ それも無い → 全体1本
 */
function resolveWeights({ place, surf, band, cls }) {
  const k52 = `${place}${surf}${band}`;
  const k30 = `${surf}${band}/${cls}`;
  const k6 = `${surf}${band}`;
  const v52 = W.w52[k52];
  const v30 = W.w30[k30];

  if (v52 && v30) {
    return {
      layer: `0.5*w52[${k52}] + 0.5*w30[${k30}]`,
      w: NAMES.map((_, i) => 0.5 * v52[i] + 0.5 * v30[i]),
    };
  }
  if (v30) return { layer: `w30[${k30}]`, w: v30.slice() };
  // 設計図の記述は w52 単独のケースに触れていない。層としては存在するので使う。
  if (v52) return { layer: `w52[${k52}] (w30欠落)`, w: v52.slice() };
  if (W.w6[k6]) return { layer: `w6[${k6}]`, w: W.w6[k6].slice() };
  return { layer: '全体1本 (w6平均)', w: globalVector() };
}

/* ------------------------------------------------------------------ *
 * 手順2: レース内Z正規化
 * ------------------------------------------------------------------ */

/** 母集団SD。SD=0（全馬同値）の成分は寄与ゼロとして 0 を返す。 */
function zNormalize(rows) {
  const n = rows.length;
  if (n === 0) return [];
  const stats = NAMES.map((_, i) => {
    const col = rows.map(v => v[i]);
    const mean = col.reduce((s, x) => s + x, 0) / n;
    const sd = Math.sqrt(col.reduce((s, x) => s + (x - mean) ** 2, 0) / n);
    return { mean, sd };
  });
  return rows.map(row => row.map((x, i) => (stats[i].sd === 0 ? 0 : (x - stats[i].mean) / stats[i].sd)));
}

/* ------------------------------------------------------------------ *
 * 手順5: PWin と形
 * ------------------------------------------------------------------ */

/** softmax → 上限30%でクリップ → 残りを再正規化（クリップが安定するまで反復）。 */
function pwin(scores) {
  const t = PROVISIONAL.softmaxTemperature;
  const mx = Math.max(...scores);
  const ex = scores.map(s => Math.exp((s - mx) / t));
  const sum = ex.reduce((a, b) => a + b, 0);
  let p = ex.map(x => x / sum);

  // 一度クリップした馬は以降も上限のまま固定し、残りの馬だけを再正規化する。
  // 固定集合が増えなくなるまで繰り返す。
  const capped = p.map(() => false);
  for (let pass = 0; pass < scores.length; pass++) {
    const newly = p.map((x, i) => !capped[i] && x > PWIN_CAP + 1e-12);
    if (!newly.some(Boolean)) break;
    newly.forEach((c, i) => { if (c) capped[i] = true; });
    const fixed = capped.reduce((s, c) => s + (c ? PWIN_CAP : 0), 0);
    const freeSum = p.reduce((s, x, i) => s + (capped[i] ? 0 : x), 0);
    const rest = Math.max(0, 1 - fixed);
    p = p.map((x, i) => (capped[i] ? PWIN_CAP : (freeSum === 0 ? 0 : (x / freeSum) * rest)));
  }
  return p;
}

/** g12=(1位−2位)/SD, g23, g34。SD はレース内の得点SD。 */
function gaps(sortedScores) {
  const n = sortedScores.length;
  const mean = sortedScores.reduce((s, x) => s + x, 0) / n;
  const sd = Math.sqrt(sortedScores.reduce((s, x) => s + (x - mean) ** 2, 0) / n);
  const g = k => (sd === 0 || sortedScores.length <= k ? 0 : (sortedScores[k - 1] - sortedScores[k]) / sd);
  return { sd, g12: g(1), g23: g(2), g34: g(3) };
}

/** 形の分類。しきい値は設計図に無いため PROVISIONAL.shape の暫定値による。 */
function shapeOf({ g12, g23, g34 }) {
  const { strong, step } = PROVISIONAL.shape;
  if (g12 >= strong) return '1強';
  if (g23 >= strong) return '2強';
  if (g34 >= strong) return '3強';
  if (g12 >= step && g23 >= step && g34 >= step) return '階段';
  return '混戦';
}

/* ------------------------------------------------------------------ *
 * 手順4: 内積 → 得点、並べ替え
 * ------------------------------------------------------------------ */

/**
 * @param {object} race
 *   place  場（札幌/函館/福島/新潟/東京/中山/中京/阪神/小倉/京都）
 *   surf   '芝' | 'ダ'
 *   band   'S' | 'M' | 'L'（未指定なら dist から導出）
 *   dist   距離[m]（band 未指定時に使用）
 *   cls    't3' | 't4' | 't5' | 't6' | 't10'
 *   horses [{ umaban, name, comps:{TSI:…,…}, wavg }]
 *          comps は16成分すべてを含むこと。wavg は同点時の第2キー。
 */
function scoreRace(race) {
  const band = race.band || distBand(race.dist);
  const { layer, w } = resolveWeights({ place: race.place, surf: race.surf, band, cls: race.cls });

  const rows = race.horses.map(h => NAMES.map(n => {
    const x = h.comps[n];
    if (!Number.isFinite(x)) throw new Error(`成分 ${n} が欠落: 馬番${h.umaban}`);
    return x;
  }));

  const Z = zNormalize(rows);
  const raw = Z.map(z => z.reduce((s, x, i) => s + x * w[i], 0));
  const rawMean = raw.reduce((s, x) => s + x, 0) / raw.length;
  const p = pwin(raw);

  const horses = race.horses.map((h, i) => ({
    umaban: h.umaban,
    name: h.name,
    score: raw[i],
    display: raw[i] - rawMean + PROVISIONAL.displayCenter,
    pwin: p[i],
    wavg: Number.isFinite(h.wavg) ? h.wavg : 0,
    // どの成分が効いたかの内訳（Z × 重み）
    parts: Object.fromEntries(NAMES.map((n, k) => [n, Z[i][k] * w[k]])),
  }));

  // 同点の並べ替えは (−得点, −WAvg, 馬番)
  horses.sort((a, b) => (b.score - a.score) || (b.wavg - a.wavg) || (a.umaban - b.umaban));

  const g = gaps(horses.map(h => h.score));
  return {
    layer,
    band,
    weights: Object.fromEntries(NAMES.map((n, i) => [n, w[i]])),
    horses,
    ...g,
    shape: shapeOf(g),
  };
}

/* ------------------------------------------------------------------ *
 * CLI
 * ------------------------------------------------------------------ */

function render(r) {
  const lines = [];
  lines.push(`配点層: ${r.layer}`);
  lines.push(`形: ${r.shape}  g12=${r.g12.toFixed(2)} g23=${r.g23.toFixed(2)} g34=${r.g34.toFixed(2)} SD=${r.sd.toFixed(2)}`);
  lines.push('');
  lines.push('順  馬番  馬名                得点     PWin   効いた成分(上位3)');
  r.horses.forEach((h, i) => {
    const top = Object.entries(h.parts)
      .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
      .slice(0, 3)
      .map(([n, v]) => `${n}${v >= 0 ? '+' : ''}${v.toFixed(1)}`)
      .join(' ');
    lines.push(
      String(i + 1).padStart(2) + '  ' +
      String(h.umaban).padStart(4) + '  ' +
      String(h.name || '').padEnd(16).slice(0, 16) + '  ' +
      h.display.toFixed(1).padStart(7) + '  ' +
      (h.pwin * 100).toFixed(1).padStart(5) + '%  ' + top);
  });
  lines.push('');
  lines.push('※ PWinは順位付けの副産物。確率の絶対値や期待値計算に使わないこと（logic.md 参照）。');
  return lines.join('\n');
}

function selftest() {
  const ok = [];
  const eq = (label, got, want) => {
    const pass = Math.abs(got - want) < 1e-9;
    ok.push(pass);
    console.log(`${pass ? 'ok  ' : 'FAIL'} ${label}: ${got} (expect ${want})`);
  };
  const truthy = (label, cond) => {
    ok.push(!!cond);
    console.log(`${cond ? 'ok  ' : 'FAIL'} ${label}`);
  };
  const comps = v => Object.fromEntries(NAMES.map(n => [n, v]));

  eq('16成分', NAMES.length, 16);
  eq('w52セル数', Object.keys(W.w52).length, 49);
  eq('w30セル数', Object.keys(W.w30).length, 30);
  eq('w6セル数', Object.keys(W.w6).length, 6);
  eq('中山芝M の mgn_abs', W.w52['中山芝M'][IDX.get('mgn_abs')], -75.2);
  truthy('全ベクトルが長さ16', [W.w6, W.w52, W.w30]
    .every(o => Object.values(o).every(v => v.length === 16)));

  // 2層合成の検算
  const mi = IDX.get('mgn_abs');
  const r = resolveWeights({ place: '中山', surf: '芝', band: 'M', cls: 't6' });
  eq('合成 mgn_abs', r.w[mi], 0.5 * -75.2 + 0.5 * W.w30['芝M/t6'][mi]);

  // フォールバック
  eq('w52欠落→w30のみ', resolveWeights({ place: '存在しない場', surf: '芝', band: 'M', cls: 't6' }).w[0], W.w30['芝M/t6'][0]);
  eq('両方欠落→w6', resolveWeights({ place: '存在しない場', surf: '芝', band: 'M', cls: 't99' }).w[0], W.w6['芝M'][0]);
  eq('w6も欠落→全体1本', resolveWeights({ place: 'x', surf: '砂', band: 'X', cls: 't99' }).w[0], globalVector()[0]);

  // 距離帯
  eq('1200m→S', distBand(1200) === 'S' ? 1 : 0, 1);
  eq('1800m→M', distBand(1800) === 'M' ? 1 : 0, 1);
  eq('2400m→L', distBand(2400) === 'L' ? 1 : 0, 1);

  // Z正規化: 定数列は全員0
  eq('SD=0の成分は0', zNormalize([NAMES.map(() => 5), NAMES.map(() => 5)])[0][0], 0);

  // 得点: 全馬同値なら全員0点、PWinは均等
  const flat = scoreRace({
    place: '中山', surf: '芝', band: 'M', cls: 't6',
    horses: [1, 2, 3, 4].map(u => ({ umaban: u, name: `馬${u}`, comps: comps(1) })),
  });
  eq('同値レースの得点', flat.horses[0].score, 0);
  eq('同値レースのPWin', flat.horses[0].pwin, 0.25);
  eq('同値レースの表示得点', flat.horses[0].display, 100);

  // PWinは常に合計1、上限30%
  const skew = scoreRace({
    place: '中山', surf: '芝', band: 'M', cls: 't6',
    horses: [1, 2, 3, 4, 5].map(u => ({
      umaban: u, name: `馬${u}`,
      comps: Object.fromEntries(NAMES.map(n => [n, n === 'DSI' ? u * 10 : 1])),
    })),
  });
  eq('PWin合計', skew.horses.reduce((s, h) => s + h.pwin, 0), 1);
  truthy('PWin上限30%', skew.horses.every(h => h.pwin <= PWIN_CAP + 1e-9));

  // 同点の並べ替え: (−得点, −WAvg, 馬番)
  const tie = scoreRace({
    place: '中山', surf: '芝', band: 'M', cls: 't6',
    horses: [
      { umaban: 7, name: 'A', wavg: 1, comps: comps(1) },
      { umaban: 3, name: 'B', wavg: 9, comps: comps(1) },
      { umaban: 5, name: 'C', wavg: 1, comps: comps(1) },
    ],
  });
  eq('同点1着はWAvg最大', tie.horses[0].umaban, 3);
  eq('同点2着は馬番小', tie.horses[1].umaban, 5);

  // mgn_abs は負の重み: 着差が大きい馬ほど減点される
  const mg = scoreRace({
    place: '中山', surf: '芝', band: 'M', cls: 't6',
    horses: [1, 2].map(u => ({
      umaban: u, name: `馬${u}`,
      comps: Object.fromEntries(NAMES.map(n => [n, n === 'mgn_abs' ? u * 10 : 1])),
    })),
  });
  truthy('着差が小さい馬が上位', mg.horses[0].umaban === 1);

  console.log(`\n${ok.filter(Boolean).length}/${ok.length} passed`);
  process.exit(ok.every(Boolean) ? 0 : 1);
}

if (require.main === module) {
  const arg = process.argv[2];
  if (arg === '--selftest') selftest();
  else if (arg) console.log(render(scoreRace(JSON.parse(fs.readFileSync(arg, 'utf8')))));
  else {
    console.log('usage: node score.js <race.json> | node score.js --selftest');
    process.exit(2);
  }
}

module.exports = {
  NAMES, W, PROVISIONAL, PWIN_CAP,
  distBand, resolveWeights, zNormalize, scoreRace, pwin, gaps, shapeOf, render,
};
