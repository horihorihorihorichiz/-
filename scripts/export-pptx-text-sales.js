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
  ];

  const RH = 0.9;
  const GAP = 0.18;
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

// ── SLIDE 5: 区民祭り 受注管理 ───────────────────────────
{
  const s = pptx.addSlide();
  bg(s);
  heading(s, '区民祭り 受注管理（10区）');

  const RH  = 0.40;
  const HY  = TOP;

  const xKu   = PX;          const wKu   = 1.2;
  const xDate = PX + 1.2;    const wDate = 1.1;
  const xBid  = PX + 2.3;    const wBid  = 1.4;
  const xAmt  = PX + 3.7;    const wAmt  = 4.5;
  const xSts  = PX + 8.2;    const wSts  = 1.0;

  R(s, PX, HY, CW, RH, 'e8edf5');
  const ho = { fontSize: 11, bold: true, color: MUTED, valign: 'middle' };
  T(s, '区',               xKu,   HY, wKu,   RH, ho);
  T(s, '本番日',           xDate, HY, wDate, RH, { ...ho, align: 'center' });
  T(s, '入札・見積期限',   xBid,  HY, wBid,  RH, { ...ho, align: 'center' });
  T(s, '契約金額（税抜）', xAmt,  HY, wAmt,  RH, { ...ho, align: 'right' });
  T(s, '状況',             xSts,  HY, wSts,  RH, { ...ho, align: 'center' });

  const rows = [
    { ku: '名東区', date: '5/10',  bid: '3月',   amt: '3,300,000', status: '確定', done: true },
    { ku: '中村区', date: '10/31', bid: '5月',   amt: '5,500,000', status: '確定', done: true },
    { ku: '瑞穂区', date: '11/7',  bid: '7月',   amt: '4,000,000', status: '未',   done: false },
    { ku: '東区',   date: '11/8',  bid: '7月',   amt: '4,930,000', status: '未',   done: false },
    { ku: '昭和区', date: '11/15', bid: '7月',   amt: '4,300,000', status: '未',   done: false },
    { ku: '千種区', date: '12/5',  bid: '7月',   amt: '3,700,000', status: '未',   done: false },
    { ku: '天白区', date: '12/5',  bid: '7月',   amt: '5,200,000', status: '未',   done: false },
    { ku: '守山区', date: '12/6',  bid: '7月',   amt: '4,000,000', status: '未',   done: false },
    { ku: '南区',   date: '2/21',  bid: '10月',  amt: '2,200,000', status: '未',   done: false },
    { ku: '中川区', date: '2/28',  bid: '8月頃', amt: '未定',      status: '未',   done: false },
  ];

  rows.forEach((r, i) => {
    const ry = HY + RH + RH * i;
    const rowBg = i % 2 === 0 ? BG : 'f5f7fa';
    R(s, PX, ry, CW, RH, rowBg);

    T(s, r.ku,   xKu,   ry, wKu,   RH, { fontSize: 13, bold: true,  color: TEXT, valign: 'middle' });
    T(s, r.date, xDate, ry, wDate, RH, { fontSize: 12, bold: true,  color: TEXT, align: 'center', valign: 'middle' });
    T(s, r.bid,  xBid,  ry, wBid,  RH, { fontSize: 12, bold: true,  color: TEXT, align: 'center', valign: 'middle' });
    T(s, r.amt,  xAmt,  ry, wAmt,  RH, { fontSize: 13, bold: true,  color: r.amt === '未定' ? MUTED : TEXT, align: 'right', valign: 'middle' });

    const stsBg = r.done ? GREEN : 'e5e7eb';
    const stsFg = r.done ? 'ffffff' : MUTED;
    const stsW = 0.65, stsH = 0.24;
    const stsX = xSts + (wSts - stsW) / 2;
    const stsY = ry + (RH - stsH) / 2;
    R(s, stsX, stsY, stsW, stsH, stsBg);
    T(s, r.status, stsX, stsY, stsW, stsH,
      { fontSize: 10, bold: true, color: stsFg, align: 'center', valign: 'middle' });
  });
}

// ── SLIDE 6: 原価引き当てのお願い ─────────────────────────
{
  const s = pptx.addSlide();
  bg(s);
  heading(s, '原価引き当てのお願い');

  R(s, PX, TOP + 0.1, CW, 0.65, 'dbeafe');
  T(s, '案件ごとの原価引き当てに、以下の項目も必ず入力してください。', PX + 0.2, TOP + 0.1, CW - 0.4, 0.65,
    { fontSize: 15, bold: true, color: TEXT, valign: 'middle' });

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

  const cx2 = PX + cardW + 0.3;
  R(s, cx2, cy, cardW, 1.6, 'f5f7fa');
  R(s, cx2 + 0.2, cy + 0.18, 0.45, 0.3, ACCENT);
  T(s, '②', cx2 + 0.2, cy + 0.18, 0.45, 0.3,
    { fontSize: 11, bold: true, color: 'ffffff', align: 'center', valign: 'middle' });
  T(s, '人件費', cx2 + 0.8, cy + 0.15, cardW - 1.0, 0.36,
    { fontSize: 18, bold: true, color: TEXT, valign: 'middle' });
  T(s, '商品項目「③入件費・車輌費・諸経費」で\n人件費を登録する', cx2 + 0.2, cy + 0.65, cardW - 0.4, 0.8,
    { fontSize: 13, bold: true, color: MUTED, valign: 'top', lineSpacingMultiple: 1.5 });

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
