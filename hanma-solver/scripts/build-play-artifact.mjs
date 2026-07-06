// hanma-solver を単一HTML(dist/play-standalone.html)に束ねる。
//   node hanma-solver/scripts/build-play-artifact.mjs
// ES モジュール群から import/export を除去して1つの <script> に連結し、
// CSS と play.html の body を inline 化する（claude.ai の Artifact 等にそのまま使える）。
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const base = join(dirname(fileURLToPath(import.meta.url)), '..'); // hanma-solver/
const R = (p) => readFileSync(join(base, p), 'utf8');

// import 文（複数行対応）と export キーワードを除去
function strip(js) {
  return js
    .replace(/import\s+[\s\S]*?from\s+['"][^'"]+['"];?/g, '')
    .replace(/^\s*export\s+/gm, '');
}

const order = ['src/tiles.js','src/shanten.js','src/ukeire.js','src/score.js','src/analyze.js','src/game.js','src/play.js'];
let js = order.map(f => `// ===== ${f} =====\n` + strip(R(f))).join('\n\n');

const css = R('styles.css') + '\n' + R('play.css');

// play.html の body 内容（wrap 部分）を抽出
let html = R('play.html');
const bodyInner = html.match(/<body>([\s\S]*?)<script/)[1]
  .replace(/<link[^>]*>/g, '')                             // link 除去（CSSはinline）
  .replace(/<a\s+href="index\.html"[\s\S]*?<\/a>/g, '');   // ソルバーへのリンクを丸ごと削除

const out = `<style>
${css}
</style>
${bodyInner}
<script>
${js}
</script>`;

mkdirSync(join(base, 'dist'), { recursive: true });
writeFileSync(join(base, 'dist', 'play-standalone.html'), out);

console.log('built dist/play-standalone.html, bytes=', out.length);
