# -*- coding: utf-8 -*-
"""公式の様式にならった問題用紙と標準解答例を6セットつくる。

建築技術教育普及センターが公開している過去問（令和5年・令和7年）の
問題用紙と標準解答例の章立て・文言・表の構成を写し、
令和8年の課題「商店街に建つ併用住宅（木造3階建て）」に置きかえたもの。
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_onepage import inline_svg          # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN = "'Zen Old Mincho','Hiragino Mincho ProN','Yu Mincho','MS Mincho',serif"
GO = "'Hiragino Sans','Noto Sans JP','Yu Gothic',Meiryo,'IPAGothic',sans-serif"

CSS = """<style>
@page{size:A4;margin:14mm 13mm}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:GOFONT;font-size:11.5px;line-height:1.75;color:#000;
  background:#fff}
.sheet{max-width:186mm;margin:0 auto}
.note0{border:1px solid #000;padding:7px 9px;font-size:10.5px;line-height:1.6;
  margin-bottom:12px}
.kadai{text-align:center;font-family:MINFONT;font-size:16px;font-weight:700;
  letter-spacing:.06em;margin:14px 0 16px;padding:7px 0;
  border-top:2px solid #000;border-bottom:2px solid #000}
.kadai small{display:block;font-family:GOFONT;font-size:11px;font-weight:400;
  letter-spacing:0;margin-top:4px;color:#444}
h2.sec{font-family:MINFONT;font-size:14px;font-weight:700;margin:18px 0 6px}
h3.sub{font-size:12px;font-weight:700;margin:12px 0 4px}
p{margin:5px 0}
.ind{margin-left:1.1em}
ol.jp{list-style:none;counter-reset:jp;margin:4px 0 4px 1.7em}
ol.jp>li{counter-increment:jp;position:relative;margin:3px 0}
ol.jp>li::before{content:counter(jp,katakana)"．";position:absolute;
  left:-1.8em}
ul.dot{list-style:none;margin:3px 0 3px 1em}
ul.dot>li{position:relative;margin:2px 0}
ul.dot>li::before{content:"・";position:absolute;left:-1em}
table{border-collapse:collapse;width:100%;font-size:10.5px;margin:7px 0;
  line-height:1.6}
th,td{border:1px solid #000;padding:4px 6px;vertical-align:top}
th{background:#f0f0f0;font-weight:700;text-align:center}
td.c{text-align:center;vertical-align:middle;width:32px;font-weight:700}
td.rm{width:100px;font-weight:700}
td.n{text-align:right;font-family:GOFONT;width:80px}
.fig{text-align:center;margin:14px 0}
.fig svg{max-width:100%;height:auto;max-height:210mm}
.brk{break-before:page}
.stamp{border:2px solid #000;display:inline-block;padding:5px 22px;
  font-family:MINFONT;font-size:15px;font-weight:700;letter-spacing:.2em}
.ansbox{border:1px solid #000;padding:9px 11px;margin:9px 0;
  break-inside:avoid}
.ansbox .q{font-weight:700;margin-bottom:5px}
.ansbox .a{font-size:11px;line-height:1.9}
.warn{border:1px solid #999;background:#f7f7f7;padding:8px 10px;
  font-size:10.5px;margin:11px 0}
</style>""".replace('GOFONT', GO).replace('MINFONT', MIN)

# ---------------- 要求室 ----------------
R_SHOP = [
    ('店舗売場', 'ア．25m<sup>2</sup>以上とする。<br>'
     'イ．道路に面して出入口を設ける。<br>'
     'ウ．陳列棚及びレジカウンターを設ける。'),
    ('厨房・作業場', 'ア．9m<sup>2</sup>以上とする。<br>'
     'イ．店舗売場に隣接させ、直接行き来できるようにする。<br>'
     'ウ．流し台、調理台、作業台及びオーブンを設ける。'),
    ('スタッフルーム', 'ア．6m<sup>2</sup>以上とする。<br>'
     'イ．従業員の更衣及び休憩に使用する。'),
    ('店舗用便所', 'ア．来客が利用できるものとする。<br>'
     'イ．洋式便器及び手洗い器を設ける。'),
    ('倉　庫', '・商品及び材料を保管する。'),
    ('玄　関', 'ア．住宅部分の玄関とし、道路から直接出入りできるものとする。'
     '<br>イ．下足入れを設ける。'),
]
R_2F = [
    ('居間・食事室・台所', 'ア．１室にまとめ、25m<sup>2</sup>以上として'
     '計画する。<br>イ．ソファー、テーブル及び椅子（計４席以上）を設ける。'
     '<br>ウ．台所設備機器（流し台・調理台・コンロ台・冷蔵庫等）を設ける。'),
    ('和　室', 'ア．６畳以上とする。<br>'
     'イ．居間に隣接させ、直接行き来できるようにする。<br>'
     'ウ．押入れを設ける。'),
    ('浴室・洗面脱衣室',
     '・浴室には浴槽、洗面脱衣室には洗面台及び洗濯機を設ける。'),
    ('便　所', '・洋式便器を設ける。'),
    ('家事室', '・納戸を兼ねてもよい。'),
]
R_3F = [
    ('夫婦寝室', 'ア．13m<sup>2</sup>以上とする。<br>'
     'イ．洋室とし、ベッド（計２台）及び収納を設ける。'),
    ('子ども室', 'ア．２室（各8m<sup>2</sup>以上）設け、いずれも同じ広さと'
     'する。<br>イ．いずれも洋室とし、ベッド、机及び収納を設ける。'),
    ('便　所', '・洋式便器を設ける。'),
    ('納　戸', ''),
]
R_SHOP_B = [r for r in R_SHOP if r[0] != 'スタッフルーム'] + [
    ('和　室<br>（母の寝室）',
     'ア．６畳以上とする。<br>'
     'イ．母が階段を使わずに生活できるようにする。<br>'
     'ウ．押入れを設ける。'),
]

ZUSHO = [
    ('⑴ １階平面図兼配置図<br>（１/100）<br><br>⑵ ２階平面図<br>（１/100）'
     '<br><br>⑶ ３階平面図<br>（１/100）',
     'ア．１階平面図兼配置図、２階平面図及び３階平面図には、次のものを'
     '記入する。<ul class="dot"><li>建築物の主要な寸法</li><li>室名等</li>'
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
     'ウ．２階平面図には、次のものを記入する。<ul class="dot">'
     '<li>居間・食事室・台所…ソファー、テーブル、椅子及び台所設備機器</li>'
     '<li>和室…畳及び押入れ</li>'
     '<li>浴室…浴槽／洗面脱衣室…洗面台及び洗濯機／便所…洋式便器</li></ul>'
     'エ．３階平面図には、次のものを記入する。<ul class="dot">'
     '<li>夫婦寝室…ベッド及び収納</li>'
     '<li>子ども室…ベッド、机及び収納</li>'
     '<li>便所…洋式便器</li></ul>'),
    ('⑷ 床伏図兼小屋伏図<br>（１/100）',
     'ア．３階床伏図兼小屋伏図とする。<br>'
     'イ．主要部材（通し柱、各階の管柱、胴差、床梁、桁、小屋梁、火打梁、'
     '棟木、母屋、小屋束等必要なもの）については、凡例の表示記号に'
     'したがって記入し、断面寸法（小屋束を除く。）を凡例欄に記入する。<br>'
     'ウ．火打梁の代わりに構造用面材による床組とする場合には、胴差、床梁、'
     '桁を記入したうえで、構造用合板の厚さ、釘の種類・打ち付け間隔を'
     '明記する。<br>エ．建築物の主要な寸法を記入する。'),
    ('⑸ 立面図<br>（１/100）',
     'ア．南側立面図とする。<br>イ．建築物の最高の高さを記入する。'),
    ('⑹ 部分詳細図（断面）<br>（１/20）',
     'ア．切断位置は、外壁を含む部分とし、開口部を含むものとする。<br>'
     'イ．作図の範囲は、基礎から２階の床までとする。<br>'
     'ウ．主要部の寸法等（床高、天井高、階高、基礎の寸法等）を記入する。<br>'
     'エ．主要部材（基礎、土台、柱、胴差、床梁等必要なもの）の名称・'
     '断面寸法を記入する。<br>オ．アンカーボルト等の名称・寸法を'
     '記入する。<br>カ．外壁、床、その他必要と思われる部分の断熱・防湿措置'
     'を記入する。<br>キ．内外の主要な部位（外壁、床、内壁、天井）の'
     '仕上材料名を記入する。'),
    ('⑺ 面積表',
     'ア．建築面積、床面積及び延べ面積を記入する。<br>'
     'イ．建築面積及び床面積については、計算式も記入する。<br>'
     'ウ．面積の数値は、小数点以下第２位までとし、第３位以下は切り捨てる。'),
]


def rooms_std(shop=None):
    return [('１階', shop or R_SHOP), ('２階', R_2F), ('３階', R_3F)]


AREA_STD = ('7.28 × 9.10', '66.24', '198.72')
AREA_B = ('8.19 × 9.10', '74.52', '223.56')
AREA_C = ('6.37 × 10.01', '63.76', '191.28')

Y_KOZO = ('木造３階建てとするに当たり、構造計画上工夫した点',
          # ①なにをした →②数字 →③なぜ →④どうなる の順に並べた見本。
          '１階から３階まで柱の位置をすべてそろえ、通り芯の交点に各階'
          '共通で配置した。建築物の四隅には120mm角の通し柱、その他には'
          '同寸の管柱を用い、梁の最大スパンは3,640mm以下としている。'
          '床は構造用合板t=24を梁に直接張った剛床とし、耐力壁は筋かい'
          '45×90のたすき掛け及び構造用合板t=9を、桁行方向・梁間方向の'
          'いずれにも偏りなく配置した。木造３階建ては上階からの鉛直力'
          '及び水平力が大きくなるため、力の流れを上下階でそろえる必要が'
          'あるからである。これにより直下率が高くなり、地震力及び風圧力'
          'を剛床を介して耐力壁へ確実に伝達させることができる。')


def y_bouka(nobe):
    return ('防火及び避難について配慮した点',
            '準防火地域に建つ延べ面積%sm<sup>2</sup>・地上３階の木造で'
            'あるため、45分準耐火建築物とした。外壁は屋内側から強化石膏'
            'ボードt=15、柱120（グラスウール16K t=100充填）、構造用合板'
            't=9、透湿防水シート、通気胴縁t=18、窯業系サイディングt=16の'
            '構成とし、軒裏はケイ酸カルシウム板としている。３階に居室を'
            '有するため、階段室を準耐火構造の床及び壁で囲み、階段室に'
            '面する開口部を防火設備として竪穴区画とした。各居室から階段'
            'までの歩行距離を短くし、避難経路を単純にしている。' % nobe)


Y_DOUSEN = ('店舗部分と住宅部分の動線計画について工夫した点',
            '店舗の出入口は道路に面して設け、来店客は店舗売場から店舗用'
            '便所へ至る動線とした。店舗用便所は売場の一部を区画して設け、'
            '厨房を通らずに利用できるようにしている。住宅の玄関は店舗の'
            '出入口と壁をへだてて別に設け、幅910mm（有効約780mm）の廊下で'
            'すぐ階段へ上がれる配置とした。これにより住まい手が売場を'
            '通らずに２階・３階へ行くことができ、営業時間中も両者の動線が'
            '交錯しない。商品及び材料の搬入は建築物背面の勝手口から'
            '厨房・倉庫へ直接行える。')

SPECS = [
 dict(tag='A', name='南側道路（本命）',
      lead='ある地方都市の商店街において、パン屋を営む夫婦とその子ども'
           '２人が住むための併用住宅を計画する。',
      points=['店舗部分と住宅部分の動線が交錯しないようにする。',
              '木造３階建てであることを踏まえ、構造上のバランスに'
              '配慮する。', '防火及び避難に配慮する。'],
      ken='80', you='300', nobe='180m<sup>2</sup>以上、200m<sup>2</sup>以下',
      rooms=rooms_std(), area=AREA_STD, site_area='180.00',
      check='延べ面積 198.72m<sup>2</sup>（180〜200 ○）／建蔽率 66.24 ÷ 180 '
            '＝ 36.8%（限度80% ○）／容積率の限度は 前面道路8m × 6/10 ＝ '
            '480% と 都市計画300% の小さいほうで300%、198.72 ÷ 180 ＝ '
            '110.4%（○）',
      youten=[Y_KOZO, Y_DOUSEN, y_bouka('198.72')],
      figs=[('⑴ １階平面図兼配置図（1/100）', 'ansA_1f'),
            ('⑵ ２階平面図（1/100）', 'plan2f'),
            ('⑶ ３階平面図（1/100）', 'plan3f'),
            ('⑷ 床伏図兼小屋伏図（1/100）　その1　床伏図', 'framing_floor'),
            ('⑷ 床伏図兼小屋伏図（1/100）　その2　小屋伏図', 'framing_roof'),
            ('⑸ 南側立面図（1/100）', 'elevation_s'),
            ('⑹ 部分詳細図（断面）（1/20）', 'detail')]),

 dict(tag='B', name='１階に母の寝室',
      lead='ある地方都市の商店街において、パン屋を営む夫婦とその子ども'
           '２人、及び夫の母（70歳代）が住むための併用住宅を計画する。',
      points=['母が階段を使わずに生活できるようにする。',
              '店舗部分と住宅部分の動線が交錯しないようにする。',
              '高齢者の避難に配慮する。'],
      ken='80', you='300', nobe='200m<sup>2</sup>以上、230m<sup>2</sup>以下',
      rooms=rooms_std(R_SHOP_B), area=AREA_B, site_area='224.00',
      check='延べ面積 223.56m<sup>2</sup>（200〜230 ○）／建蔽率 74.52 ÷ 224 '
            '＝ 33.3%（限度80% ○）／容積率の限度は 前面道路6m × 6/10 ＝ '
            '360% と 300% の小さいほうで300%、223.56 ÷ 224 ＝ 99.8%（○）',
      youten=[
        ('高齢者の居室を１階に設けたことについて工夫した点',
         '母の寝室である和室６畳を１階の北西に配置し、階段を使わずに生活'
         'できるようにした。住宅玄関から寝室までは幅910mm（有効約780mm）の廊下１本で'
         'つながり、途中に段差を設けていない。寝室のすぐ南に階段室がある'
         'ため、２階・３階の家族がすぐに様子を見に行ける。廊下及び出入口'
         'の有効幅は780mm以上とし、将来手すりを取り付けられるよう壁に'
         '下地を入れている。'),
        Y_DOUSEN,
        ('高齢者の避難について配慮した点',
         '母の寝室を１階に置いたことで、火災時に階段を使わずに屋外へ避難'
         'できる。寝室は西面及び北面の２方向に窓を持ち、逃げ道が１方向に'
         'かたよらないようにした。廊下から玄関までの避難経路は幅910mm'
         '（有効約780mm）の直線で、途中に段差や狭くなる部分がない。'
         '階段室は準耐火構造の床及び壁で囲んだ竪穴区画としているため、'
         '上階からの煙が１階の廊下へ流れ込みにくく、高齢者でも落ち着いて'
         '屋外へ出られる。なお延べ面積が200m<sup>2</sup>を超えるため、'
         '竪穴区画の緩和（令112条11項ただし書）は用いていない。')],
      figs=[('⑴ １階平面図兼配置図（1/100）', 'ansB_1f'),
            ('⑵ ２階平面図（1/100）', 'ansB_2f'),
            ('⑶ ３階平面図（1/100）', 'ansB_3f')]),

 dict(tag='C', name='間口の狭い敷地',
      lead='ある地方都市の商店街において、パン屋を営む夫婦とその子ども'
           '２人が住むための併用住宅を計画する。',
      points=['間口が狭い敷地であることを踏まえた平面計画とする。',
              '奥行きの深い店舗売場の採光及び通風に配慮する。',
              '店舗部分と住宅部分の動線が交錯しないようにする。'],
      ken='80', you='300', nobe='180m<sup>2</sup>以上、200m<sup>2</sup>以下',
      rooms=rooms_std(), area=AREA_C, site_area='180.00',
      check='延べ面積 191.28m<sup>2</sup>（180〜200 ○）／建蔽率 63.76 ÷ 180 '
            '＝ 35.4%（限度80% ○）／容積率の限度は 前面道路6m × 6/10 ＝ '
            '360% と 300% の小さいほうで300%、191.28 ÷ 180 ＝ 106.3%（○）',
      youten=[
        ('間口が狭い敷地に対して、平面計画上工夫した点',
         '間口9,000mmに対し建築物の間口を6,370mm（910mm×７マス）とし、'
         '東西の隣地境界線から外壁面まで1,315mmずつを確保した。不足する'
         '床面積は奥行き方向で確保することとし、奥行を10,010mm'
         '（910mm×11マス）としている。910mmのモジュールは崩さず、マスの'
         '数だけを組みかえたため、階段の位置や西側の水まわりの配置は'
         '変えずに済んでいる。'),
        ('奥行きの深い店舗売場の採光及び通風について工夫した点',
         '店舗売場は間口4,550mm・奥行6,370mmと奥に深くなるため、南面の'
         '道路側に幅2,730mmの出入口及び開口部を設けたうえで、東面にも'
         '高さのある窓を連続して設け、奥まで光が届くようにした。北面には'
         '勝手口を設け、南面の開口部との間で南北に風が抜ける経路を確保'
         'している。天井高を2,700mmとし、高い位置に窓を設けることで'
         '奥への採光を助けている。'),
        ('木造３階建てとするに当たり、構造計画上工夫した点',
         '間口方向のスパンは1,820／2,730／1,820、奥行方向は1,820／3,640／'
         '2,730／1,820に区切り、いずれも3,640mm以下に抑えた。奥行が長く'
         'なるため東西方向の通りを５本とし、柱を各階同じ位置に20本配置'
         'して直下率を高めている。建築物の四隅は120mm角の通し柱、その他は'
         '120mm角の管柱とした。床は構造用合板t=24を梁に直接張った剛床と'
         'し、水平力を耐力壁へ伝達させている。')],
      figs=[('⑴ １階平面図兼配置図（1/100）', 'ansC_1f'),
            ('⑵ ２階平面図（1/100）', 'ansC_2f'),
            ('⑶ ３階平面図（1/100）', 'ansC_3f')]),

 dict(tag='D', name='東側道路',
      lead='ある地方都市の商店街において、パン屋を営む夫婦とその子ども'
           '２人が住むための併用住宅を計画する。',
      points=['店舗の出入口及び住宅の玄関は、東側の道路から出入りできる'
              'ものとする。',
              '店舗部分と住宅部分の動線が交錯しないようにする。',
              '木造３階建てであることを踏まえ、構造上のバランスに'
              '配慮する。'],
      ken='80', you='300', nobe='180m<sup>2</sup>以上、200m<sup>2</sup>以下',
      rooms=rooms_std(), area=AREA_STD, site_area='180.00',
      check='延べ面積 198.72m<sup>2</sup>（180〜200 ○）／建蔽率 66.24 ÷ 180 '
            '＝ 36.8%（限度80% ○）／容積率の限度は 前面道路6m × 6/10 ＝ '
            '360% と 300% の小さいほうで300%、198.72 ÷ 180 ＝ 110.4%（○）',
      youten=[
        ('東側道路に対して、平面計画上工夫した点',
         '店舗売場を建築物の東側に配置し、道路に面する東面に出入口と'
         '大きな開口部を設けて、通りから店内が見えるようにした。'
         '住宅の玄関は同じ東面の南端に別に設け、来店客と住まい手の出入口'
         'を分けている。厨房・倉庫は道路から見えない西側にまとめ、'
         '北面の勝手口から搬入できるようにした。梁の最大スパンは'
         '3,640mmに抑え、柱の位置は各階共通としている。'),
        ('階段の位置と直下率について工夫した点',
         '東面は店舗売場と住宅玄関で使い切るため、階段は玄関の西どなり'
         '（建築物の南中央）に配置した。この位置を１階から３階まで変えず、'
         '２階・３階の平面も同じ階段位置を前提に組み立てている。柱は'
         'Ａ・Ｂ・Ｃ・Ｄ通りと１・２・３・４通りの交点に各階共通で16本'
         '配置し、直下率を高めた。梁の最大スパンは3,640mmに抑えている。'),
        Y_DOUSEN],
      figs=[('⑴ １階平面図兼配置図（1/100）', 'ansD_1f'),
            ('⑵ ２階平面図（1/100）', 'ansD_2f'),
            ('⑶ ３階平面図（1/100）', 'ansD_3f')]),

 dict(tag='E', name='南東の角地',
      lead='ある地方都市の商店街において、パン屋を営む夫婦とその子ども'
           '２人が住むための併用住宅を計画する。',
      points=['角地であることを活かした計画とする。',
              '店舗部分と住宅部分の動線が交錯しないようにする。',
              '防火及び避難に配慮する。'],
      ken='90', you='300', nobe='180m<sup>2</sup>以上、200m<sup>2</sup>以下',
      ken_note='（特定行政庁が指定した角地における加算を含む。）',
      rooms=rooms_std(), area=AREA_STD, site_area='182.00',
      check='延べ面積 198.72m<sup>2</sup>（180〜200 ○）／建蔽率 66.24 ÷ 182 '
            '＝ 36.4%（限度90% ○）／容積率の限度は <b>幅の広い南側道路8m</b>'
            ' × 6/10 ＝ 480% と 300% の小さいほうで300%、198.72 ÷ 182 ＝ '
            '109.2%（○）',
      youten=[
        ('角地であることを活かして工夫した点',
         '店舗の出入口を、幅8mの南側道路と幅6mの東側道路が交わる南東の'
         '角に向けて設け、どちらの通りからも入りやすくした。店舗売場は'
         '南面と東面の２方向に開口部を持つため、自然光が奥まで入り、'
         '通りからも店内の様子が見える。住宅の玄関は南面の西端に、店舗の'
         '出入口と壁をへだてて設けた。これにより角地の２面を店舗の顔と'
         'して使いながら、来店客と住まい手の出入りが重ならない。'),
        ('容積率及び建蔽率の算定について',
         '前面道路が２つあるため、容積率の限度の算定には幅の広い南側道路'
         '8mを用い、8 × 6/10 ＝ 480% と都市計画の300% を比べて小さいほうの'
         '300% とした。実際の容積率は 198.72 ÷ 182 ＝ 109.2% である。'
         '建蔽率は特定行政庁が指定した角地における加算を含めて90% が限度'
         'であるが、本計画は36.4% であり余裕がある。'),
        y_bouka('198.72')],
      figs=[('⑴ １階平面図兼配置図（1/100）', 'ansE_1f'),
            ('⑵ ２階平面図（1/100）', 'plan2f'),
            ('⑶ ３階平面図（1/100）', 'plan3f')]),

 dict(tag='F', name='北側道路',
      lead='ある地方都市の商店街において、パン屋を営む夫婦とその子ども'
           '２人が住むための併用住宅を計画する。',
      points=['店舗の出入口及び住宅の玄関は、北側の道路から出入りできる'
              'ものとする。',
              '住宅部分の居室の日照に配慮する。',
              '防火及び避難に配慮する。'],
      ken='80', you='300', nobe='180m<sup>2</sup>以上、200m<sup>2</sup>以下',
      rooms=rooms_std(), area=AREA_STD, site_area='180.00',
      check='延べ面積 198.72m<sup>2</sup>（180〜200 ○）／建蔽率 66.24 ÷ 180 '
            '＝ 36.8%（限度80% ○）／容積率の限度は 前面道路6m × 6/10 ＝ '
            '360% と 300% の小さいほうで300%、198.72 ÷ 180 ＝ 110.4%（○）',
      youten=[
        ('北側道路に対して、住宅部分の日照をどのように確保したか',
         '店舗は道路に面する必要があるため１階の北側に店舗売場を配置し、'
         '厨房・スタッフルームなど日照を必要としない諸室を南側にまとめた。'
         '一方、住宅部分は２階・３階に配置し、居間・食事室・台所及び'
         '子ども室はいずれも南面に開口部を設けて日照を確保している。'
         '住宅の玄関は北西に設け、幅910mm（有効約780mm）の廊下１本で'
         '階段に達する動線とした。これにより、店舗は北の通りに面しながら、'
         '住宅の主要な居室はすべて南からの日照を受けられる。'),
        ('階段の位置について工夫した点',
         '１階のみ南北の配置を入れかえ、階段の位置は１階から３階まで'
         '変えていない。これにより２階・３階は南面に居室を並べた計画を'
         'そのまま採用でき、柱の位置も各階共通の16本となって直下率を'
         '高く保っている。なお店舗売場の中には通り芯上の柱が１本現れる'
         'が、梁のスパンを3,640mm以下に抑えるために必要なものである。'),
        y_bouka('198.72')],
      figs=[('⑴ １階平面図兼配置図（1/100）', 'ansF_1f'),
            ('⑵ ２階平面図（1/100）', 'plan2f'),
            ('⑶ ３階平面図（1/100）', 'plan3f')]),
]


HEAD_NOTE = (
    '<div class="note0">〔注意事項〕試験問題を十分に読んだうえで、'
    '「設計製図の試験」に臨むようにしてください。なお、建築基準法等の関係'
    '法令や要求図書、主要な要求室等の計画等の設計与条件に対して解答内容が'
    '不十分な場合には、「設計条件・要求図書に対する重大な不適合」と判断'
    'されます。</div>')


A2CSS = """<style>
@page{size:594mm 420mm;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:GOFONT;color:#000;background:#fff;font-size:10.2px;
  line-height:1.55}
.a2{width:594mm;height:420mm;display:flex;overflow:hidden;
  border:1.2px solid #000}
.tate{width:15mm;border-right:1px solid #000;padding:10mm 0 0;
  text-align:center;font-family:MINFONT;font-size:13px;font-weight:700}
.tate i{display:block;font-style:normal;line-height:1.28}
.tate i.sp{height:4mm}
.main{flex:1;display:flex;min-width:0}
.left{width:378mm;padding:5mm 5mm 4mm;display:flex;flex-direction:column;
  min-width:0}
.kadai{text-align:center;font-family:MINFONT;font-size:15px;font-weight:700;
  letter-spacing:.1em;margin-bottom:3mm}
.kadai small{display:block;font-family:GOFONT;font-size:9.5px;font-weight:400;
  letter-spacing:0;margin-top:1mm;color:#333}
.two{flex:1;display:flex;gap:5mm;min-height:0}
.col{flex:1;min-width:0;overflow:hidden}
.draft{width:200mm;border-left:1px solid #000;padding:4mm;display:flex;
  flex-direction:column}
.atten{border:1px solid #000;padding:2mm 2.5mm;font-size:8.6px;
  line-height:1.5;margin-bottom:2mm}
.dhead{font-family:MINFONT;font-size:13px;font-weight:700;letter-spacing:.5em;
  margin-bottom:1.5mm}
.dhead small{font-family:GOFONT;font-size:9px;font-weight:400;
  letter-spacing:0;margin-left:6mm}
.grid{flex:1;border:1px solid #000;
  background-image:linear-gradient(#dcdcdc 1px,transparent 1px),
    linear-gradient(90deg,#dcdcdc 1px,transparent 1px);
  background-size:4.55mm 4.55mm}
h2.sec{font-family:MINFONT;font-size:12.5px;font-weight:700;margin:0 0 1.5mm}
h3.sub{font-size:10.4px;font-weight:700;margin:2mm 0 1mm}
p{margin:1mm 0}
.ind{margin-left:1em}
ol.jp{list-style:none;counter-reset:jp;margin:1mm 0 1mm 1.6em}
ol.jp>li{counter-increment:jp;position:relative;margin:.6mm 0}
ol.jp>li::before{content:counter(jp,katakana)"．";position:absolute;left:-1.7em}
ul.dot{list-style:none;margin:1mm 0 1mm 1em}
ul.dot>li{position:relative;margin:.5mm 0}
ul.dot>li::before{content:"・";position:absolute;left:-1em}
table{border-collapse:collapse;width:100%;font-size:9.2px;margin:1.5mm 0;
  line-height:1.45}
th,td{border:.8px solid #000;padding:1mm 1.2mm;vertical-align:top}
th{background:#f2f2f2;font-weight:700;text-align:center}
td.c{text-align:center;vertical-align:middle;width:9mm;font-weight:700}
td.rm{width:22mm;font-weight:700}
.fig{text-align:center;margin-top:2mm}
.fig svg{max-width:100%;height:auto;max-height:96mm}
.small{font-size:8.6px;color:#333}
sup{font-size:.7em;vertical-align:super}
</style>""".replace('GOFONT', GO).replace('MINFONT', MIN)


def kadai(sp, sub):
    return ('<div class="kadai">設計課題　「商店街に建つ併用住宅'
            '（木造３階建て）」<small>%s　予想問題%s　%s</small></div>'
            % (sub, sp['tag'], sp['name']))


def tategaki(t):
    """1文字ずつ縦に積んで、確実に縦書きにする。／は空きを表す。"""
    return ''.join('<i class="sp"></i>' if c == '／' else '<i>%s</i>' % c
                   for c in t)


def mondai(sp):
    """本物と同じ A2横1枚の問題用紙。左＝設計条件、中＝要求図書、右＝下書欄。"""
    L, M = [], []

    L.append('<h2 class="sec">1．設計条件</h2>')
    L.append('<p class="ind">%s</p>' % sp['lead'])
    L.append('<p class="ind">計画に当たっては、次の①〜③に特に留意する。</p>')
    L.append('<ul class="dot" style="margin-left:1.6em">%s</ul>'
             % ''.join('<li>%s　%s</li>' % ('①②③'[i], t)
                       for i, t in enumerate(sp['points'])))
    L.append('<h3 class="sub">⑴　敷　地</h3><ol class="jp">'
             '<li>形状、道路との関係、方位等は、下に示す敷地図のとおりで'
             'ある。</li>'
             '<li>近隣商業地域内にあり、準防火地域に指定されている。</li>'
             '<li>建蔽率の限度は%s％%s、容積率の限度は%s％である。</li>'
             '<li>地形は平坦で、道路及び隣地との高低差はなく、地盤は良好で'
             'ある。</li>'
             '<li>電気、都市ガス、上水道及び公共下水道は完備している。</li>'
             '</ol>' % (sp['ken'], sp.get('ken_note', ''), sp['you']))
    L.append('<h3 class="sub">⑵　構造、階数、建築物の高さ等</h3>'
             '<ol class="jp"><li>木造３階建てとする。</li>'
             '<li>建築物の最高の高さは11m以下、かつ、軒の高さは9.5m以下と'
             'する。</li>'
             '<li>耐力壁（構造耐力上有効な壁）は、必要な量をバランスよく'
             '配置する。</li></ol>')
    L.append('<h3 class="sub">⑶　延べ面積等</h3><ol class="jp">'
             '<li>延べ面積は、「%s」とする。</li>'
             '<li>玄関ポーチ、バルコニー、駐輪スペース等は、床面積に'
             '算入しない。</li></ol>' % sp['nobe'])
    L.append('<h3 class="sub">⑷　人員構成等</h3><p class="ind">%s</p>'
             % sp.get('jinin', '夫婦（40歳代）、子ども２人（中学生、小学生）'))
    L.append('<h3 class="sub">⑸　要求室等</h3>'
             '<p class="ind">下表の全ての室等は、指定された設置階に'
             '計画する。</p><table><tr><th style="width:9mm">設置階</th>'
             '<th style="width:22mm">室　名　等</th>'
             '<th>特　記　事　項</th></tr>')
    for fl, lst in sp['rooms']:
        for i, (nm, memo) in enumerate(lst):
            span = ('<td class="c" rowspan="%d">%s</td>'
                    % (len(lst), fl.replace('階', '<br>階'))) if i == 0 else ''
            L.append('<tr>%s<td class="rm">%s</td><td>%s</td></tr>'
                     % (span, nm, memo))
    L.append('</table>')
    L.append('<p class="small">（注1）各要求室等においては、'
             '床面積・広さの指定がない場合、床面積は適宜とする。<br>'
             '（注2）階段は、安全を確保するために、踊場を設ける。</p>')
    L.append('<h3 class="sub">⑹　屋外施設等</h3>'
             '<p class="ind">屋外に下表のものを計画する。</p><table>'
             '<tr><td class="rm">駐輪スペース</td>'
             '<td>・４台分を設ける。</td></tr>'
             '<tr><td class="rm">門・塀・植栽等</td><td></td></tr></table>')
    L.append('<div class="fig">%s</div>' % inline_svg('site_' + sp['tag']))

    M.append('<h2 class="sec">2．要求図書</h2>')
    M.append('<ul class="dot" style="margin-left:1.1em">'
             '<li>ａ．答案用紙の定められた枠内に、下表の要求図書を記入する。'
             '（寸法線は、枠外にはみだして記入してもよい。）</li>'
             '<li>ｂ．図面は黒鉛筆仕上げとする。（定規を用いなくてもよい。）'
             '</li><li>ｃ．記入寸法の単位は、mmとする。なお、答案用紙の'
             '１目盛は、4.55mm（部分詳細図にあっては、10mm）である。</li>'
             '<li>ｄ．シックハウス対策のための機械換気設備等は、記入しなくて'
             'よい。</li></ul>')
    M.append('<table><tr><th style="width:26mm">要　求　図　書'
             '<br>（　）内は縮尺</th><th>特　記　事　項</th></tr>')
    for nm, memo in ZUSHO:
        M.append('<tr><td class="rm">%s</td><td>%s</td></tr>' % (nm, memo))
    M.append('<tr><td class="rm">⑻ 計画の要点等</td>'
             '<td>・建築物の計画に関する次の①〜③について、具体的に'
             '記述する。<ul class="dot">%s</ul></td></tr>'
             % ''.join('<li>%s　%s</li>' % ('①②③'[i], q)
                       for i, (q, _) in enumerate(sp['youten'])))
    M.append('</table>')
    M.append('<p class="small">※ この問題用紙は、公表されている過去問'
             '（令和4〜7年）の様式にならって作成した<b>予想問題</b>です。'
             '本物の試験問題ではありません。</p>')

    return ''.join([
        '<title>予想問題%s 問題用紙</title>' % sp['tag'], A2CSS,
        '<div class="a2"><div class="tate">' + tategaki(
            '令和8年二級建築士試験﹁設計製図の試験﹂／問題用紙')
        + '</div><div class="main"><div class="left">',
        kadai(sp, '問 題 用 紙'),
        '<div class="two"><div class="col">', ''.join(L),
        '</div><div class="col">', ''.join(M),
        '</div></div></div>',
        '<div class="draft">',
        '<div class="atten">〔注意事項〕試験問題を十分に読んだうえで、'
        '「設計製図の試験」に臨むようにしてください。なお、建築基準法等の'
        '関係法令や要求図書、主要な要求室等の計画等の設計与条件に対して'
        '解答内容が不十分な場合には、「設計条件・要求図書に対する重大な'
        '不適合」と判断されます。</div>',
        '<div class="dhead">下 書 欄<small>（目盛4.55mm）</small></div>',
        '<div class="grid"></div></div></div></div>'])


def kaitou(sp):
    calc, per, tot = sp['area']
    o = ['<title>予想問題%s 標準解答例</title>' % sp['tag'], CSS,
         '<div class="sheet">',
         '<div style="text-align:center;margin-bottom:12px">'
         '<span class="stamp">標 準 解 答 例</span></div>',
         '<div class="warn">これは予想問題%sに対する解答例です。'
         '公表されている本物の標準解答例ではありません。解答は１つでは'
         'なく、設計条件を満たしていれば他の答えもあります。</div>'
         % sp['tag'],
         kadai(sp, '標 準 解 答 例')]

    o.append('<h2 class="sec">⑺　面積表</h2><table>')
    rows = [('敷地面積', '', sp['site_area']),
            ('建築面積', '（計算式）　%s' % calc, per),
            ('床面積　１階', '（計算式）　%s' % calc, '① ' + per),
            ('　　　　２階', '（計算式）　%s' % calc, '② ' + per),
            ('　　　　３階', '（計算式）　%s' % calc, '③ ' + per),
            ('延べ面積', '①＋②＋③', tot)]
    for a, b, c in rows:
        o.append('<tr><td class="rm">%s</td><td>%s</td>'
                 '<td class="n">%s m<sup>2</sup></td></tr>' % (a, b, c))
    o.append('</table>')
    o.append('<p style="font-size:10.5px">※ 面積の数値は、小数点以下第２位'
             'までとし、第３位以下は切り捨てている。延べ面積は各階の床面積'
             'の合計（%s × 3 ＝ %s）。</p>' % (per, tot))
    o.append('<div class="warn">条件の確認　%s</div>' % sp['check'])

    o.append('<h2 class="sec">⑻　計画の要点等</h2>')
    o.append('<div class="warn">どの解答例にも、つぎの<b>4つの部品</b>が'
             '入っています。<b>①なにをしたか</b>／<b>②数字</b>'
             '（120mm角・3,640mm・t=24・有効780mmなど）／'
             '<b>③なぜそうしたか</b>／<b>④どうなるか</b>。'
             'とくに<b>①の構造の解答は、この4つをそのままの順に'
             'ならべた見本</b>にしてあります。文章を丸暗記せず、'
             'この4つと、分野ごとの「部品」だけを覚えてください。</div>')
    for i, (q, a) in enumerate(sp['youten']):
        o.append('<div class="ansbox"><p class="q">%s　%s</p>'
                 '<p class="a">%s</p></div>' % ('①②③'[i], q, a))
    if sp['tag'] != 'A':
        o.append('<div class="warn">床伏図兼小屋伏図・立面図・部分詳細図に'
                 'ついては、考え方は予想問題Ａの標準解答例と同じです。'
                 '建築物の大きさが変わる場合は、梁のスパンが3,640mmを'
                 '超えないように通りの数を増減してください。</div>')

    for title, fig in sp['figs']:
        o.append('<h2 class="sec brk">%s</h2>' % title)
        o.append('<div class="fig">%s</div>' % inline_svg(fig))
    o.append('</div>')
    return ''.join(o)


def combine(fn, title, css=None, mark='<div class="sheet">'):
    """6セットを1つのHTMLにまとめる。"""
    parts = ['<title>%s</title>' % title, css or CSS]
    for i, sp in enumerate(SPECS):
        html = fn(sp)
        body = html[html.index(mark):]
        if i:
            body = body.replace(
                mark, mark[:-1] + ' style="break-before:page">', 1)
        parts.append(body)
    return ''.join(parts)


if __name__ == '__main__':
    io.open(os.path.join(BASE, 'mondai_all.html'), 'w',
            encoding='utf-8').write(combine(mondai, '予想問題集 問題用紙',
                                            A2CSS, '<div class="a2">'))
    io.open(os.path.join(BASE, 'kaitou_all.html'), 'w',
            encoding='utf-8').write(combine(kaitou, '予想問題集 標準解答例'))
    for sp in SPECS:
        t = sp['tag']
        io.open(os.path.join(BASE, 'mondai_%s.html' % t), 'w',
                encoding='utf-8').write(mondai(sp))
        io.open(os.path.join(BASE, 'kaitou_%s.html' % t), 'w',
                encoding='utf-8').write(kaitou(sp))
    print('wrote mondai_A..F.html / kaitou_A..F.html')
