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

  T(s, '2026年7月度　月度実績報告・進捗確認', PX, 4.05, CW, 0.5,
    { fontSize: 20, bold: false, color: MUTED, align: 'center', valign: 'middle' });

  T(s, '2026.07.27', PX, 4.7, CW, 0.4,
    { fontSize: 14, bold: false, color: MUTED, align: 'center', valign: 'middle' });
}

// ── SLIDE 2: 目次 ─────────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);
  heading(s, 'アジェンダ');

  const items = [
    { num: '①', label: '6月分 売上　／　営業活動進捗',  accent: true  },
    { num: '②', label: '区民祭り 進捗報告（堀川）',       accent: true  },
    { num: '③', label: '店長・副店長から',                 accent: false },
    { num: '④', label: '吉川さん（PJ関連）',               accent: false },
    { num: '⑤', label: '関さん（防災関連）',               accent: false },
  ];

  const IH = 0.53;
  const GAP = 0.1;
  let iy = TOP + 0.1;

  items.forEach(item => {
    const bg2 = item.accent ? 'dbeafe' : 'f5f7fa';
    const bc  = item.accent ? ACCENT   : BORDER;
    R(s, PX, iy, CW, IH, bg2);
    R(s, PX, iy, 0.045, IH, bc);
    T(s, item.num, PX + 0.12, iy, 0.55, IH,
      { fontSize: 17, bold: true, color: item.accent ? ACCENT : MUTED, align: 'center', valign: 'middle' });
    T(s, item.label, PX + 0.72, iy, CW - 0.82, IH,
      { fontSize: 15, bold: item.accent, color: TEXT, valign: 'middle' });
    iy += IH + GAP;
  });
}

// ── SLIDE 3: ランキング TOP15 ─────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);
  heading(s, '6月度 売上ランキング　（単位：円）');

  const RH  = 0.365;
  const HY  = TOP;

  const xRank = PX;         const wRank = 0.65;
  const xNum  = PX + 0.65;  const wNum  = 0.65;
  const xName = PX + 1.3;   const wName = 7.7;
  const xAmt  = PX + 9.0;   const wAmt  = 2.1;
  const xYoy  = PX + 11.1;  const wYoy  = 1.03;

  R(s, PX, HY, CW, RH, 'e8edf5');
  const ho = { fontSize: 11, bold: true, color: MUTED, valign: 'middle' };
  T(s, '順位',     xRank,       HY, wRank, RH, { ...ho, align: 'center' });
  T(s, '号数',     xNum,        HY, wNum,  RH, { ...ho, align: 'center' });
  T(s, '店舗名',   xName + 0.1, HY, wName, RH, ho);
  T(s, '売上金額', xAmt,        HY, wAmt,  RH, { ...ho, align: 'right'  });
  T(s, '前期比',   xYoy,        HY, wYoy,  RH, { ...ho, align: 'right'  });

  const rows = [
    { rank:  1, num: 225, name: '日本橋イベントセンター',     amt: '151,287,256', yoy: '26.8%',    yc: GREEN, mine: false },
    { rank:  2, num: 305, name: '大阪北イベントセンター',     amt: '88,835,405',  yoy: '▲37.0%',  yc: RED,   mine: false },
    { rank:  3, num: 330, name: '新宿新都心イベントセンター', amt: '67,228,754',  yoy: '77.3%',    yc: GREEN, mine: false },
    { rank:  4, num: 417, name: '銀座イベントセンター',       amt: '60,123,397',  yoy: '90.1%',    yc: GREEN, mine: false },
    { rank:  5, num:  78, name: '所沢イベントセンター',       amt: '44,274,702',  yoy: '▲9.4%',   yc: RED,   mine: false },
    { rank:  6, num: 145, name: '札幌イベントセンター',       amt: '41,433,503',  yoy: '▲25.0%',  yc: RED,   mine: false },
    { rank:  7, num: 186, name: '大阪南港イベントセンター',   amt: '33,183,978',  yoy: '▲22.9%',  yc: RED,   mine: false },
    { rank:  8, num: 179, name: '東京足立イベントセンター',   amt: '31,324,486',  yoy: '▲30.0%',  yc: RED,   mine: false },
    { rank:  9, num: 176, name: '静岡三島イベントセンター',   amt: '28,222,920',  yoy: '22.5%',    yc: GREEN, mine: false },
    { rank: 10, num:  24, name: '名古屋イベントセンター',     amt: '27,695,826',  yoy: '15.9%',    yc: GREEN, mine: true  },
    { rank: 11, num: 150, name: '仙台イベントセンター',       amt: '25,044,900',  yoy: '▲36.0%',  yc: RED,   mine: false },
    { rank: 12, num: 398, name: '大阪中央イベントセンター',   amt: '24,728,890',  yoy: '▲50.9%',  yc: RED,   mine: false },
    { rank: 13, num: 322, name: '横浜町田イベントセンター',   amt: '24,199,441',  yoy: '54.6%',    yc: GREEN, mine: false },
    { rank: 14, num:  45, name: '仙台ステーション',           amt: '20,238,380',  yoy: '2,011.8%', yc: GREEN, mine: false },
    { rank: 15, num:  44, name: '目黒ステーション',           amt: '19,160,198',  yoy: '12.9%',    yc: GREEN, mine: false },
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

// ── SLIDE 4: 売上トピックス ───────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);
  heading(s, '売上トピックス　（単位：千円）');

  const topics = [
    {
      client: 'ハマーステージ',
      event:  'YONFES2026',
      note:   '',
      amt:    '7,000',
      color:  ACCENT,
      bgRow:  'dbeafe',
    },
    {
      client: '中部電力パワーグリッド',
      event:  '寛政変電所',
      note:   '⚠ 台風により当日キャンセル → 7月 再実施予定',
      amt:    '2,170',
      color:  'b45309',
      bgRow:  'fef9c3',
    },
    {
      client: '',
      event:  '福祉・介護の就職総合フェア2026',
      note:   '',
      amt:    '1,600',
      color:  '475569',
      bgRow:  'f5f7fa',
    },
    {
      client: '築地イベントセンター',
      event:  'ロボットテクノロジージャパン',
      note:   '',
      amt:    '3,060',
      color:  '0891b2',
      bgRow:  'ecfeff',
    },
    {
      client: '新宿新都心イベントセンター',
      event:  'MSS（MUFG STARTUP SUMMIT）',
      note:   '',
      amt:    '1,857',
      color:  '7c3aed',
      bgRow:  'f5f3ff',
    },
  ];

  const RH = 0.72;
  const GAP = 0.12;
  const xClient = PX;        const wClient = 3.0;
  const xEvent  = PX + 3.0;  const wEvent  = 5.5;
  const xAmt    = PX + 8.5;  const wAmt    = CW - 8.5;
  let ty = TOP + 0.15;

  topics.forEach(t => {
    R(s, PX, ty, CW, RH, t.bgRow);
    R(s, PX, ty, 0.055, RH, t.color);

    if (t.client) {
      T(s, t.client, xClient + 0.15, ty + 0.1, wClient - 0.2, 0.3,
        { fontSize: 10, bold: true, color: MUTED, valign: 'middle' });
    }
    T(s, t.event, xClient + 0.15, ty + (t.client ? 0.38 : 0.25), wClient - 0.2, 0.38,
      { fontSize: 14, bold: true, color: TEXT, valign: 'middle' });

    if (t.note) {
      T(s, t.note, xEvent + 0.1, ty + 0.35, wEvent - 0.2, 0.38,
        { fontSize: 10, bold: true, color: t.color, valign: 'middle' });
    }

    T(s, t.amt, xAmt, ty, wAmt - 0.1, RH,
      { fontSize: 28, bold: true, color: t.color, align: 'right', valign: 'middle' });

    ty += RH + GAP;
  });
}

// ── Write ─────────────────────────────────────────────────
const args = process.argv.slice(2);
let outputFile = path.resolve(__dirname, '..', 'slides', 'exports', '営業会議_2026年7月度.pptx');
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
