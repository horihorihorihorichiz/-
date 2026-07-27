#!/usr/bin/env node
const PptxGenJS = require('pptxgenjs');
const path      = require('path');
const fs        = require('fs');

const pptx = new PptxGenJS();
pptx.layout = 'LAYOUT_WIDE';

const W = 13.33, H = 7.50, PX = 0.5;
const CW = W - 2 * PX;
const F = '游ゴシック';

const BG     = 'ffffff';
const ACCENT = '0077b6';
const LIGHT  = 'e8f4f8';
const TEXT    = '1a1a2e';
const MUTED  = '6b7280';
const PRICE  = 'dc2626';

const IMG = path.resolve(__dirname, '..', 'slides', 'assets', 'cooling');

function bg(s) { s.background = { fill: BG }; }
function R(s, x, y, w, h, color) {
  s.addShape('rect', { x, y, w, h, fill: { color }, line: { type: 'none' } });
}
function T(s, text, x, y, w, h, opts = {}) {
  s.addText(text, { x, y, w, h, fontFace: F, color: TEXT, bold: true,
    valign: 'top', align: 'left', ...opts });
}

// ── SLIDE 1: 表紙 ──────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);

  s.addImage({ path: path.join(IMG, 'image1.png'), x: 0, y: 0, w: W, h: H });

  R(s, 0, 0, W, 0.06, ACCENT);
  R(s, 0, H - 0.06, W, 0.06, ACCENT);

  T(s, '冷房設備レンタル商品のご提案', 1.0, 1.8, 11, 1.0,
    { fontSize: 38, bold: true, color: TEXT, align: 'center', valign: 'middle' });

  R(s, W/2 - 2.5, 3.1, 5.0, 0.04, ACCENT);

  T(s, '2026年6月26日', 1.0, 3.4, 11, 0.5,
    { fontSize: 16, bold: false, color: MUTED, align: 'center', valign: 'middle' });

  T(s, '名古屋市防災危機管理局　御中', 1.0, 4.2, 11, 0.6,
    { fontSize: 22, bold: true, color: TEXT, align: 'center', valign: 'middle' });

  R(s, W/2 - 2.0, 5.3, 4.0, 0.04, 'e0e4ea');

  T(s, 'ダスキン　名古屋イベントセンター', 1.0, 5.55, 11, 0.4,
    { fontSize: 14, bold: true, color: MUTED, align: 'center', valign: 'middle' });

  T(s, '堀川', 1.0, 5.95, 11, 0.35,
    { fontSize: 13, bold: true, color: MUTED, align: 'center', valign: 'middle' });

  s.addImage({ path: path.join(IMG, 'image2.jpeg'), x: W - 2.2, y: H - 0.75, w: 1.6, h: 0.55 });
}

// ── Helper: Product card ────────────────────────────────
function productCard(s, x, y, cardW, opts) {
  const { title, image, imgW, imgH, imgX, imgY, specs, price, priceAdd, desc } = opts;
  const cardH = 5.8;

  R(s, x, y, cardW, cardH, 'f8fafc');
  s.addShape('rect', { x, y, w: cardW, h: cardH,
    fill: { type: 'none' },
    line: { color: 'e0e4ea', width: 0.75, type: 'solid' },
    rectRadius: 0.08 });

  R(s, x, y, cardW, 0.5, ACCENT);
  T(s, title, x, y, cardW, 0.5,
    { fontSize: 16, bold: true, color: 'ffffff', align: 'center', valign: 'middle' });

  if (image) {
    s.addImage({ path: path.join(IMG, image),
      x: imgX || (x + (cardW - (imgW || 2.0)) / 2),
      y: imgY || (y + 0.6),
      w: imgW || 2.0,
      h: imgH || 2.0,
      sizing: { type: 'contain', w: imgW || 2.0, h: imgH || 2.0 }
    });
  }

  const specY = y + (imgH ? imgH + 0.7 : 2.7);
  const specX = x + 0.2;
  const specW = cardW - 0.4;

  R(s, specX, specY - 0.05, specW, 0.03, ACCENT);

  specs.forEach((sp, i) => {
    const sy = specY + 0.08 + i * 0.28;
    T(s, sp.label, specX, sy, specW * 0.42, 0.26,
      { fontSize: 9, bold: true, color: MUTED, valign: 'middle' });
    T(s, sp.value, specX + specW * 0.42, sy, specW * 0.58, 0.26,
      { fontSize: 10, bold: true, color: TEXT, valign: 'middle' });
  });

  const priceY = specY + 0.08 + specs.length * 0.28 + 0.1;
  R(s, specX, priceY, specW, 0.45, LIGHT);
  T(s, 'レンタル 1泊2日', specX + 0.1, priceY, specW * 0.45, 0.45,
    { fontSize: 10, bold: true, color: TEXT, valign: 'middle' });
  T(s, price, specX + specW * 0.45, priceY, specW * 0.55 - 0.1, 0.45,
    { fontSize: 18, bold: true, color: PRICE, align: 'right', valign: 'middle' });

  if (priceAdd) {
    const addY = priceY + 0.48;
    T(s, '追加 1日', specX + 0.1, addY, specW * 0.45, 0.3,
      { fontSize: 9, bold: true, color: MUTED, valign: 'middle' });
    T(s, priceAdd, specX + specW * 0.45, addY, specW * 0.55 - 0.1, 0.3,
      { fontSize: 12, bold: true, color: TEXT, align: 'right', valign: 'middle' });
  }

  if (desc) {
    const descY = priceY + (priceAdd ? 0.85 : 0.55);
    T(s, desc, specX, descY, specW, cardH - (descY - y) - 0.15,
      { fontSize: 8.5, bold: true, color: MUTED, valign: 'top', lineSpacingMultiple: 1.4 });
  }
}

// ── SLIDE 2: ミストファン + 気化式冷風機 ─────────────────
{
  const s = pptx.addSlide();
  bg(s);
  R(s, 0, 0, W, 0.06, ACCENT);
  T(s, '暑熱対策商品', PX, 0.2, CW, 0.6,
    { fontSize: 24, bold: true, color: TEXT });
  R(s, PX, 0.85, CW, 0.04, ACCENT);

  const gapX = 0.35;
  const cardW = (CW - gapX) / 2;

  productCard(s, PX, 1.1, cardW, {
    title: 'ミストファン',
    image: 'image4.jpeg',
    imgW: 2.2, imgH: 2.2,
    specs: [
      { label: 'サイズ',     value: 'D650×W530×H1700mm' },
      { label: '重量',       value: '45kg' },
      { label: '消費電力',   value: '350W' },
      { label: '電源',       value: '単相100V' },
      { label: 'タンク容量', value: '36L' },
    ],
    price: '¥18,000（税別）',
    priceAdd: '¥3,600（税別）',
    desc: 'ミストと風で体感温度を約3～5℃低下。車輪付きで移動・設置が容易。タンク給水のほか、ホース直結も可能。',
  });

  productCard(s, PX + cardW + gapX, 1.1, cardW, {
    title: '気化式冷風機 フレリア07',
    image: 'image3.png',
    imgW: 1.5, imgH: 2.2,
    specs: [
      { label: 'サイズ',     value: 'W800×D480×H1380mm' },
      { label: '質量',       value: '38kg（満水時88kg）' },
      { label: '消費電力',   value: '380W' },
      { label: '電源',       value: '単相100V' },
      { label: 'タンク容量', value: '57L' },
    ],
    price: '¥15,400（税別）',
    priceAdd: '¥3,080（税別）',
    desc: '水の気化熱を利用した冷風機。排熱が出ないため屋内外問わず使用可能。広範囲を冷却。',
  });
}

// ── SLIDE 3: 工場扇 + スポットクーラー ───────────────────
{
  const s = pptx.addSlide();
  bg(s);
  R(s, 0, 0, W, 0.06, ACCENT);
  T(s, '暑熱対策商品', PX, 0.2, CW, 0.6,
    { fontSize: 24, bold: true, color: TEXT });
  R(s, PX, 0.85, CW, 0.04, ACCENT);

  const gapX = 0.35;
  const cardW = (CW - gapX) / 2;

  productCard(s, PX, 1.1, cardW, {
    title: '工場扇（45cmファン）',
    image: 'image5.png',
    imgW: 2.0, imgH: 2.2,
    specs: [
      { label: 'サイズ',   value: 'H1245mm' },
      { label: '重量',     value: '10.4kg' },
    ],
    price: '¥3,500（税別）',
    priceAdd: '¥700（税別）',
    desc: '45cmの大型ファンで広い空間に送風。スポットクーラーや冷風機との併用で冷却効果UP。',
  });

  productCard(s, PX + cardW + gapX, 1.1, cardW, {
    title: 'スポットクーラー',
    image: 'image6.png',
    imgW: 2.0, imgH: 2.2,
    specs: [
      { label: 'サイズ',   value: 'W440×D400×H1050mm' },
      { label: '重量',     value: '43kg' },
      { label: '消費電力', value: '1000W' },
      { label: '電源',     value: '単相100V' },
    ],
    price: '¥11,000（税別）',
    priceAdd: '¥2,000（税別）',
    desc: '冷媒ガスによるエアコン同等の冷風。人や物をピンポイントで冷却したい場合に最適。',
  });
}

// ── Write ────────────────────────────────────────────────
const args = process.argv.slice(2);
let outputFile = path.resolve(__dirname, '..', 'slides', 'exports', 'cooling-proposal.pptx');
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--output' && args[i + 1]) outputFile = path.resolve(args[++i]);
}
fs.mkdirSync(path.dirname(outputFile), { recursive: true });

pptx.writeFile({ fileName: outputFile }).then(() => {
  console.log('✅ Exported: ' + outputFile);
}).catch(e => {
  console.error('❌ Failed:', e.message);
  process.exit(1);
});
