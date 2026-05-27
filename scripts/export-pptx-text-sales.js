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

  T(s, '2026年3月度　実績報告・進捗確認', PX, 4.05, CW, 0.5,
    { fontSize: 20, bold: false, color: MUTED, align: 'center', valign: 'middle' });

  T(s, '2026.04.24', PX, 4.7, CW, 0.4,
    { fontSize: 14, bold: false, color: MUTED, align: 'center', valign: 'middle' });
}

// ── SLIDE 2: 売上サマリー ─────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);
  heading(s, '3月度 売上サマリー');

  const CW3 = (CW - 0.5) / 3;
  const GAP = 0.25;
  const CY = TOP;
  const CH = 4.2;

  const cards = [
    { label: '売上高',        val: '¥48.5M', delta: '▲ 12.3% 前月比',  dc: GREEN, note: '目標 ¥45M（達成率 107.8%）' },
    { label: '新規受注件数',  val: '23件',   delta: '▲ 5件 前月比',    dc: GREEN, note: '目標 20件（達成率 115%）' },
    { label: '受注単価（平均）', val: '¥2.1M', delta: '▼ 3.2% 前月比', dc: RED,   note: '前月 ¥2.17M' },
  ];

  cards.forEach((c, i) => {
    const cx = PX + (CW3 + GAP) * i;
    R(s, cx, CY, CW3, CH, CARD);
    T(s, c.label, cx + 0.2, CY + 0.65, CW3 - 0.4, 0.4,
      { fontSize: 13, bold: false, color: MUTED, align: 'center', valign: 'middle' });
    T(s, c.val, cx + 0.2, CY + 1.3, CW3 - 0.4, 1.0,
      { fontSize: 40, bold: true, color: ACCENT, align: 'center', valign: 'middle' });
    T(s, c.delta, cx + 0.2, CY + 2.5, CW3 - 0.4, 0.4,
      { fontSize: 14, bold: true, color: c.dc, align: 'center', valign: 'middle' });
    T(s, c.note, cx + 0.2, CY + 3.05, CW3 - 0.4, 0.5,
      { fontSize: 11, bold: false, color: MUTED, align: 'center', valign: 'top' });
  });

  const sumY = CY + CH + 0.2;
  R(s, PX, sumY, CW, 0.62, 'eef2f7');
  hLine(s, PX, sumY, CW, ACCENT, 0.015);
  T(s, '売上・件数ともに月間目標を達成。単価は小型案件の増加により微減。',
    PX + 0.3, sumY, CW - 0.6, 0.62,
    { fontSize: 14, bold: false, color: TEXT, align: 'center', valign: 'middle' });
}

// ── SLIDE 3: 売上内訳 ─────────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);
  heading(s, '売上内訳');

  const colW = (CW - 0.4) / 2;
  const lx = PX;
  const rx = PX + colW + 0.4;

  // 左: カテゴリ別
  T(s, 'カテゴリ別', lx, TOP, colW, 0.4, { fontSize: 15, color: TEXT });
  hLine(s, lx, TOP + 0.43, colW, BORDER, 0.012);

  const bars = [
    { label: 'SaaS',   amt: '¥26.7M', ratio: 0.55, color: ACCENT },
    { label: '受託開発', amt: '¥14.6M', ratio: 0.30, color: '8b5cf6' },
    { label: 'コンサル', amt: '¥7.2M',  ratio: 0.15, color: '06b6d4' },
  ];
  const bw = colW - 1.5;
  const bh = 0.48;
  const bsy = TOP + 0.65;

  bars.forEach((b, i) => {
    const by = bsy + (bh + 0.26) * i;
    T(s, b.label, lx, by, 1.35, bh,
      { fontSize: 13, bold: false, color: MUTED, valign: 'middle' });
    R(s, lx + 1.4, by, bw, bh, BORDER);
    R(s, lx + 1.4, by, bw * b.ratio, bh, b.color);
    T(s, b.amt, lx + 1.55, by, bw * b.ratio - 0.15, bh,
      { fontSize: 13, bold: true, color: 'ffffff', valign: 'middle' });
  });

  // 右: チーム別実績
  T(s, 'チーム別実績', rx, TOP, colW, 0.4, { fontSize: 15, color: TEXT });
  hLine(s, rx, TOP + 0.43, colW, BORDER, 0.012);

  const teams = [
    { name: '第1営業部', sub: '田中チーム', amt: '¥22.1M', rate: '達成率 112%', rc: GREEN },
    { name: '第2営業部', sub: '鈴木チーム', amt: '¥16.2M', rate: '達成率 105%', rc: GREEN },
    { name: '第3営業部', sub: '佐藤チーム', amt: '¥10.2M', rate: '達成率 92%',  rc: RED   },
  ];
  const th = 1.3;

  teams.forEach((t, i) => {
    const ty = TOP + 0.65 + (th + 0.2) * i;
    R(s, rx, ty, colW, th, CARD);
    T(s, t.name, rx + 0.3, ty + 0.18, colW - 2.2, 0.45,
      { fontSize: 17, bold: true, color: TEXT, valign: 'middle' });
    T(s, t.sub, rx + 0.3, ty + 0.68, colW - 2.2, 0.35,
      { fontSize: 11, bold: false, color: MUTED, valign: 'middle' });
    T(s, t.amt, rx + 0.3, ty + 0.12, colW - 0.5, 0.58,
      { fontSize: 24, bold: true, color: ACCENT, align: 'right', valign: 'middle' });
    T(s, t.rate, rx + 0.3, ty + 0.75, colW - 0.5, 0.35,
      { fontSize: 12, bold: true, color: t.rc, align: 'right', valign: 'middle' });
  });
}

// ── SLIDE 4: パイプライン ─────────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);
  heading(s, '営業進捗 — パイプライン');

  const lx = PX + 1.7;
  const fw = CW - 1.7;
  const rh = 0.65;
  const sy = TOP + 0.1;

  const stages = [
    { label: 'リード',    cnt: '142件', note: '前月 +18件',    ratio: 1.0,  color: 'dbeafe' },
    { label: '商談中',   cnt: '68件',  note: '見込額 ¥156M', ratio: 0.75, color: 'bfdbfe' },
    { label: '提案済',   cnt: '31件',  note: '見込額 ¥82M',  ratio: 0.50, color: '93c5fd' },
    { label: '最終交渉', cnt: '12件',  note: '¥38M',          ratio: 0.30, color: ACCENT   },
  ];

  stages.forEach((st, i) => {
    const sy2 = sy + (rh + 0.22) * i;
    T(s, st.label, PX, sy2, 1.6, rh,
      { fontSize: 14, bold: false, color: MUTED, align: 'right', valign: 'middle' });
    R(s, lx, sy2, fw, rh, BORDER);
    R(s, lx, sy2, fw * st.ratio, rh, st.color);
    T(s, [
        { text: st.cnt + '  ', options: { bold: true,  fontSize: 15, color: TEXT } },
        { text: st.note,       options: { bold: false, fontSize: 12, color: MUTED } },
      ], lx + 0.2, sy2, fw * st.ratio - 0.2, rh,
      { valign: 'middle' });
  });

  const my = sy + (rh + 0.22) * 4 + 0.3;
  const mw = CW / 3;
  const metrics = [
    { val: '47.9%', label: 'リード→商談 転換率' },
    { val: '33.8%', label: '商談→受注 成約率'   },
    { val: '42日',  label: '平均リードタイム'    },
  ];
  metrics.forEach((m, i) => {
    const mx = PX + mw * i;
    T(s, m.val,   mx, my,        mw, 0.62,
      { fontSize: 32, bold: true, color: ACCENT, align: 'center', valign: 'middle' });
    T(s, m.label, mx, my + 0.62, mw, 0.35,
      { fontSize: 12, bold: false, color: MUTED, align: 'center', valign: 'top' });
  });
}

// ── SLIDE 5: アクションプラン ─────────────────────────────
{
  const s = pptx.addSlide();
  bg(s);
  heading(s, '4月度 アクションプラン');

  const colW = (CW - 0.4) / 2;
  const lx = PX;
  const rx = PX + colW + 0.4;

  // 左: 重点施策
  T(s, '重点施策', lx, TOP, colW, 0.4, { fontSize: 15, color: ACCENT });

  const actions = [
    { main: '最終交渉中の12件を月内クロージング', sub: '担当: 各チームリーダー / 期限: 4/25' },
    { main: '新規リード獲得キャンペーン実施',      sub: '担当: マーケ連携 / 期限: 4/15開始'  },
    { main: '第3営業部の底上げ施策',               sub: '担当: 佐藤 / 週次1on1で進捗管理'   },
  ];
  const ah = 1.35;
  actions.forEach((a, i) => {
    const ay = TOP + 0.55 + (ah + 0.12) * i;
    R(s, lx, ay + 0.33, 0.26, 0.26, ACCENT);
    T(s, '✓', lx, ay + 0.28, 0.26, 0.36,
      { fontSize: 12, bold: true, color: 'ffffff', align: 'center', valign: 'middle' });
    T(s, [
        { text: a.main + '\n', options: { bold: true,  fontSize: 15, color: TEXT,  breakLine: true } },
        { text: a.sub,         options: { bold: false, fontSize: 11, color: MUTED } },
      ], lx + 0.4, ay, colW - 0.4, ah,
      { valign: 'middle', lineSpacingMultiple: 1.4 });
    hLine(s, lx, ay + ah + 0.06, colW, BORDER, 0.012);
  });

  // 右: 4月度目標
  T(s, '4月度 目標', rx, TOP, colW, 0.4, { fontSize: 15, color: ACCENT });

  const goals = [
    { label: '売上目標', val: '¥52M'  },
    { label: '新規受注', val: '25件'  },
    { label: '成約率',   val: '35%↑' },
  ];
  const gh = 0.9;
  goals.forEach((g, i) => {
    const gy = TOP + 0.55 + (gh + 0.18) * i;
    R(s, rx, gy, colW, gh, CARD);
    T(s, g.label, rx + 0.3, gy, colW * 0.55, gh,
      { fontSize: 16, bold: true, color: TEXT, valign: 'middle' });
    T(s, g.val, rx + 0.3, gy, colW - 0.4, gh,
      { fontSize: 26, bold: true, color: ACCENT, align: 'right', valign: 'middle' });
  });

  const q1y = TOP + 0.55 + (gh + 0.18) * 3 + 0.1;
  R(s, rx, q1y, colW, 0.72, 'eef2f7');
  hLine(s, rx, q1y, colW, ACCENT, 0.015);
  T(s, 'Q1累計  ¥138.2M　（通期目標進捗 69.1%）',
    rx + 0.2, q1y, colW - 0.3, 0.72,
    { fontSize: 14, bold: false, color: TEXT, align: 'center', valign: 'middle' });
}

// ── SLIDE 6: ランキング TOP15 ─────────────────────────────
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
