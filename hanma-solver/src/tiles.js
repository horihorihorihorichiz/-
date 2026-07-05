// tiles.js — 牌モデルと表記の相互変換
//
// 牌は 0-33 のインデックスで表す（count 配列 length 34 が基本表現）:
//   0-8   : 1m-9m（萬子）
//   9-17  : 1p-9p（筒子）
//   18-26 : 1s-9s（索子）
//   27-33 : 字牌 東(1z) 南(2z) 西(3z) 北(4z) 白(5z) 發(6z) 中(7z)
//
// 赤5は count 配列とは別に「赤の枚数」として保持する（0m/0p/0s 表記で入力）。

export const SUITS = ['m', 'p', 's', 'z'];
export const HONORS = ['東', '南', '西', '北', '白', '發', '中'];

export const N_TILES = 34;

// 数牌スート開始インデックス
export const MAN = 0;
export const PIN = 9;
export const SOU = 18;
export const HONOR = 27;

export function isHonor(idx) { return idx >= HONOR; }
export function isNumber(idx) { return idx < HONOR; }
export function suitOf(idx) {
  if (idx < PIN) return 'm';
  if (idx < SOU) return 'p';
  if (idx < HONOR) return 's';
  return 'z';
}
// スート内の数（数牌なら 1-9、字牌なら 1-7）
export function rankOf(idx) {
  if (idx < HONOR) return (idx % 9) + 1;
  return idx - HONOR + 1;
}
// 端牌（1/9）または字牌か（国士・么九判定用）
export function isTerminalOrHonor(idx) {
  if (isHonor(idx)) return true;
  const r = rankOf(idx);
  return r === 1 || r === 9;
}

export const TERMINALS_AND_HONORS = (() => {
  const arr = [];
  for (const base of [MAN, PIN, SOU]) { arr.push(base + 0, base + 8); }
  for (let i = HONOR; i < N_TILES; i++) arr.push(i);
  return arr; // 13種
})();

// 1牌インデックス → 表記文字列（"3m" "東" など）
export function tileName(idx) {
  const s = suitOf(idx);
  if (s === 'z') return HONORS[idx - HONOR];
  return rankOf(idx) + s;
}

// "123m0p789s11z" のような表記 → { counts:Int[34], aka:{m,p,s}, tiles:[idx...] }
// 0m/0p/0s は赤5（rank5 として counts に加算し、aka も +1）
export function parseHand(str) {
  const counts = new Array(N_TILES).fill(0);
  const aka = { m: 0, p: 0, s: 0 };
  const tiles = [];
  const clean = (str || '').replace(/\s+/g, '');
  let digits = [];
  for (const ch of clean) {
    if (ch >= '0' && ch <= '9') { digits.push(ch); continue; }
    const suit = ch;
    if (!SUITS.includes(suit)) throw new Error(`不明なスート: ${ch}`);
    for (const d of digits) {
      let n = parseInt(d, 10);
      if (suit === 'z') {
        if (n < 1 || n > 7) throw new Error(`字牌は1-7: ${d}z`);
        const idx = HONOR + (n - 1);
        counts[idx]++; tiles.push(idx);
      } else {
        const base = suit === 'm' ? MAN : suit === 'p' ? PIN : SOU;
        if (n === 0) { // 赤5
          const idx = base + 4;
          counts[idx]++; tiles.push(idx); aka[suit]++;
        } else {
          if (n < 1 || n > 9) throw new Error(`数牌は1-9: ${d}${suit}`);
          const idx = base + (n - 1);
          counts[idx]++; tiles.push(idx);
        }
      }
    }
    digits = [];
  }
  if (digits.length) throw new Error('末尾にスート文字が必要です');
  return { counts, aka, tiles };
}

// counts[34] → "123m..." 表記（赤は無視。表示用）
export function formatCounts(counts) {
  let out = '';
  for (const [suit, base] of [['m', MAN], ['p', PIN], ['s', SOU]]) {
    let seg = '';
    for (let r = 0; r < 9; r++) { for (let k = 0; k < counts[base + r]; k++) seg += (r + 1); }
    if (seg) out += seg + suit;
  }
  let zseg = '';
  for (let i = 0; i < 7; i++) { for (let k = 0; k < counts[HONOR + i]; k++) zseg += (i + 1); }
  if (zseg) out += zseg + 'z';
  return out;
}

export function totalTiles(counts) { return counts.reduce((a, b) => a + b, 0); }

// ドラ表示牌 → ドラ本体のインデックス（次の牌。数牌は9→1、風は北→東、三元は中→白で循環）
export function doraFromIndicator(indIdx) {
  if (indIdx < HONOR) {
    const base = Math.floor(indIdx / 9) * 9;
    const r = indIdx % 9;
    return base + ((r + 1) % 9);
  }
  const h = indIdx - HONOR;
  if (h <= 3) return HONOR + ((h + 1) % 4);       // 東南西北 循環
  return HONOR + 4 + ((h - 4 + 1) % 3);           // 白發中 循環
}
