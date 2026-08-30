// 堀川システム オッズ書き出し（Chrome の netkeiba タブで実行）
// 開催中に開いておくと、30秒ごとに全対象レースの単勝オッズを取り、
// odds_live_YYYYMMDD.json と同じ形の JSON を画面に出す。
// notify.py はそのファイルを --odds-file で読む（Chromeとオッズ取得を分離するため）。
// ※ ダウンロード先は Chrome の設定に従う。data/ フォルダに保存すること。
(function () {
  const IDS = window.__HORI_IDS__ || [];
  if (!IDS.length) { alert("レースIDが未設定。register が書き出した ids を貼ること"); return; }
  const DATE = IDS[0].slice(0, 4) + IDS[0].slice(8, 10);  // 便宜上
  async function once() {
    const out = {};
    for (const id of IDS) {
      try {
        const r = await fetch(`https://race.netkeiba.com/api/api_get_jra_odds.html?type=1&locale=ja&race_id=${id}`, { credentials: "include" });
        const j = await r.json();
        const o = j && j.data && j.data.odds && j.data.odds["1"];
        if (o) out[id] = Object.fromEntries(Object.entries(o).map(([k, v]) => [String(parseInt(k, 10)), { odds: v[0], pop: v[2] }]));
      } catch (e) {}
      await new Promise(r => setTimeout(r, 300));
    }
    const blob = new Blob([JSON.stringify(out)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "odds_live.json";
    a.click();
    console.log("odds_live.json を書き出した", Object.keys(out).length, "レース", new Date().toLocaleTimeString());
  }
  once();
  setInterval(once, 30000);
})();
