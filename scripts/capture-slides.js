#!/usr/bin/env node
/**
 * Capture each slide as a PNG for inline preview.
 * Usage: node scripts/capture-slides.js <input.html> <outDir>
 */
const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const W = 1920, H = 1080;

async function main() {
  const input = path.resolve(process.argv[2] || 'slides/architecture2026.html');
  const outDir = path.resolve(process.argv[3] || '.slide-preview');
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H });

  if (process.env.CLAUDE_CODE_REMOTE === 'true') {
    await page.setRequestInterception(true);
    page.on('request', (req) => {
      if (/fonts\.googleapis\.com|fonts\.gstatic\.com/.test(req.url())) req.abort();
      else req.continue();
    });
  }

  await page.goto(`file://${input}`, { waitUntil: 'load', timeout: 60000 });
  try { await page.waitForFunction(() => document.fonts && document.fonts.status === 'loaded', { timeout: 10000 }); } catch {}
  await new Promise(r => setTimeout(r, 400));

  const total = await page.evaluate(() => document.querySelectorAll('.slide').length);
  for (let i = 0; i < total; i++) {
    await page.evaluate((idx) => {
      document.querySelectorAll('.slide').forEach((s, j) => s.classList.toggle('active', j === idx));
    }, i);
    await new Promise(r => setTimeout(r, 500));
    const p = path.join(outDir, `slide-${String(i + 1).padStart(2, '0')}.png`);
    await page.screenshot({ path: p, type: 'png' });
    console.log(p);
  }
  await browser.close();
}
main().catch(e => { console.error(e); process.exit(1); });
