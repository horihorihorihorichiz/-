#!/usr/bin/env node
/**
 * netkeiba レースデータスクレイパー
 *
 * Chromeのログイン済みプロファイルを使い、有料のタイム指数データを含む
 * 全レース情報を取得してJSONで出力する。
 *
 * Usage:
 *   node scripts/scrape-race.js <race_id_or_url> [--chrome-profile <path>]
 *
 * Examples:
 *   node scripts/scrape-race.js 202506010811
 *   node scripts/scrape-race.js https://race.netkeiba.com/race/shutuba.html?race_id=202506010811
 *   node scripts/scrape-race.js 202506010811 --chrome-profile "/home/user/.config/google-chrome"
 *
 * Output: keiba/data/<race_id>.json
 */

const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');
const os = require('os');

// ─── Chrome プロファイルパス検出 ───
function detectChromeProfile(override) {
  if (override) return override;

  const platform = os.platform();
  const home = os.homedir();

  const candidates = [];
  if (platform === 'linux') {
    candidates.push(
      path.join(home, '.config', 'google-chrome'),
      path.join(home, '.config', 'chromium'),
      path.join(home, 'snap', 'chromium', 'common', 'chromium'),
    );
  } else if (platform === 'darwin') {
    candidates.push(
      path.join(home, 'Library', 'Application Support', 'Google', 'Chrome'),
      path.join(home, 'Library', 'Application Support', 'Chromium'),
    );
  } else if (platform === 'win32') {
    const appData = process.env.LOCALAPPDATA || path.join(home, 'AppData', 'Local');
    candidates.push(
      path.join(appData, 'Google', 'Chrome', 'User Data'),
      path.join(appData, 'Chromium', 'User Data'),
    );
  }

  for (const c of candidates) {
    if (fs.existsSync(c)) {
      console.error(`[INFO] Chrome profile found: ${c}`);
      return c;
    }
  }
  return null;
}

// ─── race_id 抽出 ───
function extractRaceId(input) {
  // URLからrace_idを抽出
  const m = input.match(/race_id=(\d+)/);
  if (m) return m[1];
  // 純粋な数字ならそのまま
  if (/^\d{12}$/.test(input)) return input;
  throw new Error(`Invalid race_id or URL: ${input}`);
}

// ─── メインスクレイパー ───
async function scrapeRace(raceId, chromeProfilePath) {
  const userDataDir = chromeProfilePath || detectChromeProfile();

  const launchOptions = {
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
    ],
  };

  if (userDataDir) {
    launchOptions.args.push(`--user-data-dir=${userDataDir}`);
    // Default プロファイルを使用
    launchOptions.args.push('--profile-directory=Default');
  } else {
    console.error('[WARN] Chrome profile not found. Proceeding without login (free data only).');
  }

  const browser = await puppeteer.launch(launchOptions);
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  // User-Agent をリアルなものに
  await page.setUserAgent(
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  );

  const result = {
    race_id: raceId,
    race_info: {},
    time_index_ranking: [],
    horses: [],
  };

  try {
    // ─── Step 1: 出馬表ページ (基本情報 + 馬リスト) ───
    console.error(`[1/4] Fetching shutuba page...`);
    const shutubaUrl = `https://race.netkeiba.com/race/shutuba.html?race_id=${raceId}`;
    await page.goto(shutubaUrl, { waitUntil: 'networkidle2', timeout: 30000 });
    await sleep(2000);

    result.race_info = await page.evaluate(() => {
      const info = {};

      // レース名
      const raceNameEl = document.querySelector('.RaceName');
      info.race_name = raceNameEl ? raceNameEl.textContent.trim() : '';

      // レース詳細 (距離・芝/ダート・馬場状態等)
      const raceData01 = document.querySelector('.RaceData01');
      if (raceData01) {
        const text = raceData01.textContent.trim();
        info.race_detail_1 = text;

        // 距離
        const distM = text.match(/(\d{3,4})m/);
        info.distance = distM ? parseInt(distM[1]) : 0;

        // 芝/ダート
        info.surface = text.includes('ダ') ? 'ダート' : '芝';

        // 右/左
        info.direction = text.includes('左') ? '左' : '右';

        // 内/外
        if (text.includes('外')) info.course_type = '外回り';
        else if (text.includes('内')) info.course_type = '内回り';
        else info.course_type = '';

        // 馬場状態
        for (const cond of ['不良', '重', '稍重', '良']) {
          if (text.includes(cond)) { info.track_condition = cond; break; }
        }
      }

      const raceData02 = document.querySelector('.RaceData02');
      if (raceData02) {
        const text = raceData02.textContent.trim();
        info.race_detail_2 = text;

        // 開催場
        const spans = raceData02.querySelectorAll('span');
        if (spans.length > 1) {
          info.venue = spans[1] ? spans[1].textContent.trim() : '';
        }

        // クラス
        for (const cls of ['G1', 'G2', 'G3', 'オープン', '3勝', '2勝', '1勝', '未勝利', '新馬']) {
          if (text.includes(cls)) { info.class_name = cls; break; }
        }

        // 別定/定量/ハンデ
        for (const wt of ['ハンデ', '別定', '定量', '馬齢']) {
          if (text.includes(wt)) { info.weight_rule = wt; break; }
        }
      }

      // 日付
      const dateEl = document.querySelector('#RaceList_DateList .Active a, .Race_Date');
      if (dateEl) {
        info.race_date = dateEl.textContent.trim();
      }

      return info;
    });

    // ─── 馬データ (出馬表から基本情報) ───
    const basicHorses = await page.evaluate(() => {
      const rows = document.querySelectorAll('.HorseTable tr.HorseList');
      return Array.from(rows).map(row => {
        const horse = {};

        // 枠番
        const wakuEl = row.querySelector('td.Waku span');
        horse.gate = wakuEl ? parseInt(wakuEl.textContent.trim()) || 0 : 0;

        // 馬番
        const umabanEl = row.querySelector('td.Umaban');
        horse.post = umabanEl ? parseInt(umabanEl.textContent.trim()) || 0 : 0;

        // 馬名 + horse_id
        const horseNameEl = row.querySelector('.HorseName a');
        horse.name = horseNameEl ? horseNameEl.textContent.trim() : '';
        if (horseNameEl) {
          const href = horseNameEl.getAttribute('href') || '';
          const idM = href.match(/horse\/(\d+)/);
          horse.horse_id = idM ? idM[1] : '';
        }

        // 性齢
        const ageEl = row.querySelector('.Age');
        horse.sex_age = ageEl ? ageEl.textContent.trim() : '';

        // 斤量
        const weightEl = row.querySelector('.Txt_C');
        horse.impost = weightEl ? parseFloat(weightEl.textContent.trim()) || 0 : 0;

        // 騎手
        const jockeyEl = row.querySelector('.Jockey a');
        horse.jockey = jockeyEl ? jockeyEl.textContent.trim() : '';

        // 調教師
        const trainerEl = row.querySelector('.Trainer a');
        horse.trainer = trainerEl ? trainerEl.textContent.trim() : '';

        // 馬体重 (当日/前走比)
        const bodyWtEl = row.querySelector('.Weight');
        if (bodyWtEl) {
          const text = bodyWtEl.textContent.trim();
          horse.body_weight_text = text;
          const wtM = text.match(/(\d+)\(([+-]?\d+)\)/);
          if (wtM) {
            horse.body_weight = parseInt(wtM[1]);
            horse.weight_change = parseInt(wtM[2]);
          }
        }

        return horse;
      });
    });

    result.horses = basicHorses;
    console.error(`[1/4] Found ${basicHorses.length} horses`);

    // ─── Step 2: タイム指数ランキングタブ ───
    console.error(`[2/4] Fetching time index ranking tab...`);
    try {
      // タイム指数タブをクリック
      const tabClicked = await page.evaluate(() => {
        const tabs = document.querySelectorAll('.RaceColumn01 li a, .TabItem a, .SubMenu a');
        for (const tab of tabs) {
          if (tab.textContent.includes('タイム指数')) {
            tab.click();
            return true;
          }
        }
        // 別のセレクタも試す
        const allLinks = document.querySelectorAll('a');
        for (const a of allLinks) {
          if (a.textContent.includes('タイム指数') || a.textContent.includes('指数')) {
            a.click();
            return true;
          }
        }
        return false;
      });

      if (tabClicked) {
        await sleep(3000); // タブ切り替え待ち

        result.time_index_ranking = await page.evaluate(() => {
          const rows = document.querySelectorAll('.TimeIndex_Table tr, .RankTable tr, table.nk_tb_common tr');
          const data = [];
          for (const row of rows) {
            const cells = row.querySelectorAll('td');
            if (cells.length < 7) continue;

            const entry = {};
            const texts = Array.from(cells).map(c => c.textContent.trim());

            // 馬名を探す
            const nameEl = row.querySelector('a[href*="horse"]');
            entry.name = nameEl ? nameEl.textContent.trim() : texts[0];

            // 列の並び: 最高 / 5走平均 / 距離 / コース / 3走前 / 2走前 / 前走 / オッズ(or 人気)
            // 実際の列順はページ構造による
            entry.raw_cells = texts;
            data.push(entry);
          }
          return data;
        });

        console.error(`[2/4] Time index data: ${result.time_index_ranking.length} entries`);
      } else {
        console.error(`[2/4] Time index tab not found (may need premium login)`);
      }
    } catch (e) {
      console.error(`[2/4] Failed to get time index: ${e.message}`);
    }

    // ─── Step 3: 各馬の過去走データ ───
    console.error(`[3/4] Fetching past race data for each horse...`);
    for (let i = 0; i < result.horses.length; i++) {
      const horse = result.horses[i];
      if (!horse.horse_id) {
        console.error(`  [${i + 1}/${result.horses.length}] ${horse.name}: no horse_id, skipping`);
        continue;
      }

      console.error(`  [${i + 1}/${result.horses.length}] ${horse.name}...`);
      try {
        const horseUrl = `https://db.netkeiba.com/horse/${horse.horse_id}`;
        await page.goto(horseUrl, { waitUntil: 'networkidle2', timeout: 30000 });
        await sleep(1500);

        horse.past_races = await page.evaluate(() => {
          const rows = document.querySelectorAll('.db_h_race_results tbody tr');
          const races = [];
          for (let j = 0; j < Math.min(rows.length, 10); j++) {
            const cells = rows[j].querySelectorAll('td');
            if (cells.length < 20) continue;
            const race = {
              date: cells[0] ? cells[0].textContent.trim() : '',
              venue: cells[1] ? cells[1].textContent.trim() : '',
              race_name: cells[4] ? cells[4].textContent.trim() : '',
              head_count: cells[6] ? cells[6].textContent.trim() : '',
              post_position: cells[7] ? cells[7].textContent.trim() : '',
              odds: cells[8] ? cells[8].textContent.trim() : '',
              popularity: cells[9] ? cells[9].textContent.trim() : '',
              finish: cells[10] ? cells[10].textContent.trim() : '',
              jockey: cells[11] ? cells[11].textContent.trim() : '',
              impost: cells[12] ? cells[12].textContent.trim() : '',
              distance: cells[14] ? cells[14].textContent.trim() : '',
              track_condition: cells[15] ? cells[15].textContent.trim() : '',
              time: cells[16] ? cells[16].textContent.trim() : '',
              margin: cells[17] ? cells[17].textContent.trim() : '',
              passing: cells[19] ? cells[19].textContent.trim() : '',
              last_3f: cells[22] ? cells[22].textContent.trim() : '',
              body_weight: cells[23] ? cells[23].textContent.trim() : '',
            };
            // 距離から芝/ダートを抽出
            const distText = cells[14] ? cells[14].textContent.trim() : '';
            race.surface = distText.includes('ダ') ? 'ダート' : '芝';
            const dm = distText.match(/(\d{3,4})/);
            race.distance_m = dm ? parseInt(dm[1]) : 0;
            // クラス
            race.class_name = cells[4] ? cells[4].textContent.trim() : '';

            races.push(race);
          }
          return races;
        });

        console.error(`    → ${(horse.past_races || []).length} past races`);
      } catch (e) {
        console.error(`    → Failed: ${e.message}`);
        horse.past_races = [];
      }
    }

    // ─── Step 4: オッズ・人気 (出馬表ページに戻る) ───
    console.error(`[4/4] Fetching odds...`);
    try {
      const oddsUrl = `https://race.netkeiba.com/odds/index.html?race_id=${raceId}&type=b1`;
      await page.goto(oddsUrl, { waitUntil: 'networkidle2', timeout: 30000 });
      await sleep(2000);

      const oddsData = await page.evaluate(() => {
        const rows = document.querySelectorAll('.Basic tr, .Odds_Table tr, table tr');
        const result = {};
        for (const row of rows) {
          const cells = row.querySelectorAll('td');
          if (cells.length < 3) continue;
          const numEl = row.querySelector('.Umaban, .Num');
          const oddsEl = row.querySelector('.Odds, .Popular');
          if (numEl && oddsEl) {
            const num = parseInt(numEl.textContent.trim());
            const odds = parseFloat(oddsEl.textContent.trim());
            if (num && odds) {
              result[num] = odds;
            }
          }
        }
        return result;
      });

      for (const horse of result.horses) {
        if (oddsData[horse.post]) {
          horse.odds = oddsData[horse.post];
        }
      }
      console.error(`[4/4] Odds data retrieved`);
    } catch (e) {
      console.error(`[4/4] Odds fetch failed: ${e.message}`);
    }

  } finally {
    await browser.close();
  }

  return result;
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ─── CLI ───
async function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error('Usage: node scripts/scrape-race.js <race_id_or_url> [--chrome-profile <path>]');
    process.exit(1);
  }

  const raceId = extractRaceId(args[0]);
  let chromeProfile = null;
  const profileIdx = args.indexOf('--chrome-profile');
  if (profileIdx >= 0 && args[profileIdx + 1]) {
    chromeProfile = args[profileIdx + 1];
  }

  console.error(`\n=== netkeiba Race Scraper ===`);
  console.error(`Race ID: ${raceId}`);

  const data = await scrapeRace(raceId, chromeProfile);

  // JSON出力
  const outDir = path.resolve(__dirname, '..', 'keiba', 'data');
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, `${raceId}.json`);
  fs.writeFileSync(outFile, JSON.stringify(data, null, 2), 'utf-8');

  console.error(`\n✅ Saved: ${outFile}`);

  // stdoutにも出力 (パイプ用)
  console.log(JSON.stringify(data, null, 2));
}

main().catch(err => {
  console.error(`❌ Error: ${err.message}`);
  process.exit(1);
});
