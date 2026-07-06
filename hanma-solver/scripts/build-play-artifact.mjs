// hanma-solver を単一HTML(dist/*.html)に束ねる。
//   node hanma-solver/scripts/build-play-artifact.mjs
// ESモジュール群から import/export を除去して1つの <script> に連結し、
// CSS と *.html の body を inline 化する（claude.ai の Artifact 等にそのまま使える）。
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const base = join(dirname(fileURLToPath(import.meta.url)), '..'); // hanma-solver/
const R = (p) => readFileSync(join(base, p), 'utf8');

function strip(js) {
  return js
    .replace(/import\s+[\s\S]*?from\s+['"][^'"]+['"];?/g, '')
    .replace(/^\s*export\s+/gm, '');
}

// pages: { modules:[...js in dep order], css:[...], html, out, docsName, keepLinks }
function build({ modules, css, html, out, docsName }) {
  const js = modules.map(f => `// ===== ${f} =====\n` + strip(R(f))).join('\n\n');
  const styles = css.map(R).join('\n');
  const bodyInner = R(html).match(/<body>([\s\S]*?)<script/)[1]
    .replace(/<link[^>]*>/g, '');
  // 単一HTML(Artifact)版: 内部リンクは削除
  const artifactBody = bodyInner.replace(/<a\s+href="(index|play|quiz)\.html"[\s\S]*?<\/a>/g, '');
  const wrap = (body) => `<!doctype html><html lang="ja"><head><meta charset="UTF-8">` +
    `<meta name="viewport" content="width=device-width, initial-scale=1.0">` +
    `<title>韓麻</title><style>\n${styles}\n</style></head><body>\n${body}\n<script>\n${js}\n</script></body></html>`;

  mkdirSync(join(base, 'dist'), { recursive: true });
  writeFileSync(join(base, 'dist', out), `<style>\n${styles}\n</style>\n${artifactBody}\n<script>\n${js}\n</script>`);
  console.log(`built dist/${out}`);

  // GitHub Pages 用（リポジトリ直下 /docs。内部リンクは維持して完全な html を書き出す）
  if (docsName) {
    const pagesDir = join(base, '..', 'docs');
    mkdirSync(pagesDir, { recursive: true });
    writeFileSync(join(pagesDir, docsName), wrap(bodyInner));
    console.log(`built /docs/${docsName}`);
  }
}

// 実戦
build({
  modules: ['src/tiles.js', 'src/tileview.js', 'src/shanten.js', 'src/ukeire.js', 'src/score.js', 'src/analyze.js', 'src/game.js', 'src/play.js'],
  css: ['styles.css', 'play.css'],
  html: 'play.html',
  out: 'play-standalone.html',
  docsName: 'play.html',
});

// 何切るクイズ
build({
  modules: ['src/tiles.js', 'src/tileview.js', 'src/shanten.js', 'src/ukeire.js', 'src/score.js', 'src/analyze.js', 'src/danger.js', 'src/game.js', 'src/quiz.js'],
  css: ['styles.css', 'quiz.css'],
  html: 'quiz.html',
  out: 'quiz-standalone.html',
  docsName: 'quiz.html',
});
