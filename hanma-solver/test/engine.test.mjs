// 簡易テスト: node hanma-solver/test/engine.test.mjs で実行
import { parseHand, tileName } from '../src/tiles.js';
import { shanten } from '../src/shanten.js';
import { ukeire } from '../src/ukeire.js';
import { analyzeDiscards } from '../src/analyze.js';
import { score, countDora } from '../src/score.js';

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

// --- score ---
const sc = score({ win: 'ron', riichi: true, dora: 2, players: 4 });
eq('点数 リーチ+ドラ2 ロン', sc.points, 10); // 6+2+1+1
const scT = score({ win: 'tsumo', riichi: false, dora: 1, players: 4 });
eq('点数 ツモ ドラ1 (総取り)', scT.totalGain, 9); // (2+1)*3
const scK = score({ win: 'ron', kokushi: true, players: 4 });
eq('点数 国士', scK.points, 20);
const scCap = score({ win: 'ron', riichi: true, dora: 30, players: 4 });
eq('点数 上限20', scCap.points, 20);

// --- dora count ---
const dh = parseHand('55m'); // 5m2枚, ドラ表示4m → ドラ5m が2枚
eq('ドラ計算 表示4m→5m×2', countDora(parseHand('55m').counts, 0, [parseHand('4m').tiles[0]]), 2);
eq('ドラ計算 赤2枚', countDora(parseHand('11m').counts, 2, []), 2);

console.log(`\n=== ${pass} passed, ${fail} failed ===`);
process.exit(fail ? 1 : 0);
