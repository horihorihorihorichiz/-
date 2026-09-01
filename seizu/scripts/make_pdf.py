# -*- coding: utf-8 -*-
"""PDFを2本つくる。

pdf/二級建築士_製図早見盤.pdf … 早見盤の全内容（読み物）
pdf/二級建築士_図面集.pdf     … 図面だけを1ページ1枚で大きく
pdf/予想問題集A-F_問題用紙.pdf   … 公式の様式にならった問題用紙6セット
pdf/予想問題集A-F_標準解答例.pdf … その解答例（面積表・計画の要点等・図面）

Chromium の印刷機能を使う（外部ライブラリ不要）。
"""
import io
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_onepage import inline_svg          # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, 'pdf')
TMP = os.path.join(OUT, '_tmp')
CHROME = os.environ.get(
    'CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')

FONT = ("'Hiragino Sans','Noto Sans JP','Yu Gothic',Meiryo,"
        "'IPAGothic',sans-serif")

PRINT_CSS = """
<style>
@page{size:A4;margin:12mm 11mm}
nav{display:none!important}
.shell{max-width:none;padding:0}
section[role=tabpanel]{display:block!important;animation:none!important;
  break-before:page}
section[role=tabpanel]#p1{break-before:auto}
body{background:#fff!important;background-image:none!important;font-size:12.5px;
  line-height:1.75}
:root{--paper:#fff;--panel:#fff}
h2{break-after:avoid;break-inside:avoid;margin:22px 0 4px;font-size:19px}
h3{margin:16px 0 4px}
p{margin:8px 0;max-width:none}
figure{margin:12px 0;break-inside:avoid}
.sheet{box-shadow:none;border:1px solid #ddd;padding:6px}
.sheet svg{max-height:196mm;width:auto;max-width:100%;display:block;margin:0 auto}
.flag,.qa,.panel,.tw,.paper{break-inside:avoid}
.flag{margin:12px 0;padding:12px 14px}
.qa{margin:10px 0;padding:12px 14px}
.deck .ctrl,.deck .bar2,#stage,.wsearch,.whit{display:none!important}
.dimline{max-width:520px}
.term{padding:7px 0}
header{padding:14px 0 10px}
footer{display:none}
</style>
"""

FIGS = [
    ('答案の作法', 'symbols', '答案で使う記号の一覧'),
    ('答案の作法', 'hanrei', '伏図の表示記号（凡例欄）'),
    ('答案の作法', 'anselev_s', '南側立面図（答案の描き方）'),
    ('答案の作法', 'ansfuse_floor', '床伏図（答案の描き方）'),
    ('答案の作法', 'ansfuse_roof', '小屋伏図（答案の描き方）'),
    ('型', 'plan1f', '1階平面図 兼 配置図'),
    ('型', 'plan2f', '2階平面図'),
    ('型', 'plan3f', '3階平面図'),
    ('型', 'stair', '階段の段数の割付'),
    ('型', 'stair_updown', '階段のUPとDN'),
    ('型', 'kaidan', '階段の描き方（6コマ）'),
    ('型', 'tobira', '扉と窓の描き方'),
    ('基本', 'suuji', '数字はぜんぶ910から'),
    ('型', 'section', '木材の寸法の書き方（幅×せい）'),
    ('骨組み', 'framing_floor', '床伏図'),
    ('骨組み', 'framing_roof', '小屋伏図'),
    ('骨組み', 'beamsize', '梁のせいの決め方'),
    ('高さ', 'gl', 'GLとFL（高さの基準）'),
    ('高さ', 'mado', '立面図の窓の描き方'),
    ('高さ', 'elevation_s', '南立面図'),
    ('部分詳細図', 'detail_key', 'どこを切った図なのか'),
    ('部分詳細図', 'shousai', '部分詳細図の描き方'),
    ('部分詳細図', 'detail_wall', '外壁の6層（横に切った図）'),
    ('部分詳細図', 'detail_foot', '拡大A　地面のところ'),
    ('部分詳細図', 'detail_floor2', '拡大B　2階の床のところ'),
    ('部分詳細図', 'detail', '本番で提出する1枚'),
    ('記述', 'youten', '計画の要点等の書き方'),
    ('記述', 'hourei', '法令集の補強のしかた'),
    ('解き方', 'esquisse', 'エスキスの6手順'),
    ('解き方', 'esquisse2', 'スパンをどこで割るか'),
    ('解き方', 'slope', 'スロープと床の高さ'),
    ('解き方', 'site', '配置図の型'),
    ('予想A', 'ansA_1f', '1階（客用便所を売場から）'),
    ('予想B', 'ansB_1f', '1階（母の和室）'),
    ('予想B', 'ansB_2f', '2階'),
    ('予想B', 'ansB_3f', '3階'),
    ('予想C', 'ansC_1f', '1階（細長い敷地）'),
    ('予想C', 'ansC_2f', '2階'),
    ('予想C', 'ansC_3f', '3階'),
    ('予想D', 'ansD_1f', '1階（東側道路）'),
    ('予想E', 'ansE_1f', '1階（南東の角地）'),
    ('予想F', 'ansF_1f', '1階（北側道路）'),
]


def to_pdf(html_path, pdf_path):
    subprocess.run(
        [CHROME, '--headless', '--disable-gpu', '--no-sandbox',
         '--no-pdf-header-footer', '--virtual-time-budget=20000',
         '--print-to-pdf=' + pdf_path, 'file://' + html_path],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print('wrote %s  (%.1f MB)'
          % (pdf_path, os.path.getsize(pdf_path) / 1048576.0))


def build_hayami():
    src = io.open(os.path.join(BASE, 'onepage.html'), encoding='utf-8').read()
    src = src.replace('</style>', '</style>' + PRINT_CSS, 1)
    p = os.path.join(TMP, 'hayami.html')
    io.open(p, 'w', encoding='utf-8').write(src)
    to_pdf(p, os.path.join(OUT, '二級建築士_製図早見盤.pdf'))


def build_a2(src_name, pdf_name):
    """A2横の問題用紙をそのままPDFにする。"""
    to_pdf(os.path.join(BASE, src_name), pdf_name)


def build_plain(src_name, pdf_name):
    """すでにプリント向けに書かれたHTMLをそのままPDFにする。"""
    to_pdf(os.path.join(BASE, src_name), os.path.join(OUT, pdf_name))


def build_zumen():
    css = [
        '<title>図面集</title><style>',
        '@page{size:A4;margin:10mm}',
        '*{box-sizing:border-box;margin:0;padding:0}',
        'body{font-family:%s;background:#fff;color:#1b1e1b}' % FONT,
        '.pg{break-after:page;height:277mm;display:flex;flex-direction:column}',
        '.pg:last-child{break-after:auto}',
        '.hd{display:flex;align-items:baseline;gap:10px;'
        'border-bottom:2px solid #a8324a;padding-bottom:5px;margin-bottom:8px}',
        '.hd .cat{font-size:11px;letter-spacing:.12em;color:#a8324a;'
        'font-weight:700}',
        '.hd .ti{font-size:16px;font-weight:700}',
        '.hd .no{margin-left:auto;font-size:11px;color:#8a8f88}',
        '.bd{flex:1;display:flex;align-items:center;justify-content:center;'
        'min-height:0}',
        '.bd svg{max-width:100%;max-height:100%;width:auto;height:auto}',
        '</style>']
    for i, (cat, name, title) in enumerate(FIGS, 1):
        css.append('<div class="pg"><div class="hd">'
                   '<span class="cat">%s</span><span class="ti">%s</span>'
                   '<span class="no">%d / %d</span></div>'
                   '<div class="bd">%s</div></div>'
                   % (cat, title, i, len(FIGS), inline_svg(name)))
    p = os.path.join(TMP, 'zumen.html')
    io.open(p, 'w', encoding='utf-8').write(''.join(css))
    to_pdf(p, os.path.join(OUT, '二級建築士_図面集.pdf'))


# ---------------------------------------------------------------
# 予想問題集：問題と解答を1問ずつ別のPDFにする
# ---------------------------------------------------------------
SHEETS = os.path.join(BASE, 'sheets')
KEYS = ['A', 'B', 'C', 'D', 'E', 'F']

A3CSS = ("<style>@page{size:594mm 420mm;margin:0}"
         "html,body{margin:0;padding:0;background:#fff}"
         ".pg{width:594mm;height:420mm;break-after:page;overflow:hidden}"
         ".pg:last-child{break-after:auto}"
         ".pg svg{width:594mm;height:420mm;display:block}</style>")


def _svg(name):
    t = io.open(os.path.join(SHEETS, name + '.svg'),
                encoding='utf-8').read()
    return t.replace('width="1684" height="1191"', '', 1)


def build_a3(names, pdf_name):
    """A3横のシートを並べて1本のPDFにする。"""
    html = [A3CSS] + ['<div class="pg">%s</div>' % _svg(n) for n in names]
    p = os.path.join(TMP, 'a3_%s.html'
                     % os.path.basename(pdf_name).replace('.pdf', ''))
    io.open(p, 'w', encoding='utf-8').write(''.join(html))
    to_pdf(p, pdf_name)


def build_mondaishu():
    """1問ずつ「問題」と「解答例」を別のPDFにして pdf/予想問題集/ に置く。"""
    d = os.path.join(OUT, '予想問題集')
    os.makedirs(d, exist_ok=True)
    for k in KEYS:
        build_a2('mondai_%s.html' % k,
                 os.path.join(d, '予想問題%s_問題.pdf' % k))
        build_a3(['kaitou_%s' % k, 'kaitou_common1', 'kaitou_common2'],
                 os.path.join(d, '予想問題%s_解答例.pdf' % k))
    build_a2('mondai_all.html', os.path.join(d, '00_問題編_A-F.pdf'))
    build_a3(['kaitou_%s' % k for k in KEYS] +
             ['kaitou_common1', 'kaitou_common2'],
             os.path.join(d, '00_解答編_A-F.pdf'))


if __name__ == '__main__':
    os.makedirs(TMP, exist_ok=True)
    build_hayami()
    build_zumen()
    build_plain('kaisetsu.html', '二級建築士_答案用紙まるごと解説.pdf')
    build_plain('mondai_all.html', '予想問題集A-F_問題用紙.pdf')
    build_plain('kaitou_all.html', '予想問題集A-F_標準解答例.pdf')
    build_mondaishu()
