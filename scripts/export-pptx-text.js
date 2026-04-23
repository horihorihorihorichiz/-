#!/usr/bin/env node
/**
 * 建築トレンド 2026 — テキスト編集可能 PPTX
 * pptxgenjsでテキスト・図形を直接配置する（画像なし）。
 * フォント: 游明朝 統一
 *
 * Usage: node scripts/export-pptx-text.js [--output path/to/out.pptx]
 */

const PptxGenJS = require('pptxgenjs');
const path      = require('path');
const fs        = require('fs');

// ── Palette ───────────────────────────────────────────────
const PAPER  = 'f1ede4';
const INK    = '17140f';
const MUTED  = '6b6560';
const BODY   = INK;  // 本文もインク色に統一（薄さ解消）

// ── Slide dimensions: LAYOUT_WIDE = 13.33 × 7.5 inch ──────
const W = 13.33;
const H = 7.50;

// ── Layout ─────────────────────────────────────────────────
const PX  = 1.0;    // padding x
const PY  = 0.65;   // padding y
const CW  = W - 2 * PX;  // 11.33"
const TOP = 1.0;    // body top

// ── Font ───────────────────────────────────────────────────
const F = '游明朝';

// ── pptxgenjs ──────────────────────────────────────────────
const pptx = new PptxGenJS();
pptx.layout = 'LAYOUT_WIDE';

// ── Helpers ────────────────────────────────────────────────

function bg(s) { s.background = { fill: PAPER }; }

// Horizontal rule (thin line using rect)
function hLine(s, x, y, w = CW, thick = false) {
  s.addShape('rect', {
    x, y, w, h: thick ? 0.038 : 0.012,
    fill: { color: INK }, line: { type: 'none' },
  });
}

// Unfilled circle
function ring(s, cx, cy, r) {
  s.addShape('ellipse', {
    x: cx - r, y: cy - r, w: r * 2, h: r * 2,
    fill: { type: 'none' },
    line: { color: INK, width: 1.2 },
  });
}

// Shorthand addText
function T(s, text, x, y, w, h, opts = {}) {
  s.addText(text, {
    x, y, w, h,
    fontFace: F,
    valign: 'top',
    align: 'left',
    ...opts,
  });
}

// ── SLIDE 1: Cover ──────────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);

  ring(s, W,         -0.5,  1.8);
  ring(s, W - 1.1,    0.4,  0.75);

  // Eyebrow
  T(s, '— これからの建築を、5つの視座で。',
    PX, 1.5, 7.0, 0.45,
    { fontSize: 14, italic: true, color: INK });

  // Title: 建築 / トレンド 2026.
  T(s, [
    { text: '建築',      options: { fontSize: 72, bold: true } },
    { text: '\n',        options: {} },
    { text: 'トレンド ', options: { fontSize: 72, bold: true } },
    { text: '2026.',     options: { fontSize: 42, italic: true } },
  ], PX, 1.95, 9.0, 3.5, {
    fontSize: 72, bold: true, color: INK,
    lineSpacingMultiple: 0.95,
  });

  // Bottom subblock
  hLine(s, PX, 5.7, 5.0);
  T(s, '気候、素材、知能、そして人。\n5つのキーワードで、\n次の建築の輪郭をたどる。',
    PX + 0.2, 5.75, 5.0, 1.4,
    { fontSize: 16, color: BODY, lineSpacingMultiple: 1.85 });
}

// ── SLIDE 2: 目次 ───────────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);

  ring(s, 0.5, H - 0.5, 0.48);

  // Left column
  T(s, '目次', PX, TOP, 1.8, 0.9, { fontSize: 40, bold: true, color: INK });
  hLine(s, PX, TOP + 0.88, 1.8, true);
  T(s, 'この号で追いかける5つの主題。\nどれも独立した流れでありながら、\n静かに互いを引き寄せている。',
    PX, TOP + 1.05, 1.8, 2.0,
    { fontSize: 13, color: BODY, lineSpacingMultiple: 1.9 });

  // TOC area
  const TX = PX + 2.2;   // TOC start x
  const TW = W - PX - TX; // 10.13"
  const RH = 1.05;        // row height

  hLine(s, TX, TOP, TW, true); // thick top rule

  const rows = [
    { n: '01', ja: 'カーボンニュートラル建築', pg: 'p. 003' },
    { n: '02', ja: '木造建築の進化',           pg: 'p. 004' },
    { n: '03', ja: 'AI × BIM',                 pg: 'p. 005' },
    { n: '04', ja: 'リノベーション',            pg: 'p. 006' },
    { n: '05', ja: 'ウェルビーイング',          pg: 'p. 006' },
  ];
  rows.forEach((r, i) => {
    const ry = TOP + RH * i;
    // Number
    T(s, r.n,  TX, ry + 0.12, 1.1, 0.85,
      { fontSize: 26, italic: true, color: INK, valign: 'middle' });
    // Title
    T(s, r.ja, TX + 1.2, ry + 0.22, 7.5, 0.65,
      { fontSize: 20, bold: true, color: INK });
    // Page (right-aligned)
    T(s, r.pg, W - PX - 1.2, ry + 0.28, 1.2, 0.5,
      { fontSize: 14, italic: true, color: INK, align: 'right' });
    // Bottom rule
    hLine(s, TX, ry + RH, TW);
  });
}

// ── SLIDE 3: 01 Carbon ─────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);

  // Section heading
  T(s, '建築は、\n地球にとって最大の炭素産業である。',
    PX, TOP, CW, 2.4,
    { fontSize: 42, bold: true, color: INK, lineSpacingMultiple: 1.1 });

  // Lede
  T(s, '世界のCO₂排出の約37%は建築に由来する。\n2050年に向けて、設計の前提そのものが\n書き換えられようとしている。',
    PX, TOP + 2.55, 7.5, 1.2,
    { fontSize: 16, color: BODY, lineSpacingMultiple: 1.8 });

  // Infobox
  const IBY = 5.5;
  hLine(s, PX, IBY, CW, true);
  T(s, '建築部門のCO₂排出構造',
    PX, IBY + 0.1, 5.0, 0.3,
    { fontSize: 11, color: MUTED, charSpacing: 0.4 });

  const colW = CW / 2 - 0.5;
  const bars = [
    { label: '運用エネルギー', pct: 70, col: 0, row: 0 },
    { label: '材料製造',       pct: 22, col: 0, row: 1 },
    { label: '解体・廃棄',     pct: 8,  col: 1, row: 0 },
  ];
  bars.forEach((b) => {
    const bx = PX + b.col * (colW + 1.0);
    const by = IBY + 0.5 + b.row * 0.72;
    T(s, b.label, bx, by, 3.5, 0.32, { fontSize: 14, bold: true, color: INK });
    T(s, `${b.pct}%`, bx + 3.6, by, 0.8, 0.32,
      { fontSize: 24, italic: true, color: INK, align: 'right' });
    s.addShape('rect', { x: bx, y: by + 0.35, w: colW * 0.9, h: 0.055,
      fill: { color: 'e6dfce' }, line: { type: 'none' } });
    s.addShape('rect', { x: bx, y: by + 0.35, w: colW * 0.9 * b.pct / 100, h: 0.055,
      fill: { color: INK }, line: { type: 'none' } });
  });
  T(s, 'Source · IEA / UNEP, 2024',
    PX + colW + 1.0, IBY + 1.2, colW, 0.25,
    { fontSize: 11, color: MUTED, charSpacing: 0.3 });
}

// ── SLIDE 4: 02 Wood ───────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);

  ring(s, 4.5, H - 0.6, 0.6);

  // Heading
  T(s, '街が、木で立ち上がる。',
    PX, TOP, CW, 0.9, { fontSize: 42, bold: true, color: INK });
  hLine(s, PX, TOP + 0.88, CW * 0.55);

  // Timeline (left col: 5.8" wide)
  const TLX = PX;
  const TLW = 5.8;
  const TLY = TOP + 1.1;
  const TRH = 1.15;

  T(s, '木造建築のマイルストーン',
    TLX, TLY - 0.28, TLW, 0.25, { fontSize: 11, color: MUTED, charSpacing: 0.4 });
  hLine(s, TLX, TLY, TLW);

  const tl = [
    { y: '2019', b: 'CLT基準法改正',   t: '直交集成板が一般的な構造材料として基準法に位置づけ。', f: false },
    { y: '2022', b: '木材利用促進法',   t: '公共だけでなく民間建築物にも木材利用を拡大。',        f: false },
    { y: '2025', b: '中高層木造の増加', t: '10階以上の木造ビルが国内で複数竣工。',                f: false },
    { y: '2030', b: '木造比率目標',     t: '新築の木造比率 40% → 55% へ。',                      f: true  },
  ];
  tl.forEach((e, i) => {
    const ry = TLY + TRH * i;
    const c = e.f ? MUTED : INK;
    // Year
    T(s, e.y, TLX, ry + 0.10, 1.0, 0.5,
      { fontSize: 22, italic: true, color: c });
    // Bold title (separate box)
    T(s, e.b, TLX + 1.1, ry + 0.10, TLW - 1.2, 0.35,
      { fontSize: 15, bold: true, color: c });
    // Body text (separate box, below title)
    T(s, e.t, TLX + 1.1, ry + 0.48, TLW - 1.2, 0.58,
      { fontSize: 13, color: e.f ? MUTED : INK, lineSpacingMultiple: 1.5 });
    hLine(s, TLX, ry + TRH, TLW);
  });

  // Hero right col
  const HX = TLX + TLW + 0.6;
  const HW = W - PX - HX;
  T(s, '2030年へ向かう、その到達点',
    HX, TLY - 0.28, HW, 0.25, { fontSize: 11, color: MUTED, charSpacing: 0.4 });
  T(s, [
    { text: '18',  options: { fontSize: 96, bold: true } },
    { text: '階',  options: { fontSize: 36, italic: true } },
  ], HX, TLY, HW, 1.9, { fontSize: 96, color: INK });
  hLine(s, HX, TLY + 1.95, HW);
  T(s, '2025年、国内最高の木造ビル。\nCLTとRC造のハイブリッドで、\n木は「風合い」から「骨格」へ還った。',
    HX, TLY + 2.1, HW, 1.5,
    { fontSize: 14, color: BODY, lineSpacingMultiple: 1.8 });
}

// ── SLIDE 5: 03 AI × BIM ───────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);

  T(s, '設計図を、もう一度考え直す。',
    PX, TOP, CW, 0.9, { fontSize: 42, bold: true, color: INK });

  const SW  = CW / 3;
  const SY  = TOP + 1.1;
  const stats = [
    { n: '−40', u: '%', h3: '設計期間',      p: '法規チェック、構造計算、ドキュメント生成。手仕事の大半が自動化される。' },
    { n: '−25', u: '%', h3: '施工コスト',     p: 'BIMデータから自動積算、工程最適化。見積の透明度が一段上がる。' },
    { n: '+60', u: '%', h3: '維持管理の精度', p: 'IoTセンサー × AI予測により、建物は「使われながら学習する」対象に。' },
  ];
  stats.forEach((st, i) => {
    const sx = PX + SW * i;
    const sw = SW - 0.15;
    hLine(s, sx, SY, sw, true);
    // Big number (separate box)
    T(s, [
      { text: st.n, options: { fontSize: 64, bold: true, color: INK } },
      { text: st.u, options: { fontSize: 24, italic: true, color: MUTED } },
    ], sx, SY + 0.06, sw, 1.3, { fontSize: 64 });
    // Label (separate box)
    T(s, st.h3, sx, SY + 1.45, sw, 0.4,
      { fontSize: 17, bold: true, color: INK });
    // Body (separate box, natural wrap)
    T(s, st.p, sx, SY + 1.9, sw, 1.6,
      { fontSize: 14, color: INK, lineSpacingMultiple: 1.7 });
  });

  // Footer
  s.addShape('rect', { x: PX, y: H - PY - 0.55, w: 0.03, h: 0.5,
    fill: { color: INK }, line: { type: 'none' } });
  T(s, '— 創造性の輪郭は変わらない。\nただ、そこに至る道のりが短くなる。',
    PX + 0.18, H - PY - 0.6, CW, 0.65,
    { fontSize: 15, italic: true, color: BODY, lineSpacingMultiple: 1.6 });
}

// ── SLIDE 6: 04 + 05 Spread ────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);

  ring(s, W + 0.5, -0.5, 1.4);

  const C1W = (CW - 0.02) / 2;
  const C1X = PX;
  const DVX = PX + C1W;
  const C2X = DVX + 0.5;
  const C2W = W - PX - C2X;

  s.addShape('rect', { x: DVX, y: TOP, w: 0.015, h: H - TOP - PY,
    fill: { color: INK }, line: { type: 'none' } });

  const col = (num, h3, body, bignum, label, x, w) => {
    T(s, num, x, TOP, w, 0.8, { fontSize: 40, italic: true, color: INK });
    T(s, h3, x, TOP + 0.8, w, 1.8,
      { fontSize: 44, bold: true, color: INK, lineSpacingMultiple: 1.05 });
    T(s, body, x, TOP + 2.65, w, 1.9,
      { fontSize: 14, color: BODY, lineSpacingMultiple: 1.85 });
    T(s, bignum, x, TOP + 4.55, w, 1.1,
      { fontSize: 60, bold: true, color: INK });
    T(s, label, x, TOP + 5.65, w, 0.45,
      { fontSize: 13, color: MUTED });
  };

  col('04',
    '既存を\n読み直す。',
    '新築の時代から、\nストック更新の時代へ。\n既存躯体の価値を読み解き、\n手を入れることで街が変わる。',
    '64%', '2030年 リノベ市場比率の予測',
    C1X, C1W - 0.25);

  col('05',
    '建築は、\nケアになる。',
    'WELL認証、CASBEE-ウェルネス、\n環境IoTによる快適性の数値化。\n空間は「健康を手当てする装置」\nとして設計される。',
    '×3.2', '健康志向オフィスの生産性指標',
    C2X, C2W);
}

// ── SLIDE 7: Closing ───────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);

  ring(s, W + 1.2, H + 1.2, 2.2);

  T(s, [
    { text: '建築の未来は、', options: {} },
    { text: '\n', options: {} },
    { text: '環境', options: { bold: true, italic: false } },
    { text: 'と', options: {} },
    { text: '技術', options: { bold: true, italic: false } },
    { text: 'と', options: {} },
    { text: '人', options: { bold: true, italic: false } },
    { text: 'の', options: {} },
    { text: '\n', options: {} },
    { text: '交差点にある。', options: {} },
  ], PX, 1.6, CW, 4.5, {
    fontSize: 58, italic: true, color: INK, lineSpacingMultiple: 1.2,
  });

  hLine(s, PX, H - PY - 0.75);
  T(s, '— 建築トレンド 2026 / 2026.03.30',
    PX, H - PY - 0.62, CW, 0.5,
    { fontSize: 15, italic: true, color: INK, align: 'center' });
}

// ── Write ───────────────────────────────────────────────────
const args = process.argv.slice(2);
let out = path.resolve(__dirname, '..', 'slides', 'exports', 'architecture2026_text.pptx');
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--output' && args[i + 1]) out = path.resolve(args[++i]);
}
fs.mkdirSync(path.dirname(out), { recursive: true });

pptx.writeFile({ fileName: out }).then(() => {
  console.log(`✅ Exported: ${out}`);
}).catch(err => {
  console.error('❌ Export failed:', err.message);
  process.exit(1);
});
