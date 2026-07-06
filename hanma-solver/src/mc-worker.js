// mc-worker.js — モンテカルロEVをバックグラウンドで計算する Web Worker
// UI（app.js）から手牌候補を受け取り、1候補終わるごとに結果を逐次 postMessage する。

import { monteCarloDiscard } from './mc.js';

self.onmessage = (e) => {
  const msg = e.data;
  if (msg.type !== 'run') return;
  const { jobs, common } = msg;
  for (let i = 0; i < jobs.length; i++) {
    const job = jobs[i];
    const result = monteCarloDiscard({
      hand13: job.hand13,
      calledMelds: common.calledMelds,
      omoteIndicators: common.omoteIndicators,
      unseen: common.unseen,
      turnsLeft: common.turnsLeft,
      rollouts: common.rollouts,
      players: common.players,
    });
    self.postMessage({ type: 'progress', index: i, total: jobs.length, discard: job.discard, result });
  }
  self.postMessage({ type: 'done' });
};
