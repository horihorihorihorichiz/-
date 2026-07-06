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

// pages: { modules:[...js in dep order], css:[...], html, out }
function build({ modules, css, html, out }) {
  const js = modules.map(f => `// ===== ${f} =====\n` + strip(R(f))).join('\n\n');
  const styles = css.map(R).join('\n');
  const bodyInner = R(html).match(/<body>([\s\S]*?)<script/)[1]
    .replace(/<link[^>]*>/g, '')
    .replace(/<a\s+href="(index|play|quiz)\.html"[\s\S]*?<\/a>/g, ''); // 内部リンクは削除
  const doc = `<style>\n${styles}\n</style>\n${bodyInner}\n<script>\n${js}\n</script>`;
  mkdirSync(join(base, 'dist'), { recursive: true });
  writeFileSync(join(base, 'dist', out), doc);
  console.log(`built dist/${out}, bytes=`, doc.length);
}

// 実戦
build({
  modules: ['src/tiles.js', 'src/tileview.js', 'src/shanten.js', 'src/ukeire.js', 'src/score.js', 'src/analyze.js', 'src/game.js', 'src/play.js'],
  css: ['styles.css', 'play.css'],
  html: 'play.html',
  out: 'play-standalone.html',
});

// 何切るクイズ
build({
  modules: ['src/tiles.js', 'src/tileview.js', 'src/shanten.js', 'src/ukeire.js', 'src/score.js', 'src/analyze.js', 'src/danger.js', 'src/game.js', 'src/quiz.js'],
  css: ['styles.css', 'quiz.css'],
  html: 'quiz.html',
  out: 'quiz-standalone.html',
});
