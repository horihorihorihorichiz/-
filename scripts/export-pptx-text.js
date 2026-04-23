#!/usr/bin/env node
/**
 * 建築トレンド 2026 — テキスト編集可能 PPTX エクスポーター
 * 画像貼り付けではなく pptxgenjs でテキスト・図形を直接配置する。
 *
 * Usage: node scripts/export-pptx-text.js [--output path/to/out.pptx]
 */

const PptxGenJS = require('pptxgenjs');
const path      = require('path');
const fs        = require('fs');

// ── Palette ───────────────────────────────────────────────
const PAPER = 'f1ede4';
const INK   = '17140f';
const MUTED = '8b8578';
const BODY  = '2b251e';

// ── Slide dimensions (LAYOUT_WIDE = 13.33 × 7.5 inch) ─────
const W = 13.33;
const H = 7.50;
const ix  = (n) => +(n * W / 1920).toFixed(4);   // px → x-inch
const iy  = (n) => +(n * H / 1080).toFixed(4);   // px → y-inch
const fpt = (n) => +(n * H / 1080 * 72).toFixed(1); // px → pt

// ── Layout constants ──────────────────────────────────────
const PADX  = ix(120);
const PADY  = iy(96);
const BTOP  = iy(120);   // body top
const CW    = +(W - 2 * PADX).toFixed(4); // 11.664"

// ── Fonts ────────────────────────────────────────────────
const SERIF = '游明朝';
const SANS  = '游明朝'; // 全スライド游明朝に統一

// ── pptxgenjs ────────────────────────────────────────────
const pptx = new PptxGenJS();
pptx.layout = 'LAYOUT_WIDE';

// ── Helpers ───────────────────────────────────────────────

function bg(slide) {
  slide.background = { fill: PAPER };
}

// Horizontal rule (thin/thick)
function hRule(slide, x, y, w = CW, thick = false) {
  slide.addShape('rect', {
    x, y, w, h: thick ? 0.040 : 0.015,
    fill: { color: INK },
    line: { type: 'none' },
  });
}

// Unfilled circle ring
function ring(slide, cx, cy, r) {
  slide.addShape('ellipse', {
    x: cx - r, y: cy - r, w: r * 2, h: r * 2,
    fill: { type: 'none' },
    line: { color: INK, width: 1.5 },
  });
}

// ── SLIDE 1: Cover ────────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);

  ring(s, W - ix(0),   iy(-140), ix(260));
  ring(s, W - ix(120), iy(170),  ix(110));

  // Eyebrow
  s.addText('— これからの建築を、5つの視座で。', {
    x: PADX, y: iy(260), w: ix(900), h: iy(48),
    fontFace: SERIF, fontSize: fpt(28), italic: true, color: INK,
    valign: 'top',
  });

  // H1: 建築\nトレンド 2026.
  s.addText([
    { text: '建築', options: {} },
    { text: '\n', options: {} },
    { text: 'トレンド ', options: { fontSize: fpt(196) } },
    { text: '2026.', options: { fontSize: fpt(108), italic: true } },
  ], {
    x: PADX, y: iy(310), w: ix(1400), h: iy(560),
    fontFace: SERIF, fontSize: fpt(196), bold: true, color: INK,
    valign: 'top', lineSpacingMultiple: 0.92,
  });

  // Subblock — rule + text
  const sbY = iy(840);
  hRule(s, PADX, sbY, ix(720));
  s.addText(
    '気候、素材、知能、そして人。\n5つのキーワードで、\n次の建築の輪郭をたどる。',
    {
      x: PADX + ix(24), y: sbY + iy(18), w: ix(700), h: iy(200),
      fontFace: SERIF, fontSize: fpt(24), color: BODY,
      valign: 'top', lineSpacingMultiple: 1.85,
    }
  );
}

// ── SLIDE 2: 目次 ─────────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);

  ring(s, ix(56) + ix(70), H - ix(70), ix(70));

  // Left column
  s.addText('目次', {
    x: PADX, y: BTOP, w: ix(280), h: iy(100),
    fontFace: SERIF, fontSize: fpt(72), bold: true, color: INK, valign: 'top',
  });
  hRule(s, PADX, BTOP + iy(92), ix(280), true);
  s.addText(
    'この号で追いかける5つの主題。\nどれも独立した流れでありながら、\n静かに互いを引き寄せている。',
    {
      x: PADX, y: BTOP + iy(130), w: ix(260), h: iy(360),
      fontFace: SERIF, fontSize: fpt(22), color: BODY,
      valign: 'top', lineSpacingMultiple: 1.9,
    }
  );

  // TOC
  const tocX = PADX + ix(352);
  const tocW = W - PADX - tocX;
  const rowH = iy(112);
  hRule(s, tocX, BTOP, tocW, true);

  const rows = [
    { n: '01', ja: 'カーボンニュートラル建築', pg: 'p. 003' },
    { n: '02', ja: '木造建築の進化',           pg: 'p. 004' },
    { n: '03', ja: 'AI × BIM',                 pg: 'p. 005' },
    { n: '04', ja: 'リノベーション',             pg: 'p. 006' },
    { n: '05', ja: 'ウェルビーイング',           pg: 'p. 006' },
  ];

  rows.forEach((row, i) => {
    const y = BTOP + rowH * i + iy(12);
    s.addText(row.n, {
      x: tocX, y, w: ix(96), h: iy(80),
      fontFace: SERIF, fontSize: fpt(64), italic: true, color: INK, valign: 'middle',
    });
    s.addText(row.ja, {
      x: tocX + ix(130), y: y + iy(18), w: ix(920), h: iy(56),
      fontFace: SERIF, fontSize: fpt(36), bold: true, color: INK, valign: 'top',
    });
    s.addText(row.pg, {
      x: W - PADX - ix(120), y, w: ix(120), h: iy(80),
      fontFace: SERIF, fontSize: fpt(24), italic: true, color: INK,
      valign: 'middle', align: 'right',
    });
    hRule(s, tocX, BTOP + rowH * (i + 1), tocW);
  });
}

// ── SLIDE 3: 01 Carbon ────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);

  // H2
  s.addText('建築は、\n地球にとって最大の炭素産業である。', {
    x: PADX, y: BTOP, w: CW, h: iy(330),
    fontFace: SERIF, fontSize: fpt(84), bold: true, color: INK,
    valign: 'top', lineSpacingMultiple: 1.1,
  });

  // Lede — 句読点で改行
  s.addText(
    '世界のCO₂排出の約37%は建築に由来する。\n' +
    '2050年に向けて、設計の前提そのものが\n' +
    '書き換えられようとしている。',
    {
      x: PADX, y: BTOP + iy(350), w: ix(880), h: iy(150),
      fontFace: SERIF, fontSize: fpt(24), color: BODY,
      valign: 'top', lineSpacingMultiple: 1.8,
    }
  );

  // Infobox
  const ibY = H - PADY - iy(240);
  hRule(s, PADX, ibY, CW, true);
  s.addText('建築部門のCO₂排出構造', {
    x: PADX, y: ibY + iy(14), w: ix(600), h: iy(22),
    fontFace: SANS, fontSize: fpt(13), color: MUTED, charSpacing: 0.5,
  });

  const colW2 = CW / 2 - ix(40);
  const bars = [
    { label: '運用エネルギー', pct: 70, col: 0 },
    { label: '材料製造',       pct: 22, col: 0 },
    { label: '解体・廃棄',     pct: 8,  col: 1 },
  ];
  bars.forEach((bar) => {
    const bx  = PADX + bar.col * (colW2 + ix(80));
    const idx = bar.col === 0 ? bars.indexOf(bar) : 0;
    const by  = ibY + iy(46) + idx * iy(88);
    s.addText(bar.label, {
      x: bx, y: by, w: ix(400), h: iy(30),
      fontFace: SERIF, fontSize: fpt(22), bold: true, color: INK, valign: 'top',
    });
    s.addText(`${bar.pct}%`, {
      x: bx + ix(420), y: by, w: ix(80), h: iy(30),
      fontFace: SERIF, fontSize: fpt(36), italic: true, color: INK,
      valign: 'top', align: 'right',
    });
    // Bar bg
    s.addShape('rect', {
      x: bx, y: by + iy(33), w: colW2 * 0.88, h: 0.06,
      fill: { color: 'e6dfce' }, line: { type: 'none' },
    });
    // Bar fill
    s.addShape('rect', {
      x: bx, y: by + iy(33), w: colW2 * 0.88 * bar.pct / 100, h: 0.06,
      fill: { color: INK }, line: { type: 'none' },
    });
  });
  s.addText('Source · IEA / UNEP, 2024', {
    x: PADX + colW2 + ix(80), y: ibY + iy(150), w: colW2, h: iy(24),
    fontFace: SANS, fontSize: fpt(13), color: MUTED, charSpacing: 0.4,
  });
}

// ── SLIDE 4: 02 Wood ─────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);

  ring(s, ix(650), H - iy(90), ix(90));

  // H2
  s.addText('街が、木で立ち上がる。', {
    x: PADX, y: BTOP, w: CW, h: iy(105),
    fontFace: SERIF, fontSize: fpt(84), bold: true, color: INK, valign: 'top',
  });
  hRule(s, PADX, BTOP + iy(102), CW * 0.60);

  // Timeline (left)
  const tlX = PADX;
  const tlW = ix(1040);
  const tlY = BTOP + iy(130);
  const rowH = iy(118);

  s.addText('木造建築のマイルストーン', {
    x: tlX, y: tlY - iy(26), w: tlW, h: iy(24),
    fontFace: SANS, fontSize: fpt(13), color: MUTED, charSpacing: 0.4,
  });
  hRule(s, tlX, tlY, tlW);

  const tl = [
    { y: '2019', b: 'CLT基準法改正',   t: '直交集成板が一般的な構造材料として\n基準法に位置づけ。',  f: false },
    { y: '2022', b: '木材利用促進法',   t: '公共だけでなく民間建築物にも\n木材利用を拡大。',          f: false },
    { y: '2025', b: '中高層木造の増加', t: '10階以上の木造ビルが国内で\n複数竣工。',                  f: false },
    { y: '2030', b: '木造比率目標',     t: '新築の木造比率\n40% → 55% へ。',                         f: true  },
  ];
  tl.forEach((e, i) => {
    const ry = tlY + rowH * i;
    const c = e.f ? MUTED : INK;
    s.addText(e.y, {
      x: tlX, y: ry + iy(8), w: ix(136), h: iy(50),
      fontFace: SERIF, fontSize: fpt(40), italic: true, color: c, valign: 'top',
    });
    s.addText([
      { text: e.b, options: { bold: true, fontSize: fpt(24), color: c } },
      { text: '\n', options: {} },
      { text: e.t, options: { fontSize: fpt(22), color: e.f ? MUTED : BODY } },
    ], {
      x: tlX + ix(156), y: ry + iy(8), w: ix(860), h: rowH - iy(16),
      fontFace: SERIF, valign: 'top', lineSpacingMultiple: 1.7,
    });
    hRule(s, tlX, ry + rowH, tlW);
  });

  // Hero (right)
  const hx = PADX + ix(1100);
  const hw = W - PADX - hx;
  s.addText('2030年へ向かう、その到達点', {
    x: hx, y: tlY - iy(26), w: hw, h: iy(24),
    fontFace: SANS, fontSize: fpt(13), color: MUTED, charSpacing: 0.4,
  });
  s.addText([
    { text: '18', options: { fontSize: fpt(224), bold: true } },
    { text: '階', options: { fontSize: fpt(64), italic: true } },
  ], {
    x: hx, y: tlY, w: hw, h: iy(270),
    fontFace: SERIF, color: INK, valign: 'top',
  });
  hRule(s, hx, tlY + iy(278), hw);
  s.addText(
    '2025年、国内最高の木造ビル。\nCLTとRC造のハイブリッドで、\n木は「風合い」から「骨格」へ還った。',
    {
      x: hx, y: tlY + iy(294), w: hw, h: iy(200),
      fontFace: SERIF, fontSize: fpt(22), color: BODY,
      valign: 'top', lineSpacingMultiple: 1.8,
    }
  );
}

// ── SLIDE 5: 03 AI × BIM ─────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);

  // H2
  s.addText('設計図を、もう一度考え直す。', {
    x: PADX, y: BTOP, w: CW, h: iy(105),
    fontFace: SERIF, fontSize: fpt(84), bold: true, color: INK, valign: 'top',
  });

  // 3 stats
  const sw  = CW / 3;
  const sy  = BTOP + iy(150);

  const stats = [
    { n: '−40', u: '%', h3: '設計期間',      p: '法規チェック、構造計算、\nドキュメント生成。\n手仕事の大半が自動化される。' },
    { n: '−25', u: '%', h3: '施工コスト',    p: 'BIMデータから自動積算、\n工程最適化。\n見積の透明度が一段上がる。' },
    { n: '+60', u: '%', h3: '維持管理の精度', p: 'IoTセンサー × AI予測により、\n建物は「使われながら学習する」\n対象に。' },
  ];
  stats.forEach((stat, i) => {
    const sx = PADX + sw * i + (i > 0 ? ix(24) : 0);
    const sw2 = sw - (i > 0 ? ix(24) : 0);
    hRule(s, sx, sy, sw2, true);
    s.addText([
      { text: stat.n, options: { fontSize: fpt(148), bold: true, color: INK } },
      { text: stat.u, options: { fontSize: fpt(52),  italic: true, color: MUTED } },
    ], {
      x: sx, y: sy + iy(10), w: sw2, h: iy(195),
      fontFace: SERIF, valign: 'top',
    });
    s.addText(stat.h3, {
      x: sx, y: sy + iy(215), w: sw2, h: iy(48),
      fontFace: SERIF, fontSize: fpt(30), bold: true, color: INK, valign: 'top',
    });
    s.addText(stat.p, {
      x: sx, y: sy + iy(272), w: sw2, h: iy(200),
      fontFace: SERIF, fontSize: fpt(22), color: BODY,
      valign: 'top', lineSpacingMultiple: 1.75,
    });
  });

  // Footer — left border + italic quote
  const fy = H - PADY - iy(64);
  s.addShape('rect', {
    x: PADX, y: fy - iy(4), w: ix(4), h: iy(52),
    fill: { color: INK }, line: { type: 'none' },
  });
  s.addText(
    '— 創造性の輪郭は変わらない。\nただ、そこに至る道のりが短くなる。',
    {
      x: PADX + ix(22), y: fy - iy(8), w: CW, h: iy(72),
      fontFace: SERIF, fontSize: fpt(24), italic: true, color: BODY,
      valign: 'middle', lineSpacingMultiple: 1.6,
    }
  );
}

// ── SLIDE 6: 04 + 05 Spread ───────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);

  ring(s, W + ix(60) - ix(110), iy(-60) + ix(110), ix(110));

  const c1W  = (CW - ix(2)) / 2;
  const c1X  = PADX;
  const divX = PADX + c1W;
  const c2X  = divX + ix(72);
  const c2W  = W - PADX - c2X;

  // Vertical divider
  s.addShape('rect', {
    x: divX, y: BTOP, w: ix(2), h: H - BTOP - PADY,
    fill: { color: INK }, line: { type: 'none' },
  });

  const addCol = (num, h3, body, bignum, label, x, w) => {
    s.addText(num, {
      x, y: BTOP, w, h: iy(88),
      fontFace: SERIF, fontSize: fpt(80), italic: true, color: INK, valign: 'top',
    });
    s.addText(h3, {
      x, y: BTOP + iy(88), w, h: iy(195),
      fontFace: SERIF, fontSize: fpt(80), bold: true, color: INK,
      valign: 'top', lineSpacingMultiple: 1.05,
    });
    s.addText(body, {
      x, y: BTOP + iy(295), w, h: iy(240),
      fontFace: SERIF, fontSize: fpt(22), color: BODY,
      valign: 'top', lineSpacingMultiple: 1.85,
    });
    s.addText(bignum, {
      x, y: BTOP + iy(540), w, h: iy(155),
      fontFace: SERIF, fontSize: fpt(128), bold: true, color: INK,
      valign: 'top',
    });
    s.addText(label, {
      x, y: BTOP + iy(700), w, h: iy(50),
      fontFace: SERIF, fontSize: fpt(22), color: MUTED, valign: 'top',
    });
  };

  addCol(
    '04',
    '既存を\n読み直す。',
    '新築の時代から、\nストック更新の時代へ。\n既存躯体の価値を読み解き、\n手を入れることで街が変わる。',
    '64%',
    '2030年 リノベ市場比率の予測',
    c1X, c1W - ix(36),
  );
  addCol(
    '05',
    '建築は、\nケアになる。',
    'WELL認証、CASBEE-ウェルネス、\n環境IoTによる快適性の数値化。\n空間は「健康を手当てする装置」\nとして設計される。',
    '×3.2',
    '健康志向オフィスの生産性指標',
    c2X, c2W,
  );
}

// ── SLIDE 7: Closing ─────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);

  ring(s, W + ix(120), H + iy(120), ix(210));

  s.addText([
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
  ], {
    x: PADX, y: iy(260), w: W - 2 * PADX, h: iy(580),
    fontFace: SERIF, fontSize: fpt(112), italic: true, color: INK,
    valign: 'top', lineSpacingMultiple: 1.18,
  });

  hRule(s, PADX, H - PADY - iy(76));
  s.addText('— 建築トレンド 2026 / 2026.03.30', {
    x: PADX, y: H - PADY - iy(62), w: CW, h: iy(50),
    fontFace: SERIF, fontSize: fpt(24), italic: true, color: INK,
    valign: 'top', align: 'center',
  });
}

// ── Write ────────────────────────────────────────────────
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
