// 簡易テスト: node hanma-solver/test/engine.test.mjs で実行
import { parseHand, tileName } from '../src/tiles.js';
import { shanten, normalShanten } from '../src/shanten.js';
import { ukeire } from '../src/ukeire.js';
import { analyzeDiscards } from '../src/analyze.js';
import { score, countDora } from '../src/score.js';
import { monteCarloDiscard } from '../src/mc.js';

let pass = 0, fail = 0;
function eq(name, got, want) {
  const ok = got === want;
  console.log(`${ok ? '✅' : '❌'} ${name}: got=${got} want=${want}`);
  ok ? pass++ : fail++;
}

// --- shanten ---
const shOf = (s) => shanten(parseHand(s).counts).value;

eq('完成形(4面子1雀頭)', shOf('123456789m123p11s'), -1);
eq('テンパイ 単騎', shOf('123456789m123p1s'), 0);
eq('テンパイ 両面', shOf('123456789m12p11s'), 0);
eq('1向聴', shOf('123456789m13p11s'), 0); // 13pは嵌張→テンパイ相当
eq('七対子 完成', shOf('11223344556677m'), -1);
eq('七対子 テンパイ', shOf('1122334455667m'), 0);
eq('七対子 1向聴', shOf('112233445566m7p'), 0); // 6対子+1浮き=テンパイ
eq('国士 テンパイ(13面)', shOf('19m19p19s1234567z'), 0);
eq('国士 完成', shOf('119m19p19s1234567z'), -1);
eq('バラバラ手', shOf('147m258p369s1234z'), 6);

// --- ukeire ---
const h = parseHand('123456789m12p11s'); // 両面テンパイ 3p/待ちは? 12p→3p, また 1s雀頭。待ちは3p
const uk = ukeire(h.counts);
eq('両面テンパイ 受け入れ種類', uk.tiles.length, 1);
eq('両面テンパイ 受け入れ牌', uk.tiles[0] ? tileName(uk.tiles[0].idx) : '-', '3p');
eq('両面テンパイ 枚数', uk.total, 4);

// --- analyze (14枚 → 打牌) ---
const a = analyzeDiscards({ counts: parseHand('123456789m123p1s1z').counts, aka: {m:0,p:0,s:0} });
// 1s か 1z を切ればテンパイ。best は shanten 0
eq('打牌解析 best向聴', a[0].shanten, 0);

// --- score（粗品動画 #21-1 の数字に準拠）---
const scRon = score({ win: 'ron', riichi: true, dora: 2, players: 4 });
eq('点数 リーチ+ドラ2 ロン', scRon.total, 10); // 6 + ドラ2 + リーチ2
const scTri = score({ win: 'tsumo', riichi: true, dora: 0, players: 4 });
eq('点数 リーチツモ 計8', scTri.total, 8);      // 2×3 + リーチ2（フラット）
const scTd = score({ win: 'tsumo', riichi: false, dora: 1, players: 4 });
eq('点数 ツモ ドラ1', scTd.total, 9);           // (2+1)×3
const scK = score({ win: 'ron', kokushi: true, players: 4 });
eq('点数 国士 ロン', scK.total, 20);
const scKt = score({ win: 'tsumo', kokushi: true, players: 4 });
eq('点数 国士 ツモ (計60)', scKt.total, 60);    // 20×3
const scCap = score({ win: 'ron', riichi: false, dora: 30, players: 4 });
eq('点数 1人あたり上限20', scCap.perPayer, 20);

// --- dora count ---
const dh = parseHand('55m'); // 5m2枚, ドラ表示4m → ドラ5m が2枚
eq('ドラ計算 表示4m→5m×2', countDora(parseHand('55m').counts, 0, [parseHand('4m').tiles[0]]), 2);
eq('ドラ計算 赤2枚', countDora(parseHand('11m').counts, 2, []), 2);

// --- 高速向聴 vs ブルートフォース参照（乱数ハンド） ---
function refShanten(counts, called = 0) {
  const c = counts.slice(); let best = 8;
  (function rec(i, m, t, h) {
    while (i < 34 && c[i] === 0) i++;
    if (i >= 34) { const mm = Math.min(m, 4); const sh = 8 - 2 * mm - Math.min(t, 4 - mm) - (h ? 1 : 0); if (sh < best) best = sh; return; }
    const inS = i < 27, r = i % 9;
    if (c[i] >= 3) { c[i] -= 3; rec(i, m + 1, t, h); c[i] += 3; }
    if (inS && r <= 6 && c[i + 1] > 0 && c[i + 2] > 0) { c[i]--; c[i + 1]--; c[i + 2]--; rec(i, m + 1, t, h); c[i]++; c[i + 1]++; c[i + 2]++; }
    if (c[i] >= 2 && !h) { c[i] -= 2; rec(i, m, t, true); c[i] += 2; }
    if (c[i] >= 2) { c[i] -= 2; rec(i, m, t + 1, h); c[i] += 2; }
    if (inS && r <= 7 && c[i + 1] > 0) { c[i]--; c[i + 1]--; rec(i, m, t + 1, h); c[i]++; c[i + 1]++; }
    if (inS && r <= 6 && c[i + 2] > 0) { c[i]--; c[i + 2]--; rec(i, m, t + 1, h); c[i]++; c[i + 2]++; }
    c[i]--; rec(i, m, t, h); c[i]++;
  })(0, called, 0, false);
  return best;
}
let shMis = 0;
for (let k = 0; k < 5000; k++) {
  const called = k % 3, n = 13 - called * 3 + (k % 2);
  const c = new Array(34).fill(0);
  for (let placed = 0, g = 0; placed < n && g < 999; g++) { const i = Math.floor(Math.random() * 34); if (c[i] < 4) { c[i]++; placed++; } }
  if (normalShanten(c, called) !== refShanten(c, called)) shMis++;
}
eq('高速向聴 = 参照実装（5000乱数）', shMis, 0);

// --- モンテカルロ スモーク（統計的・緩い下限）---
const tenpai = parseHand('123456789m1122p').counts; // 3p/待ち相当のテンパイ
const unseen = new Array(34).fill(4);
for (let i = 0; i < 34; i++) unseen[i] -= tenpai[i];
const mc = monteCarloDiscard({ hand13: tenpai, akaCount: 0, calledMelds: 0, omoteIndicators: [], unseen, turnsLeft: 16, rollouts: 500, players: 4 });
eq('MC winRate ∈ [0,1]', mc.winRate >= 0 && mc.winRate <= 1, true);
eq('MC テンパイのアガリ率 > 0.4', mc.winRate > 0.4, true);
eq('MC EV = winRate×打点', Math.abs(mc.ev - mc.winRate * mc.avgPoints) < 1e-9, true);

console.log(`\n=== ${pass} passed, ${fail} failed ===`);
process.exit(fail ? 1 : 0);
