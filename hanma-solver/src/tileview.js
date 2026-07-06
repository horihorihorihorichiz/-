// tileview.js — 本物風の牌フェイス描画（play/quiz 共通）
import { suitOf, rankOf } from './tiles.js';

const KAN_NUM = ['一', '二', '三', '四', '五', '六', '七', '八', '九'];
const HONOR_CH = ['東', '南', '西', '北', '白', '發', '中'];
// 筒子/索子のドット配置（viewBox 0 0 60 84）
const PIP = {
  1: [[30, 42]],
  2: [[30, 26], [30, 58]],
  3: [[18, 22], [30, 42], [42, 62]],
  4: [[20, 24], [40, 24], [20, 60], [40, 60]],
  5: [[20, 24], [40, 24], [30, 42], [20, 60], [40, 60]],
  6: [[20, 22], [40, 22], [20, 42], [40, 42], [20, 62], [40, 62]],
  7: [[30, 18], [20, 34], [40, 34], [20, 52], [40, 52], [20, 66], [40, 66]],
  8: [[20, 18], [40, 18], [20, 37], [40, 37], [20, 55], [40, 55], [20, 71], [40, 71]],
  9: [[17, 22], [30, 22], [43, 22], [17, 42], [30, 42], [43, 42], [17, 62], [30, 62], [43, 62]],
};

export function faceHTML(idx) {
  const s = suitOf(idx), r = rankOf(idx);
  if (s === 'm') return `<span class="fm"><b>${KAN_NUM[r - 1]}</b><i>萬</i></span>`;
  if (s === 'z') { const h = idx - 27; return `<span class="fz z${h}">${HONOR_CH[h]}</span>`; }
  const red = r === 5;
  const marks = PIP[r].map(([x, y], i) => {
    if (s === 'p') {
      const isC = red && i === 2;
      return `<circle cx="${x}" cy="${y}" r="8.8" class="pdot${isC ? ' rd' : ''}"/><circle cx="${x}" cy="${y}" r="3.4" class="pdotc"/>`;
    }
    // 索子: 竹を1本ずつ間隔を空けて描く（節つき）
    const rd = red && i === Math.floor(PIP[r].length / 2);
    return `<g class="stalk${rd ? ' rd' : ''}">` +
      `<rect x="${x - 4}" y="${y - 7.5}" width="8" height="15" rx="4"/>` +
      `<rect x="${x - 4}" y="${y - 1.2}" width="8" height="2.4" class="node"/></g>`;
  }).join('');
  // 隅に小さく数字（索子・筒子は数えやすく）
  const num = `<text x="7" y="15" class="rnum">${r}</text>`;
  return `<svg viewBox="0 0 60 84" class="pips suit-${s}">${num}${marks}</svg>`;
}

export function tileEl(idx, opts = {}) {
  const el = document.createElement('span');
  if (opts.back) { el.className = 'tile back' + (opts.small ? ' t-sm' : ''); return el; }
  const red = idx < 27 && rankOf(idx) === 5;
  el.className = 'tile' + (opts.small ? ' t-sm' : '') + (red ? ' red' : '') +
    (opts.drawn ? ' drawn' : '') + (opts.disabled ? ' disabled' : '') + (opts.pick ? ' pick' : '') + (opts.best ? ' best' : '');
  el.innerHTML = faceHTML(idx);
  return el;
}

export function backsInto(container, n, small = true) {
  for (let k = 0; k < n; k++) container.appendChild(tileEl(0, { back: true, small }));
}
