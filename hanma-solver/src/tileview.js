// tileview.js — 牌フェイス描画（play/quiz 共通）
// 牌の絵柄は CC BY 4.0 の素材（FluffyStuff/riichi-mahjong-tiles）を使用。
import { rankOf } from './tiles.js';
import { TILE_SVG } from './tiles-data.js';

export function faceHTML(idx) {
  return `<img class="tface" src="${TILE_SVG[idx]}" alt="" draggable="false">`;
}

export function tileEl(idx, opts = {}) {
  const el = document.createElement('span');
  if (opts.back) { el.className = 'tile back' + (opts.small ? ' t-sm' : ''); return el; }
  const red = idx < 27 && rankOf(idx) === 5;
  el.className = 'tile' + (opts.small ? ' t-sm' : '') + (red ? ' red' : '') +
    (opts.drawn ? ' drawn' : '') + (opts.disabled ? ' disabled' : '') + (opts.pick ? ' pick' : '') +
    (opts.best ? ' best' : '') + (opts.safe ? ' safe' : '') + (opts.dora ? ' is-dora' : '');
  el.innerHTML = faceHTML(idx);
  return el;
}

export function backsInto(container, n, small = true) {
  for (let k = 0; k < n; k++) container.appendChild(tileEl(0, { back: true, small }));
}
