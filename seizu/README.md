# 二級建築士 設計製図 対策キット（令和8年度）

課題「商店街に建つ併用住宅（木造3階建て）」用の自習教材。
試験日 2026年9月13日。

## 使い方

`seizu/index.html` をブラウザで開く。以下がリンクされている。

| ファイル | 中身 |
|---|---|
| `index.html` | もくじ・試験の仕組み・5時間の流れ・ランクⅣの6項目 |
| `01-tools.html` | 製図道具の発注リスト、届いたら最初にやること |
| `02-katachi.html` | 型の図面集（平面・伏図・立面・部分詳細・階段・面積表） |
| `03-cards.html` | 記述の暗記カード20問（携帯用・localStorage保存） |
| `mondai_A.html` 〜 `mondai_F.html` | 予想問題A〜F 問題用紙（過去問の様式にならったもの） |
| `kaitou_A.html` 〜 `kaitou_F.html` | 予想問題A〜F 標準解答例 |
| `mondai_all.html` / `kaitou_all.html` | 6セットを1本にまとめたもの |
| `04-yosou.html` | 予想問題A〜H（かんたん版・記述の記入欄つき） |
| `onepage.html` | 全部入りの1枚ページ（携帯用）。`onepage.src.html` + `parts/` から生成 |
| `timetrial.xlsx` | タイムトライアル記録表 |
| `figures/*.svg` | 図面（スクリプトで生成） |
| `pdf/二級建築士_製図早見盤.pdf` | 全内容のPDF（75ページ） |
| `pdf/二級建築士_図面集.pdf` | 図面だけを1ページ1枚で（25ページ） |

## 図面の作り直し

図はすべて Python で SVG を生成している（matplotlib 不使用・依存なし）。
部屋の配置や寸法を変えたいときは各スクリプトの上部の定義を書き換えて再実行する。

```sh
cd seizu/scripts
python3 plans.py        # 平面図 1F/2F/3F
python3 framing.py      # 床伏図・小屋伏図
python3 elevation.py    # 南立面図・階段の割付図
python3 detail.py       # 部分詳細図 1/20
python3 esquisse.py     # エスキス手順図
python3 site.py         # 配置図
python3 variants.py     # 予想問題の解答例（1階平面図）
python3 timetrial.py    # 記録表 xlsx（openpyxl が必要）
python3 build_onepage.py # onepage.html を組み立てる
python3 sitemap.py      # 敷地図（公式様式・A〜Fの6種）
python3 mondai.py       # 問題用紙・標準解答例のHTML（A〜F・まとめ版）
python3 make_pdf.py     # pdf/ に4本のPDFを書き出す（Chromium を使用）
```

`scripts/svgkit.py` が共通の描画ライブラリ。
`scripts/render.sh <svg> <png> <w> <h>` で目視確認用の PNG を出せる（Chromium 使用）。

## この教材で採用した数値

- グリッド 910mm、間口 7,280（8マス）× 奥行 9,100（10マス）、各階 66.24㎡、延べ 198.72㎡
  （面積は公式の指定どおり小数点以下第3位を**切り捨て**。7.28×9.10＝66.248→66.24）
- 柱は全階共通16本（通し柱120角×4＝四隅、管柱105角×12）
- 階段は3階とも西側の同じ位置。**1階→2階は15段（蹴上206.7）、2階→3階は14段（蹴上207.1）**、踏面はいずれも210
- **1FL = GL+550**（基礎の立上りを地上300mm以上とるため）。軒高 9,350、最高 10,806
- 外壁 163mm＝強化石膏ボード15＋柱105（GW100）＋構造用合板9＋透湿防水シート＋通気胴縁18＋窯業系サイディング16

## 注意

型は各資格学校の予想にもとづく想定であり、正解は当日の問題文のみ。
法令の数値（階段・基礎・壁倍率など）は必ず最新の法令集・告示で確認すること。
特に木造の構造規定は2025年4月施行の改正がある。
