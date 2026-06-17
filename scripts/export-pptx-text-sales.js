#!/usr/bin/env node
/**
 * 営業会議 — テキスト編集可能 PPTX
 * Usage: node scripts/export-pptx-text-sales.js [--output path/to/out.pptx]
 */

const PptxGenJS = require('pptxgenjs');
const path      = require('path');
const fs        = require('fs');

// ── Palette ───────────────────────────────────────────────
const BG     = 'ffffff';
const CARD   = 'f5f7fa';
const BORDER = 'e0e4ea';
const TEXT   = '1a1a2e';
const ACCENT = '2563eb';
const GREEN  = '16a34a';
const RED    = 'dc2626';
const MUTED  = '6b7280';

// ── Dimensions: LAYOUT_WIDE = 13.33 × 7.50 inch ──────────
const W = 13.33;
const H = 7.50;
const PX  = 0.6;
const CW  = W - 2 * PX;
const TOP = 1.25;

// ── Font ─────────────────────────────────────────────────
const F = '游ゴシック';

const pptx = new PptxGenJS();
pptx.layout = 'LAYOUT_WIDE';

// ── Helpers ───────────────────────────────────────────────

function bg(s) { s.background = { fill: BG }; }

function R(s, x, y, w, h, color) {
  s.addShape('rect', { x, y, w, h, fill: { color }, line: { type: 'none' } });
}

function hLine(s, x, y, w, color = ACCENT, h = 0.04) {
  R(s, x, y, w, h, color);
}

function T(s, text, x, y, w, h, opts = {}) {
  s.addText(text, { x, y, w, h, fontFace: F, color: TEXT, bold: true,
    valign: 'top', align: 'left', ...opts });
}

function heading(s, title) {
  T(s, title, PX, 0.3, CW, 0.65, { fontSize: 26, bold: true, color: TEXT });
  hLine(s, PX, 1.05, CW);
}

// ── SLIDE 1: タイトル ─────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);
  R(s, 0, 0, W, 0.07, ACCENT);
  R(s, 0, H - 0.07, W, 0.07, ACCENT);

  R(s, W/2 - 1.3, 2.1, 2.6, 0.44, ACCENT);
  T(s, 'SALES MEETING', W/2 - 1.3, 2.1, 2.6, 0.44,
    { fontSize: 12, bold: true, color: 'ffffff', align: 'center', valign: 'middle' });

  T(s, '営業会議', PX, 2.75, CW, 1.1,
    { fontSize: 62, bold: true, color: TEXT, align: 'center', valign: 'middle' });

  T(s, '2026年6月度　月度実績報告・進捗確認', PX, 4.05, CW, 0.5,
    { fontSize: 20, bold: false, color: MUTED, align: 'center', valign: 'middle' });

  T(s, '2026.06.18', PX, 4.7, CW, 0.4,
    { fontSize: 14, bold: false, color: MUTED, align: 'center', valign: 'middle' });
}

// ── SLIDE 2: 目次 ─────────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);
  heading(s, 'アジェンダ');

  const items = [
    { num: '①', label: '5月分 売上　／　営業活動進捗', accent: true },
    { num: '②', label: '店長・副店長から',               accent: false },
    { num: '③', label: '吉川さん（PJ関連）',             accent: false },
    { num: '④', label: '関さん（防災関連）',             accent: false },
  ];

  const IH = 0.58;
  const GAP = 0.12;
  let iy = TOP + 0.15;

  items.forEach(item => {
    const bg2 = item.accent ? 'dbeafe' : 'f5f7fa';
    const bc  = item.accent ? ACCENT   : BORDER;
    R(s, PX, iy, CW, IH, bg2);
    R(s, PX, iy, 0.045, IH, bc);
    T(s, item.num, PX + 0.12, iy, 0.55, IH,
      { fontSize: 18, bold: true, color: item.accent ? ACCENT : MUTED, align: 'center', valign: 'middle' });
    T(s, item.label, PX + 0.72, iy, CW - 0.82, IH,
      { fontSize: 16, bold: item.accent, color: TEXT, valign: 'middle' });
    iy += IH + GAP;
  });
}

// ── SLIDE 3: ランキング TOP15 ─────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);
  heading(s, '5月度 売上ランキング　（単位：円）');

  const RH  = 0.365;
  const HY  = TOP;

  const xRank = PX;         const wRank = 0.65;
  const xNum  = PX + 0.65;  const wNum  = 0.65;
  const xName = PX + 1.3;   const wName = 7.7;
  const xAmt  = PX + 9.0;   const wAmt  = 2.1;
  const xYoy  = PX + 11.1;  const wYoy  = 1.03;

  R(s, PX, HY, CW, RH, 'e8edf5');
  const ho = { fontSize: 11, bold: true, color: MUTED, valign: 'middle' };
  T(s, '順位',   xRank,        HY, wRank, RH, { ...ho, align: 'center' });
  T(s, '号数',   xNum,         HY, wNum,  RH, { ...ho, align: 'center' });
  T(s, '店舗名', xName + 0.1,  HY, wName, RH, ho);
  T(s, '売上金額', xAmt,       HY, wAmt,  RH, { ...ho, align: 'right'  });
  T(s, '前期比', xYoy,         HY, wYoy,  RH, { ...ho, align: 'right'  });

  const rows = [
    { rank:  1, num: 225, name: '日本橋イベントセンター',       amt: '141,916,484', yoy: '8.4%',    yc: GREEN, mine: false },
    { rank:  2, num: 305, name: '大阪北イベントセンター',       amt: '87,722,501',  yoy: '62.1%',   yc: GREEN, mine: false },
    { rank:  3, num: 150, name: '仙台イベントセンター',         amt: '83,606,860',  yoy: '▲7.0%',  yc: RED,   mine: false },
    { rank:  4, num: 398, name: '大阪中央イベントセンター',     amt: '80,502,402',  yoy: '0.9%',    yc: GREEN, mine: false },
    { rank:  5, num: 145, name: '札幌イベントセンター',         amt: '53,712,021',  yoy: '105.4%',  yc: GREEN, mine: false },
    { rank:  6, num: 330, name: '新宿新都心イベントセンター',   amt: '40,101,320',  yoy: '125.0%',  yc: GREEN, mine: false },
    { rank:  7, num: 172, name: '神戸西イベントセンター',       amt: '36,361,979',  yoy: '5.1%',    yc: GREEN, mine: false },
    { rank:  8, num: 204, name: '広島イベントセンター',         amt: '36,063,194',  yoy: '5.8%',    yc: GREEN, mine: false },
    { rank:  9, num: 107, name: '岡山イベントセンター',         amt: '35,056,186',  yoy: '149.9%',  yc: GREEN, mine: false },
    { rank: 10, num:  24, name: '名古屋イベントセンター',       amt: '33,447,345',  yoy: '126.2%',  yc: GREEN, mine: true  },
    { rank: 11, num: 417, name: '銀座イベントセンター',         amt: '28,293,034',  yoy: '26.1%',   yc: GREEN, mine: false },
    { rank: 12, num:  85, name: '姫路イベントセンター',         amt: '26,936,903',  yoy: '103.9%',  yc: GREEN, mine: false },
    { rank: 13, num: 186, name: '大阪南港イベントセンター',     amt: '26,245,836',  yoy: '88.4%',   yc: GREEN, mine: false },
    { rank: 14, num:  78, name: '所沢イベントセンター',         amt: '24,939,640',  yoy: '▲9.2%',  yc: RED,   mine: false },
    { rank: 15, num: 179, name: '東京足立イベントセンター',     amt: '24,777,113',  yoy: '8.4%',    yc: GREEN, mine: false },
  ];

  rows.forEach((r, i) => {
    const ry = HY + RH + RH * i;
    const rowBg = r.mine ? 'dbeafe' : (i % 2 === 0 ? BG : 'f5f7fa');
    R(s, PX, ry, CW, RH, rowBg);
    if (r.mine) R(s, PX, ry, 0.045, RH, ACCENT);

    T(s, String(r.rank), xRank, ry, wRank, RH,
      { fontSize: 12, bold: r.mine, color: r.mine ? ACCENT : TEXT, align: 'center', valign: 'middle' });
    T(s, String(r.num),  xNum,  ry, wNum,  RH,
      { fontSize: 11, bold: false, color: MUTED, align: 'center', valign: 'middle' });
    T(s, r.name, xName + 0.1, ry, wName, RH,
      { fontSize: 13, bold: r.mine, color: TEXT, valign: 'middle' });
    T(s, r.amt, xAmt, ry, wAmt, RH,
      { fontSize: 13, bold: true, color: r.mine ? ACCENT : TEXT, align: 'right', valign: 'middle' });
    T(s, r.yoy, xYoy, ry, wYoy, RH,
      { fontSize: 13, bold: true, color: r.yc, align: 'right', valign: 'middle' });
  });
}

// ── SLIDE 4: 売上トピック ─────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);
  heading(s, '売上トピック');

  const RH = 0.46;
  const HY = TOP;

  const xType = PX;          const wType = 0.85;
  const xCust = PX + 0.85;   const wCust = 3.2;
  const xMkt  = PX + 4.05;   const wMkt  = 3.2;
  const xProd = PX + 7.25;   const wProd = 2.2;
  const xAmt  = PX + 9.45;   const wAmt  = 2.68;

  R(s, PX, HY, CW, RH, 'e8edf5');
  const ho = { fontSize: 11, bold: true, color: MUTED, valign: 'middle' };
  T(s, '区分',     xType, HY, wType, RH, { ...ho, align: 'center' });
  T(s, '顧客名',   xCust, HY, wCust, RH, ho);
  T(s, '市場機会', xMkt,  HY, wMkt,  RH, ho);
  T(s, '主要商品', xProd, HY, wProd, RH, ho);
  T(s, '売上',     xAmt,  HY, wAmt,  RH, { ...ho, align: 'right' });

  const rows = [
    { type: '新規', cust: 'BMI',                mkt: 'ラオスフェス',   prod: 'テント',     amt: '4,000', isNew: true },
    { type: '新規', cust: 'ヤマチコーポレーション', mkt: '防災展',       prod: 'テント',     amt: '4,000', isNew: true },
    { type: '既存', cust: 'イーキューブ',         mkt: 'アイドル感謝祭', prod: 'EZパネル',   amt: '3,500', isNew: false },
    { type: '既存', cust: '名古屋市名東区',       mkt: '区民祭り',      prod: 'テント',     amt: '3,300', isNew: false },
    { type: '新規', cust: 'イーキューブ',         mkt: 'アイドル',      prod: 'EZパネル',   amt: '1,400', isNew: true },
  ];

  rows.forEach((r, i) => {
    const ry = HY + RH + RH * i;
    const rowBg = i % 2 === 0 ? BG : 'f5f7fa';
    R(s, PX, ry, CW, RH, rowBg);

    const badgeBg = r.isNew ? ACCENT : 'e5e7eb';
    const badgeFg = r.isNew ? 'ffffff' : MUTED;
    const bW = 0.55; const bH = 0.24;
    const bX = xType + (wType - bW) / 2;
    const bY = ry + (RH - bH) / 2;
    R(s, bX, bY, bW, bH, badgeBg);
    T(s, r.type, bX, bY, bW, bH,
      { fontSize: 9, bold: true, color: badgeFg, align: 'center', valign: 'middle' });

    T(s, r.cust, xCust, ry, wCust, RH,
      { fontSize: 13, bold: true, color: TEXT, valign: 'middle' });
    T(s, r.mkt, xMkt, ry, wMkt, RH,
      { fontSize: 12, bold: true, color: MUTED, valign: 'middle' });
    T(s, r.prod, xProd, ry, wProd, RH,
      { fontSize: 12, bold: true, color: MUTED, valign: 'middle' });
    T(s, r.amt, xAmt, ry, wAmt, RH,
      { fontSize: 14, bold: true, color: TEXT, align: 'right', valign: 'middle' });
  });
}

// ── SLIDE 5: 原価引き当てのお願い ─────────────────────────
{
  const s = pptx.addSlide();
  bg(s);
  heading(s, '原価引き当てのお願い');

  // intro box
  R(s, PX, TOP + 0.1, CW, 0.65, 'dbeafe');
  T(s, '案件ごとの原価引き当てに、以下の項目も必ず入力してください。', PX + 0.2, TOP + 0.1, CW - 0.4, 0.65,
    { fontSize: 15, bold: true, color: TEXT, valign: 'middle' });

  // card 1: 車両費
  const cy = TOP + 1.0;
  const cardW = (CW - 0.3) / 2;
  R(s, PX, cy, cardW, 1.6, 'f5f7fa');
  R(s, PX + 0.2, cy + 0.18, 0.45, 0.3, ACCENT);
  T(s, '①', PX + 0.2, cy + 0.18, 0.45, 0.3,
    { fontSize: 11, bold: true, color: 'ffffff', align: 'center', valign: 'middle' });
  T(s, '搬入車両費', PX + 0.8, cy + 0.15, cardW - 1.0, 0.36,
    { fontSize: 18, bold: true, color: TEXT, valign: 'middle' });
  T(s, '商品項目「③入件費・車輌費・諸経費」で\n搬入車両費を登録する', PX + 0.2, cy + 0.65, cardW - 0.4, 0.8,
    { fontSize: 13, bold: true, color: MUTED, valign: 'top', lineSpacingMultiple: 1.5 });

  // card 2: 人件費
  const cx2 = PX + cardW + 0.3;
  R(s, cx2, cy, cardW, 1.6, 'f5f7fa');
  R(s, cx2 + 0.2, cy + 0.18, 0.45, 0.3, ACCENT);
  T(s, '②', cx2 + 0.2, cy + 0.18, 0.45, 0.3,
    { fontSize: 11, bold: true, color: 'ffffff', align: 'center', valign: 'middle' });
  T(s, '人件費', cx2 + 0.8, cy + 0.15, cardW - 1.0, 0.36,
    { fontSize: 18, bold: true, color: TEXT, valign: 'middle' });
  T(s, '商品項目「③入件費・車輌費・諸経費」で\n人件費を登録する', cx2 + 0.2, cy + 0.65, cardW - 0.4, 0.8,
    { fontSize: 13, bold: true, color: MUTED, valign: 'top', lineSpacingMultiple: 1.5 });

  // warning box
  const wy = cy + 1.85;
  R(s, PX, wy, CW, 0.6, 'fef3c7');
  T(s, '売上だけでなく、車両費・人件費の引き当ても毎回必ず行ってください。正確な原価把握につながります。',
    PX + 0.2, wy, CW - 0.4, 0.6,
    { fontSize: 13, bold: true, color: '92400e', valign: 'middle' });
}

// ── Write ─────────────────────────────────────────────────
const args = process.argv.slice(2);
let outputFile = path.resolve(__dirname, '..', 'slides', 'exports', 'sales-meeting.pptx');
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
