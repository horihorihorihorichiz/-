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

  T(s, '2026年5月度　月度売上ランキング', PX, 4.05, CW, 0.5,
    { fontSize: 20, bold: false, color: MUTED, align: 'center', valign: 'middle' });

  T(s, '2026.05.27', PX, 4.7, CW, 0.4,
    { fontSize: 14, bold: false, color: MUTED, align: 'center', valign: 'middle' });
}

// ── SLIDE 2: 目次 ─────────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);
  heading(s, 'アジェンダ');

  const items = [
    { num: '①', label: '4月分 売上　／　営業活動進捗', accent: true },
    { num: '②', label: '店長・副店長から',               accent: false },
    { num: '③', label: '吉川さん（PJ関連）',             accent: false },
    { num: '④', label: '関さん（防災関連）',             accent: false },
    { num: '⑤', label: '業務アイデアコンテスト',         accent: false },
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
  heading(s, '4月度 売上ランキング　（単位：円）');

  const RH  = 0.365;
  const HY  = TOP;

  // Column layout
  const xRank = PX;         const wRank = 0.65;
  const xNum  = PX + 0.65;  const wNum  = 0.65;
  const xName = PX + 1.3;   const wName = 7.7;
  const xAmt  = PX + 9.0;   const wAmt  = 2.1;
  const xYoy  = PX + 11.1;  const wYoy  = 1.03;

  // Header
  R(s, PX, HY, CW, RH, 'e8edf5');
  const ho = { fontSize: 11, bold: true, color: MUTED, valign: 'middle' };
  T(s, '順位',   xRank,        HY, wRank, RH, { ...ho, align: 'center' });
  T(s, '号数',   xNum,         HY, wNum,  RH, { ...ho, align: 'center' });
  T(s, '店舗名', xName + 0.1,  HY, wName, RH, ho);
  T(s, '売上金額', xAmt,       HY, wAmt,  RH, { ...ho, align: 'right'  });
  T(s, '前期比', xYoy,         HY, wYoy,  RH, { ...ho, align: 'right'  });

  const rows = [
    { rank:  1, num: 225, name: '日本橋イベントセンター',     amt: '158,811,604', yoy: '18.3%',   yc: GREEN, mine: false },
    { rank:  2, num: 305, name: '大阪北イベントセンター',     amt: '54,676,382',  yoy: '▲25.9%', yc: RED,   mine: false },
    { rank:  3, num:  24, name: '名古屋イベントセンター',     amt: '54,377,853',  yoy: '29.5%',   yc: GREEN, mine: true  },
    { rank:  4, num: 398, name: '大阪中央イベントセンター',   amt: '48,768,831',  yoy: '▲45.3%', yc: RED,   mine: false },
    { rank:  5, num: 330, name: '新宿新都心イベントセンター', amt: '42,173,962',  yoy: '89.1%',   yc: GREEN, mine: false },
    { rank:  6, num:  78, name: '所沢イベントセンター',       amt: '36,427,140',  yoy: '30.6%',   yc: GREEN, mine: false },
    { rank:  7, num: 417, name: '銀座イベントセンター',       amt: '35,492,992',  yoy: '79.1%',   yc: GREEN, mine: false },
    { rank:  8, num: 150, name: '仙台イベントセンター',       amt: '34,904,540',  yoy: '13.3%',   yc: GREEN, mine: false },
    { rank:  9, num: 176, name: '静岡三島イベントセンター',   amt: '31,379,720',  yoy: '26.4%',   yc: GREEN, mine: false },
    { rank: 10, num: 107, name: '岡山イベントセンター',       amt: '28,224,605',  yoy: '▲6.4%',  yc: RED,   mine: false },
    { rank: 11, num:  85, name: '姫路イベントセンター',       amt: '27,404,979',  yoy: '▲9.0%',  yc: RED,   mine: false },
    { rank: 12, num: 145, name: '札幌イベントセンター',       amt: '24,245,240',  yoy: '▲20.2%', yc: RED,   mine: false },
    { rank: 13, num: 186, name: '大阪南港イベントセンター',   amt: '18,428,718',  yoy: '▲36.3%', yc: RED,   mine: false },
    { rank: 14, num: 204, name: '広島イベントセンター',       amt: '16,097,450',  yoy: '▲20.7%', yc: RED,   mine: false },
    { rank: 15, num: 380, name: '南風原ステーション',         amt: '16,019,460',  yoy: '370.0%',  yc: GREEN, mine: false },
  ];

  rows.forEach((r, i) => {
    const ry = HY + RH + RH * i;
    const rowBg = r.mine ? 'dbeafe' : (i % 2 === 0 ? BG : 'f5f7fa');
    R(s, PX, ry, CW, RH, rowBg);
    if (r.mine) R(s, PX, ry, 0.045, RH, ACCENT);

    const tc = r.mine ? TEXT : TEXT;

    T(s, String(r.rank), xRank, ry, wRank, RH,
      { fontSize: 12, bold: r.mine, color: r.mine ? ACCENT : tc, align: 'center', valign: 'middle' });
    T(s, String(r.num),  xNum,  ry, wNum,  RH,
      { fontSize: 11, bold: false, color: MUTED, align: 'center', valign: 'middle' });
    T(s, r.name, xName + 0.1, ry, wName, RH,
      { fontSize: 13, bold: r.mine, color: r.mine ? TEXT : tc, valign: 'middle' });
    T(s, r.amt, xAmt, ry, wAmt, RH,
      { fontSize: 13, bold: true, color: r.mine ? ACCENT : TEXT, align: 'right', valign: 'middle' });
    T(s, r.yoy, xYoy, ry, wYoy, RH,
      { fontSize: 13, bold: true, color: r.yc, align: 'right', valign: 'middle' });
  });
}

// ── SLIDE 4: 営業活動進捗（プレースホルダー） ────────────
{
  const s = pptx.addSlide();
  bg(s);
  const bw = 1.6;
  const bx = (W - bw) / 2;
  R(s, bx, 2.6, bw, 0.38, 'dbeafe');
  T(s, '① 売上', bx, 2.6, bw, 0.38,
    { fontSize: 11, bold: true, color: ACCENT, align: 'center', valign: 'middle' });
  T(s, '営業活動進捗', PX, 3.15, CW, 0.9,
    { fontSize: 30, bold: true, color: TEXT, align: 'center', valign: 'middle' });
  T(s, '内容を準備中', PX, 4.15, CW, 0.4,
    { fontSize: 14, bold: true, color: MUTED, align: 'center', valign: 'middle' });
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
