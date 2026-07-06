// tileview.js — 本物風の牌フェイス描画（play/quiz 共通）
import { suitOf, rankOf } from './tiles.js';

const HONOR_CH = ['東', '南', '西', '北', '白', '發', '中'];
const SUIT_CH = { m: '萬', p: 'ピ', s: '索' };
// 見やすさ優先: 数牌は「大きな数字＋スート表記（萬 / ピ / 索）」で描画。
export function faceHTML(idx) {
  const s = suitOf(idx), r = rankOf(idx);
  if (s === 'z') { const h = idx - 27; return `<span class="fz z${h}">${HONOR_CH[h]}</span>`; }
  return `<span class="fn suit-${s}"><b>${r}</b><i>${SUIT_CH[s]}</i></span>`;
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
