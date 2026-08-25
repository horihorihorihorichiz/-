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

// pages: { modules:[...js in dep order], css:[...], html, out, docsName, title, standaloneName }
function build({ modules, css, html, out, docsName, title = '韓麻', standaloneName }) {
  const js = modules.map(f => `// ===== ${f} =====\n` + strip(R(f))).join('\n\n');
  const styles = css.map(R).join('\n');
  const bodyInner = R(html).match(/<body>([\s\S]*?)<script/)[1]
    .replace(/<link[^>]*>/g, '');
  const artifactBody = bodyInner.replace(/<a\s+href="(index|play|quiz)\.html"[\s\S]*?<\/a>/g, '');
  const wrap = (body) => `<!doctype html><html lang="ja"><head><meta charset="UTF-8">` +
    `<meta name="viewport" content="width=device-width, initial-scale=1.0">` +
    `<title>${title}</title><style>\n${styles}\n</style></head><body>\n${body}\n<script>\n${js}\n</script></body></html>`;

  mkdirSync(join(base, 'dist'), { recursive: true });
  // Artifact 用（body+script のみ）
  writeFileSync(join(base, 'dist', out), `<style>\n${styles}\n</style>\n${artifactBody}\n<script>\n${js}\n</script>`);
  console.log(`built dist/${out}`);
  // 配布用（タイトル付きの完全な単一HTML・内部リンクなし）
  if (standaloneName) { writeFileSync(join(base, 'dist', standaloneName), wrap(artifactBody)); console.log(`built dist/${standaloneName}`); }

  // GitHub Pages 用（リポジトリ直下 /docs・内部リンク維持）
  if (docsName) {
    const pagesDir = join(base, '..', 'docs');
    mkdirSync(pagesDir, { recursive: true });
    writeFileSync(join(pagesDir, docsName), wrap(bodyInner));
    console.log(`built /docs/${docsName}`);
  }
}

// 実戦
build({
  modules: ['src/tiles.js', 'src/tiles-data.js', 'src/tileview.js', 'src/shanten.js', 'src/ukeire.js', 'src/score.js', 'src/analyze.js', 'src/danger.js', 'src/game.js', 'src/play.js'],
  css: ['styles.css', 'play.css'],
  html: 'play.html',
  out: 'play-standalone.html',
  docsName: 'play.html',
  title: '韓麻 実戦（対AI）🀄',
  standaloneName: '韓麻-実戦.html',
});

// 何切るクイズ
build({
  modules: ['src/tiles.js', 'src/tiles-data.js', 'src/tileview.js', 'src/shanten.js', 'src/ukeire.js', 'src/score.js', 'src/analyze.js', 'src/danger.js', 'src/mc.js', 'src/game.js', 'src/quiz.js'],
  css: ['styles.css', 'quiz.css'],
  html: 'quiz.html',
  out: 'quiz-standalone.html',
  docsName: 'quiz.html',
  title: '韓麻 何切るクイズ 🀄',
  standaloneName: '韓麻-何切るクイズ.html',
});

// ベタおり練習（守り専用ドリル）
build({
  modules: ['src/tiles.js', 'src/tiles-data.js', 'src/tileview.js', 'src/shanten.js', 'src/ukeire.js', 'src/score.js', 'src/analyze.js', 'src/danger.js', 'src/game.js', 'src/betaori.js'],
  css: ['styles.css', 'quiz.css', 'betaori.css'],
  html: 'betaori.html',
  out: 'betaori-standalone.html',
  docsName: 'betaori.html',
  title: '韓麻 ベタおり練習 🀄',
  standaloneName: '韓麻-ベタおり練習.html',
});

// 麻雀 守りGTO（通常ルール・相手の待ち読み）
build({
  modules: ['src/tiles.js', 'src/tiles-data.js', 'src/tileview.js', 'src/shanten.js', 'src/guard.js'],
  css: ['styles.css', 'quiz.css', 'guard.css'],
  html: 'guard.html',
  out: 'guard-standalone.html',
  docsName: 'guard.html',
  title: '麻雀 守りGTO 🀄',
  standaloneName: '麻雀-守りGTO.html',
});
