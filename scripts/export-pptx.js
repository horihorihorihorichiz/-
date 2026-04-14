#!/usr/bin/env node
/**
 * Slides-to-Web → PowerPoint エクスポーター
 *
 * 1. Puppeteerでindex.htmlを開く
 * 2. 各スライドを16:9(1920x1080)でスクリーンショット
 * 3. pptxgenjsでPowerPointファイルに組み込む
 *
 * Usage: node scripts/export-pptx.js [options]
 *   --input   slides/index.html  (default)
 *   --output  slides/exports/presentation.pptx (default)
 */

const puppeteer = require('puppeteer');
const PptxGenJS = require('pptxgenjs');
const path = require('path');
const fs = require('fs');

const SLIDE_WIDTH = 1920;
const SLIDE_HEIGHT = 1080;

async function main() {
  // Parse args
  const args = process.argv.slice(2);
  let inputFile = path.resolve(__dirname, '..', 'slides', 'index.html');
  let outputFile = path.resolve(__dirname, '..', 'slides', 'exports', 'presentation.pptx');

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--input' && args[i + 1]) inputFile = path.resolve(args[++i]);
    if (args[i] === '--output' && args[i + 1]) outputFile = path.resolve(args[++i]);
  }

  // Ensure output directory exists
  fs.mkdirSync(path.dirname(outputFile), { recursive: true });

  // Temp directory for screenshots
  const tmpDir = path.resolve(__dirname, '..', '.slide-screenshots');
  fs.mkdirSync(tmpDir, { recursive: true });

  console.log('🚀 Starting export...');
  console.log(`   Input:  ${inputFile}`);
  console.log(`   Output: ${outputFile}`);

  // Launch browser
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: SLIDE_WIDTH, height: SLIDE_HEIGHT });

  // In sandboxed / remote Claude Code environments external font requests
  // (Google Fonts) sometimes never settle and make networkidle hang.
  // Abort those requests only in that case so navigation completes quickly.
  if (process.env.CLAUDE_CODE_REMOTE === 'true') {
    await page.setRequestInterception(true);
    page.on('request', (req) => {
      const url = req.url();
      if (/fonts\.googleapis\.com|fonts\.gstatic\.com/.test(url)) {
        req.abort();
      } else {
        req.continue();
      }
    });
  }

  await page.goto(`file://${inputFile}`, { waitUntil: 'load', timeout: 60000 });
  try {
    await page.waitForFunction(
      () => document.fonts && document.fonts.status === 'loaded',
      { timeout: 10000 }
    );
  } catch (_) {
    // Fonts didn't report ready in time; proceed anyway.
  }
  // Small settle buffer for final layout.
  await new Promise(r => setTimeout(r, 300));

  // Get total number of slides
  const totalSlides = await page.evaluate(() => {
    return document.querySelectorAll('.slide').length;
  });

  console.log(`   Found ${totalSlides} slides`);

  // Screenshot each slide
  const screenshotPaths = [];

  for (let i = 0; i < totalSlides; i++) {
    // Navigate to slide
    await page.evaluate((index) => {
      const slides = document.querySelectorAll('.slide');
      slides.forEach((s, j) => {
        s.classList.toggle('active', j === index);
      });
    }, i);

    // Wait for animations to settle
    await new Promise(r => setTimeout(r, 800));

    const screenshotPath = path.join(tmpDir, `slide-${String(i + 1).padStart(3, '0')}.png`);
    await page.screenshot({ path: screenshotPath, type: 'png' });
    screenshotPaths.push(screenshotPath);

    console.log(`   ✓ Slide ${i + 1}/${totalSlides} captured`);
  }

  await browser.close();

  // Build PowerPoint
  console.log('\n📦 Building PowerPoint...');
  const pptx = new PptxGenJS();
  pptx.layout = 'LAYOUT_WIDE'; // 13.33 x 7.5 inches (16:9)

  for (const imgPath of screenshotPaths) {
    const slide = pptx.addSlide();
    const imgData = fs.readFileSync(imgPath).toString('base64');
    slide.addImage({
      data: `image/png;base64,${imgData}`,
      x: 0,
      y: 0,
      w: '100%',
      h: '100%',
    });
  }

  await pptx.writeFile({ fileName: outputFile });
  console.log(`\n✅ Exported: ${outputFile}`);

  // Cleanup temp screenshots
  for (const p of screenshotPaths) {
    fs.unlinkSync(p);
  }
  fs.rmdirSync(tmpDir);

  console.log('🧹 Cleaned up temporary files');
}

main().catch((err) => {
  console.error('❌ Export failed:', err.message);
  process.exit(1);
});
