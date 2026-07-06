// danger.js — 放銃リスク（危険度）推定
//
// ⚠️ 韓麻の最重要な守備特性: フリテンが無い ＝ 現物でも当たる。
//    リーチ麻雀と違い「捨て牌による絶対安全牌」は存在しない。
//    真に安全なのは「その牌が4枚とも場に見えていて、相手が待ちに使えない」場合のみ
//    （シャンポン/単騎で最後の1枚を掴ませるケースを除く近似）。
//
// v1 は相手の手牌を知らない前提のヒューリスティック:
//   放銃率 ≈ 基準率 × 牌種係数 × 見え枚数係数 × 壁係数
// を「テンパイ濃厚な相手1人あたり」の当たり確率とし、警戒人数ぶん合成する。
// 数値は絶対値ではなく、打牌間の相対的な危険度比較に使うこと。

import { isHonor, rankOf, suitOf, MAN, PIN, SOU } from './tiles.js';

export const DANGER_CONFIG = {
  baseRate: 0.09,        // 中張牌の基準放銃率（相手1人・テンパイ想定）
  honorMult: 0.45,       // 字牌（シャンポン/単騎のみ）
  terminalMult: 0.60,    // 1,9
  nearTerminalMult: 0.90,// 2,3,7,8
  middleMult: 1.15,      // 4,5,6
  deadFactor: 0.35,      // 残り0枚（見え切り）: シャンポン/単騎でしか当たらない
  kabeFactor: 0.65,      // 壁でスジ両面が消える補正
  cap: 0.5,              // 相手1人あたり上限
  avgLoss: 8,            // 放銃時の平均失点（韓麻の平均打点目安・可変）
};

// seen[34] = 場に見えている枚数（自分の手牌＋ドラ表示＋相手の河/副露 など、自分視点で見える全て）
// idx を切ったときの、相手1人あたり放銃率
function perOpponent(idx, seen, cfg) {
  let p = cfg.baseRate;
  if (isHonor(idx)) {
    p *= cfg.honorMult;
  } else {
    const r = rankOf(idx);
    if (r === 1 || r === 9) p *= cfg.terminalMult;
    else if (r === 2 || r === 3 || r === 7 || r === 8) p *= cfg.nearTerminalMult;
    else p *= cfg.middleMult;

    // 壁（カベ）: 数牌で、両面を作る隣接牌がほぼ場に出ていれば両面待ちが減る
    const base = idx - (idx % 9);
    const r0 = idx % 9;
    const seenAt = (rr) => (rr >= 0 && rr <= 8) ? (seen ? seen[base + rr] : 0) : 4;
    const leftWall = seenAt(r0 - 1) >= 3;   // 片側の隣接が枯れ
    const rightWall = seenAt(r0 + 1) >= 3;
    if (leftWall || rightWall) p *= cfg.kabeFactor;
  }

  const live = 4 - (seen ? seen[idx] : 0);
  if (live <= 0) p *= cfg.deadFactor;

  return Math.min(p, cfg.cap);
}

// 警戒人数ぶん合成した放銃率（少なくとも1人が当たる確率）
export function dealInProb(idx, seen, threats, cfg = DANGER_CONFIG) {
  if (!threats || threats <= 0) return 0;
  const p = perOpponent(idx, seen, cfg);
  return 1 - Math.pow(1 - p, threats);
}

// なぜ危険/安全か、の理由を返す。{ t:'risk'|'safe', s:説明 } の配列。
export function dangerReasons(idx, seen, threats) {
  const out = [];
  if (!threats || threats <= 0) return out;
  const seenAt = (i) => (seen ? seen[i] : 0);
  if (isHonor(idx)) {
    out.push({ t: 'safe', s: '字牌：対子・単騎の待ちにしか当たらず比較的安全' });
  } else {
    const r = rankOf(idx);
    const base = idx - (idx % 9), r0 = idx % 9;
    if (r === 1 || r === 9) out.push({ t: 'safe', s: '端牌(1・9)：両面が片側だけで危険度は低め' });
    else if (r === 4 || r === 5 || r === 6) out.push({ t: 'risk', s: '中張(4〜6)：両面・嵌張・辺張どの待ちにも刺さりやすく最も危険' });
    else out.push({ t: 'risk', s: '2・3・7・8：両面待ちに当たりやすい' });
    const leftWall = r0 - 1 >= 0 && seenAt(base + r0 - 1) >= 3;
    const rightWall = r0 + 1 <= 8 && seenAt(base + r0 + 1) >= 3;
    if (leftWall || rightWall) out.push({ t: 'safe', s: '隣の牌が場に3枚以上（壁）→ 両面待ちが減り危険度ダウン' });
  }
  const seen4 = seenAt(idx);
  if (seen4 === 0) out.push({ t: 'risk', s: '生牌（場に1枚も切れていない）→ 相手が待ちに使いやすい' });
  else if (seen4 >= 3) out.push({ t: 'safe', s: `場に${seen4}枚見え → シャンポン・単騎で当たりにくい` });
  return out;
}
