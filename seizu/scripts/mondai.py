# -*- coding: utf-8 -*-
"""公式の様式にならった問題用紙と標準解答例をつくる。

過去問（令和5年・令和7年）の問題用紙の章立て・文言・表の構成を写し、
令和8年度の課題「商店街に建つ併用住宅（木造3階建て）」に置きかえたもの。
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_onepage import inline_svg          # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MIN = ("'Zen Old Mincho','Hiragino Mincho ProN','Yu Mincho','MS Mincho',"
       "serif")
GO = ("'Hiragino Sans','Noto Sans JP','Yu Gothic',Meiryo,'IPAGothic',"
      "sans-serif")

CSS = """
<style>
@page{size:A4;margin:14mm 13mm}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:%s;font-size:11.5px;line-height:1.75;color:#000;
  background:#fff}
.sheet{max-width:186mm;margin:0 auto}
.note0{border:1px solid #000;padding:7px 9px;font-size:10.5px;line-height:1.6;
  margin-bottom:14px}
.kadai{text-align:center;font-family:%s;font-size:17px;font-weight:700;
  letter-spacing:.08em;margin:16px 0 18px;padding:7px 0;
  border-top:2px solid #000;border-bottom:2px solid #000}
h2.sec{font-family:%s;font-size:14px;font-weight:700;margin:20px 0 7px}
h3.sub{font-size:12px;font-weight:700;margin:13px 0 4px}
p{margin:5px 0}
.ind{margin-left:1.1em}
ol.jp{list-style:none;counter-reset:jp;margin:4px 0 4px 1.6em}
ol.jp>li{counter-increment:jp;position:relative;margin:3px 0}
ol.jp>li::before{content:counter(jp,katakana)"．";position:absolute;
  left:-1.7em;width:1.6em;text-align:left}
ol.maru{list-style:none;counter-reset:mr;margin:4px 0 4px 1.6em}
ol.maru>li{counter-increment:mr;position:relative;margin:3px 0}
ol.maru>li::before{content:"("counter(mr)")";position:absolute;left:-1.9em}
ul.dot{list-style:none;margin:3px 0 3px 1em}
ul.dot>li{position:relative;margin:2px 0}
ul.dot>li::before{content:"・";position:absolute;left:-1em}
table{border-collapse:collapse;width:100%%;font-size:10.5px;margin:7px 0;
  line-height:1.6}
th,td{border:1px solid #000;padding:4px 6px;vertical-align:top}
th{background:#f0f0f0;font-weight:700;text-align:center}
td.c{text-align:center;vertical-align:middle;width:34px;font-weight:700}
td.rm{width:96px;font-weight:700}
td.n{text-align:right;font-family:%s}
.fig{text-align:center;margin:16px 0}
.fig svg{max-width:100%%;height:auto}
.brk{break-before:page}
.stamp{border:2px solid #000;display:inline-block;padding:5px 22px;
  font-family:%s;font-size:15px;font-weight:700;letter-spacing:.2em}
.ansbox{border:1px solid #000;padding:9px 11px;margin:9px 0}
.ansbox .q{font-weight:700;margin-bottom:5px}
.ansbox .a{font-size:11px;line-height:1.9}
.cap{font-size:10px;color:#444;text-align:center;margin-top:5px}
.warn{border:1px solid #999;background:#f7f7f7;padding:8px 10px;
  font-size:10.5px;margin:12px 0}
</style>
""" % (GO, MIN, MIN, GO, MIN)

ROOMS = [
    ('１<br>階', '店舗売場',
     'ア．25m<sup>2</sup>以上とする。<br>'
     'イ．道路に面して出入口を設ける。<br>'
     'ウ．陳列棚及びレジカウンターを設ける。'),
    ('', '厨房・作業場',
     'ア．9m<sup>2</sup>以上とする。<br>'
     'イ．店舗売場に隣接させ、直接行き来できるようにする。<br>'
     'ウ．流し台、調理台、作業台及びオーブンを設ける。'),
    ('', 'スタッフルーム',
     'ア．6m<sup>2</sup>以上とする。<br>'
     'イ．従業員の更衣及び休憩に使用する。'),
    ('', '店舗用便所',
     'ア．来客が利用できるものとする。<br>'
     'イ．洋式便器及び手洗い器を設ける。'),
    ('', '倉　庫', '・商品及び材料を保管する。'),
    ('', '玄　関',
     'ア．住宅部分の玄関とし、道路から直接出入りできるものとする。<br>'
     'イ．下足入れを設ける。'),
    ('２<br>階', '居間・食事室・台所',
     'ア．１室にまとめ、25m<sup>2</sup>以上として計画する。<br>'
     'イ．ソファー、テーブル及び椅子（計４席以上）を設ける。<br>'
     'ウ．台所設備機器（流し台・調理台・コンロ台・冷蔵庫等）を設ける。'),
    ('', '和　室',
     'ア．６畳以上とする。<br>'
     'イ．居間に隣接させ、直接行き来できるようにする。<br>'
     'ウ．押入れを設ける。'),
    ('', '浴室・洗面脱衣室',
     '・浴室には浴槽、洗面脱衣室には洗面台及び洗濯機を設ける。'),
    ('', '便　所', '・洋式便器を設ける。'),
    ('', '家事室', '・納戸を兼ねてもよい。'),
    ('３<br>階', '夫婦寝室',
     'ア．13m<sup>2</sup>以上とする。<br>'
     'イ．洋室とし、ベッド（計２台）及び収納を設ける。'),
    ('', '子ども室',
     'ア．２室（各8m<sup>2</sup>以上）設け、いずれも同じ広さとする。<br>'
     'イ．いずれも洋室とし、ベッド、机及び収納を設ける。'),
    ('', '便　所', '・洋式便器を設ける。'),
    ('', '納　戸', ''),
]

ZUSHO = [
    ('⑴ １階平面図兼配置図<br>（１/100）<br><br>'
     '⑵ ２階平面図<br>（１/100）<br><br>'
     '⑶ ３階平面図<br>（１/100）',
     'ア．１階平面図兼配置図、２階平面図及び３階平面図には、次のものを'
     '記入する。'
     '<ul class="dot"><li>建築物の主要な寸法</li><li>室名等</li>'
     '<li>「通し柱」を○印で囲み、「耐力壁」には△印を付ける。</li>'
     '<li>部分詳細図の切断位置及び方向</li></ul>'
     'イ．１階平面図兼配置図には、次のものを記入する。'
     '<ul class="dot"><li>敷地境界線と建築物との距離</li>'
     '<li>道路から建築物へのアプローチ、駐輪スペース、門、塀、植栽等</li>'
     '<li>道路から敷地及び建築物への出入口には、▲印を付ける。</li>'
     '<li>玄関及び店舗売場の土間部分の地盤面からの高さ</li>'
     '<li>玄関ホール（廊下）の床高</li>'
     '<li>店舗売場…陳列棚及びレジカウンター</li>'
     '<li>厨房・作業場…流し台、調理台、作業台及びオーブン</li>'
     '<li>店舗用便所…洋式便器及び手洗い器</li>'
     '<li>玄関…下足入れ</li></ul>'
     'ウ．２階平面図には、次のものを記入する。'
     '<ul class="dot">'
     '<li>居間・食事室・台所…ソファー、テーブル、椅子及び台所設備機器</li>'
     '<li>和室…畳及び押入れ</li>'
     '<li>浴室…浴槽／洗面脱衣室…洗面台及び洗濯機／便所…洋式便器</li></ul>'
     'エ．３階平面図には、次のものを記入する。'
     '<ul class="dot"><li>夫婦寝室…ベッド及び収納</li>'
     '<li>子ども室…ベッド、机及び収納</li>'
     '<li>便所…洋式便器</li></ul>'),
    ('⑷ 床伏図兼小屋伏図<br>（１/100）',
     'ア．３階床伏図兼小屋伏図とする。<br>'
     'イ．主要部材（通し柱、各階の管柱、胴差、床梁、桁、小屋梁、火打梁、'
     '棟木、母屋、小屋束等必要なもの）については、凡例の表示記号に'
     'したがって記入し、断面寸法（小屋束を除く。）を凡例欄に記入する。<br>'
     'ウ．火打梁の代わりに構造用面材による床組とする場合には、胴差、床梁、'
     '桁を記入したうえで、構造用合板の厚さ、釘の種類・打ち付け間隔を'
     '明記する。<br>'
     'エ．建築物の主要な寸法を記入する。'),
    ('⑸ 立面図<br>（１/100）',
     'ア．南側立面図とする。<br>'
     'イ．建築物の最高の高さを記入する。'),
    ('⑹ 部分詳細図（断面）<br>（１/20）',
     'ア．切断位置は、外壁を含む部分とし、開口部を含むものとする。<br>'
     'イ．作図の範囲は、基礎から２階の床までとする。<br>'
     'ウ．主要部の寸法等（床高、天井高、階高、基礎の寸法等）を記入する。<br>'
     'エ．主要部材（基礎、土台、柱、胴差、床梁等必要なもの）の名称・'
     '断面寸法を記入する。<br>'
     'オ．アンカーボルト等の名称・寸法を記入する。<br>'
     'カ．外壁、床、その他必要と思われる部分の断熱・防湿措置を記入する。<br>'
     'キ．内外の主要な部位（外壁、床、内壁、天井）の仕上材料名を記入する。'),
    ('⑺ 面積表',
     'ア．建築面積、床面積及び延べ面積を記入する。<br>'
     'イ．建築面積及び床面積については、計算式も記入する。<br>'
     'ウ．面積の数値は、小数点以下第２位までとし、第３位以下は切り捨てる。'),
    ('⑻ 計画の要点等',
     '・建築物の計画に関する次の①〜③について、具体的に記述する。'
     '<ul class="dot">'
     '<li>①　木造３階建てとするに当たり、構造計画上工夫した点</li>'
     '<li>②　店舗部分と住宅部分の動線計画について工夫した点</li>'
     '<li>③　防火及び避難について配慮した点</li></ul>'),
]


def mondai():
    o = ['<title>予想問題A 問題用紙</title>', CSS, '<div class="sheet">']
    o.append('<div class="note0">〔注意事項〕試験問題を十分に読んだうえで、'
             '「設計製図の試験」に臨むようにしてください。なお、建築基準法等の'
             '関係法令や要求図書、主要な要求室等の計画等の設計与条件に対して'
             '解答内容が不十分な場合には、「設計条件・要求図書に対する重大な'
             '不適合」と判断されます。</div>')
    o.append('<div class="warn">この問題用紙は、過去問（令和5年・令和7年）の'
             '様式にならって作成した<b>予想問題</b>です。本物の試験問題では'
             'ありません。実際の出題内容は当日の問題用紙によります。</div>')
    o.append('<div class="kadai">設計課題　「商店街に建つ併用住宅'
             '（木造３階建て）」</div>')

    o.append('<h2 class="sec">1．設計条件</h2>')
    o.append('<p class="ind">ある地方都市の商店街において、パン屋を営む'
             '夫婦とその子ども２人が住むための併用住宅を計画する。</p>')
    o.append('<p class="ind">計画に当たっては、次の①〜③に特に留意する。</p>')
    o.append('<ul class="dot" style="margin-left:1.8em">'
             '<li>①　店舗部分と住宅部分の動線が交錯しないようにする。</li>'
             '<li>②　木造３階建てであることを踏まえ、構造上のバランスに'
             '配慮する。</li>'
             '<li>③　防火及び避難に配慮する。</li></ul>')

    o.append('<h3 class="sub">⑴　敷　地</h3><ol class="jp">'
             '<li>形状、道路との関係、方位等は、下に示す敷地図のとおりで'
             'ある。</li>'
             '<li>近隣商業地域内にあり、準防火地域に指定されている。</li>'
             '<li>建蔽率の限度は80％、容積率の限度は300％である。</li>'
             '<li>地形は平坦で、道路及び隣地との高低差はなく、地盤は良好で'
             'ある。</li>'
             '<li>電気、都市ガス、上水道及び公共下水道は完備している。</li>'
             '</ol>')
    o.append('<h3 class="sub">⑵　構造、階数、建築物の高さ等</h3>'
             '<ol class="jp">'
             '<li>木造３階建てとする。</li>'
             '<li>建築物の最高の高さは11m以下、かつ、軒の高さは9.5m以下と'
             'する。</li>'
             '<li>耐力壁（構造耐力上有効な壁）は、必要な量をバランスよく'
             '配置する。</li></ol>')
    o.append('<h3 class="sub">⑶　延べ面積等</h3><ol class="jp">'
             '<li>延べ面積は、「180m<sup>2</sup>以上、200m<sup>2</sup>以下」'
             'とする。</li>'
             '<li>玄関ポーチ、バルコニー、駐輪スペース等は、床面積に算入'
             'しない。</li></ol>')
    o.append('<h3 class="sub">⑷　人員構成等</h3>'
             '<p class="ind">夫婦（40歳代）、子ども２人（中学生、小学生）</p>')

    o.append('<h3 class="sub">⑸　要求室等</h3>'
             '<p class="ind">下表の全ての室等は、指定された設置階に計画する。'
             '</p><table><tr><th style="width:34px">設置階</th>'
             '<th style="width:96px">室　名　等</th>'
             '<th>特　記　事　項</th></tr>')
    for f, nm, memo in ROOMS:
        span = ''
        if f:
            cnt = 6 if '１' in f else (5 if '２' in f else 4)
            span = '<td class="c" rowspan="%d">%s</td>' % (cnt, f)
        o.append('<tr>%s<td class="rm">%s</td><td>%s</td></tr>'
                 % (span, nm, memo))
    o.append('</table>')
    o.append('<p style="font-size:10.5px">（注1）各要求室等においては、'
             '床面積・広さの指定がない場合、床面積は適宜とする。<br>'
             '（注2）階段は、安全を確保するために、踊場を設ける。</p>')

    o.append('<h3 class="sub">⑹　屋外施設等</h3>'
             '<p class="ind">屋外に下表のものを計画する。</p><table>'
             '<tr><td class="rm">駐輪スペース</td>'
             '<td>・４台分を設ける。</td></tr>'
             '<tr><td class="rm">門・塀・植栽等</td><td></td></tr></table>')

    o.append('<div class="fig">%s</div>' % inline_svg('site_map'))

    o.append('<h2 class="sec brk">2．要求図書</h2>')
    o.append('<ul class="dot" style="margin-left:1.2em">'
             '<li>ａ．答案用紙の定められた枠内に、下表の要求図書を記入する。'
             '（寸法線は、枠外にはみだして記入してもよい。）</li>'
             '<li>ｂ．図面は黒鉛筆仕上げとする。（定規を用いなくてもよい。）'
             '</li>'
             '<li>ｃ．記入寸法の単位は、mmとする。なお、答案用紙の１目盛は、'
             '4.55mm（部分詳細図にあっては、10mm）である。</li>'
             '<li>ｄ．シックハウス対策のための機械換気設備等は、記入しなくて'
             'よい。</li></ul>')
    o.append('<table><tr><th style="width:118px">要　求　図　書'
             '<br>（　）内は縮尺</th><th>特　記　事　項</th></tr>')
    for nm, memo in ZUSHO:
        o.append('<tr><td class="rm">%s</td><td>%s</td></tr>' % (nm, memo))
    o.append('</table>')
    o.append('<p style="font-size:10px;color:#444;margin-top:10px">'
             '※ 実際の試験では、⑵と⑶は「各階平面図」として1つにまとめて'
             '公表されています。答案用紙の枠の分かれ方は当日の指定によります。'
             '</p>')
    o.append('</div>')
    return ''.join(o)


AREA_ROWS = [
    ('敷地面積', '', '180.00'),
    ('建築面積', '（計算式）　7.28 × 9.10', '66.24'),
    ('床面積　１階', '（計算式）　7.28 × 9.10', '① 66.24'),
    ('　　　　２階', '（計算式）　7.28 × 9.10', '② 66.24'),
    ('　　　　３階', '（計算式）　7.28 × 9.10', '③ 66.24'),
    ('延べ面積', '①＋②＋③', '198.72'),
]

YOUTEN = [
    ('①　木造３階建てとするに当たり、構造計画上工夫した点',
     '１階から３階まで柱の位置をすべてそろえ、直下率を高めた。'
     'Ａ・Ｂ・Ｃ・Ｄ通りと１・２・３・４通りの交点に計16本の柱を各階共通で'
     '配置し、建築物の四隅は120mm角の通し柱、その他は105mm角の管柱としている。'
     '梁の最大スパンは3,640mmに抑え、床は構造用合板t=24を梁に直接張った'
     '剛床として、地震力及び風圧力を耐力壁へ確実に伝達させている。'
     '耐力壁は筋かい45×90のたすき掛け及び構造用合板t=9を用い、'
     '桁行方向・梁間方向のいずれにも偏りなく配置した。'),
    ('②　店舗部分と住宅部分の動線計画について工夫した点',
     '店舗の出入口は南面の道路側に設け、来店客は店舗売場から'
     '店舗用便所へ至る動線とした。店舗用便所は売場の一部を区画して設け、'
     '厨房を通らずに利用できるようにしている。住宅の玄関は同じ南面の西端に'
     '別に設け、玄関を入ってすぐ階段へ上がれる配置とした。'
     'これにより住まい手が売場を通らずに２階・３階へ行くことができ、'
     '営業時間中も両者の動線が交錯しない。'
     '商品及び材料の搬入は北面の勝手口から厨房・倉庫へ直接行える。'),
    ('③　防火及び避難について配慮した点',
     '準防火地域に建つ延べ面積198.72m2・地上３階の木造であるため、'
     '45分準耐火建築物とした。外壁は屋内側から強化石膏ボードt=15、'
     '柱105（グラスウール16K t=100充填）、構造用合板t=9、透湿防水シート、'
     '通気胴縁t=18、窯業系サイディングt=16の構成とし、軒裏はケイ酸'
     'カルシウム板としている。３階に居室を有するため、階段室を準耐火構造の'
     '床及び壁で囲み、階段室に面する開口部を防火設備として竪穴区画とした。'
     '各居室から階段までの歩行距離を短くし、避難経路を単純にしている。'),
]

FIGS = [
    ('⑴ １階平面図兼配置図（1/100）', 'ansA_1f'),
    ('⑵ ２階平面図（1/100）', 'plan2f'),
    ('⑶ ３階平面図（1/100）', 'plan3f'),
    ('⑷ 床伏図（1/100）', 'framing_floor'),
    ('⑷ 小屋伏図（1/100）', 'framing_roof'),
    ('⑸ 南側立面図（1/100）', 'elevation_s'),
    ('⑹ 部分詳細図（断面）（1/20）', 'detail'),
]


def kaitou():
    o = ['<title>予想問題A 標準解答例</title>', CSS, '<div class="sheet">']
    o.append('<div style="text-align:center;margin-bottom:14px">'
             '<span class="stamp">標 準 解 答 例</span></div>')
    o.append('<div class="warn">これは予想問題Aに対する解答例です。'
             '公表されている本物の標準解答例ではありません。'
             '解答は１つではなく、設計条件を満たしていれば他の答えもあります。'
             '</div>')
    o.append('<div class="kadai">設計課題　「商店街に建つ併用住宅'
             '（木造３階建て）」</div>')

    o.append('<h2 class="sec">⑺　面積表</h2><table>')
    for a, b, c in AREA_ROWS:
        o.append('<tr><td class="rm">%s</td><td>%s</td>'
                 '<td class="n" style="width:78px">%s m<sup>2</sup></td></tr>'
                 % (a, b, c))
    o.append('</table>')
    o.append('<p style="font-size:10.5px">※ 面積の数値は、小数点以下第２位'
             'までとし、第３位以下は切り捨てている。'
             '7.28 × 9.10 ＝ 66.248 → <b>66.24</b>。'
             '延べ面積は各階の床面積の合計 66.24 × 3 ＝ <b>198.72</b>。</p>')
    o.append('<div class="warn">条件の確認　'
             '延べ面積 198.72m<sup>2</sup>（180〜200 ○）／'
             '建蔽率 66.24 ÷ 180 ＝ 36.8%（限度80% ○）／'
             '容積率の限度は 前面道路6m × 6/10 ＝ 360% と 都市計画300% の'
             '小さいほうで300%、198.72 ÷ 180 ＝ 110.4%（○）</div>')

    o.append('<h2 class="sec">⑻　計画の要点等</h2>')
    for q, a in YOUTEN:
        o.append('<div class="ansbox"><p class="q">%s</p>'
                 '<p class="a">%s</p></div>' % (q, a))

    for title, fig in FIGS:
        o.append('<h2 class="sec brk">%s</h2>' % title)
        o.append('<div class="fig">%s</div>' % inline_svg(fig))
    o.append('</div>')
    return ''.join(o)


if __name__ == '__main__':
    io.open(os.path.join(BASE, 'mondai.html'), 'w',
            encoding='utf-8').write(mondai())
    io.open(os.path.join(BASE, 'kaitou.html'), 'w',
            encoding='utf-8').write(kaitou())
    print('wrote mondai.html / kaitou.html')
