# 週末ルーチン設定手順（Ver.100=紙上運用が本線／旧・レース選定も残置）

## ★Ver.100 紙上運用ルーチン（2026-07-12〜の本線。こちらを登録推奨）
登録: claude.ai/code/routines → New routine
- 名前: `競馬・週末紙上運用(Ver.100)`
- cron: `3 9 * * 6,0`（土日 9:03 JST）
- リポジトリ: `horihorihorihorichiz/-`（環境のAllowed domainsは下記・旧手順のnetkeiba系と同じ）
- プロンプト（そのまま貼る）:
```
keiba/RULES.md §0(Ver.100体制)を読んでから、以下を順に実行:
1. cd keiba && python paper.py settle && python paper.py stats   # 前回分の精算と成績
2. python paper.py run <今日のYYYYMMDD>                          # 今日の全JRAレースを紙上運用
3. もし harvest_year.py の収穫が未完了(harvest_year.stateのdoneに20260705が無い)なら
   nohup python3 harvest_year.py >> harvest_year.log 2>&1 & で収穫を再開して先へ進む
4. 収穫完了済みなら月1回程度の再学習: python fit_score.py --l2 0.05 --write &&
   python fit_score.py --surface 芝 --l2 0.08 --write && python fit_score.py --surface ダ --l2 0.08 --write &&
   python fit.py --test <直近2週末の日付8桁カンマ区切り> --write
5. paper.py stats の結果と、GOになったレースの買い目(オッズ→払戻付き)をまとめmdにして SendUserFile で送る
6. 変更を commit & push（ブランチ claude/stoic-ride-p35k9n）
※実弾なし=紙上のみ。判定ライン: 精算150Rで回収90%超→少額実弾の相談／70%未満→設計見直し。
※認証情報は扱わない・netkeibaにログインしない・購入しない。
```

---

# （旧）毎週土日 自動レース選定 ── Routine（定期実行）設定手順

「毎週土日になったら自動でレースを選ぶ」を Claude Code の **Routines** で実現する。
ルーチンはクラウドで動くので PC を閉じていても週末に自動実行される。
**このスクリプト群が選定〜予想〜買い目(確認連絡)まで自動化済み。あとは下記を登録するだけ。**

> 安全ライン（厳守）: 入金・購入・GOは人間。ルーチンは**買い目を提示するだけ**。
> 認証情報(INET-ID/暗証番号/パスワード/Cookie)は一切扱わない・netkeibaへのログインもしない。

---

## 何が自動で走るか
```
土日の朝 → その日の全レースから約10レースを自動選定（重賞>OP/特別>特別 の順）
        → 各レースを netkeiba 公開データから予想（全頭ランキング＋買い目＋i-PAT）
        → 「確認連絡」として提示（GO・購入は君）
```
- タイム指数は netkeiba プレミアム限定なので既定 None（軸はほぼ不変・相手判別のみやや低下）。
  賭ける本命レースだけ**新聞のタイム指数**を貼れば `--tsi` で精度が戻る。

---

## 登録手順（どちらか）

### A. ターミナルCLIから（一番早い）
自分のPCのターミナル（web session内ではなく）で:
```
/schedule 毎週土日の朝9時に、リポジトリ horihorihorihorichiz/- で keiba/ の週末自動選定を実行
```
対話で聞かれたら下の「ルーチンのプロンプト」を貼る。保存後、頻度を土日にするため:
```
/schedule update      # cron を "3 9 * * 6,0"（土=6・日=0 の 9:03）に設定
```

### B. Web UIから（claude.ai/code/routines）
1. **New routine** を押す
2. **名前**: `競馬・週末自動選定`
3. **プロンプト**: 下の「ルーチンのプロンプト」をそのまま貼る
4. **リポジトリ**: `horihorihorihorichiz/-` を選ぶ
5. **環境（重要）**: Network access を **Custom** にして **Allowed domains** に下記を追加
   （既定のTrustedだと netkeiba が 403 で弾かれる）:
   ```
   nar.netkeiba.com
   race.netkeiba.com
   db.netkeiba.com
   ```
   「Also include default list of common package managers」もチェック。
6. **トリガー**: Schedule → 週次プリセットを選び、保存後 `/schedule update` で cron `3 9 * * 6,0`
   （= 毎週 土・日 の 9:03。分は0/30を避ける）
7. **Connectors / Permissions**: 使わない connector は外す。ブランチpushは `claude/` 既定のままでよい
8. **Create** → 週末に自動実行。今すぐ試すなら **Run now**

---

## ルーチンのプロンプト（コピペ）

```
あなたは競馬予想の週末オペレーターです。まず keiba/RULES.md と keiba/SOP.md を読んでルールを把握してください。

手順:
1. cd keiba
2. 今日の日付(YYYYMMDD)で本日開催レースから約10レースを自動選定し、各レースを予想する:
     python pick_races.py <今日のYYYYMMDD> --run --mobile --budget 10000
   （pick_races が選定→fetch_race→predict まで一気通貫。全頭ランキング=得点列必須・買い目・i-PAT・スマホ投票用が各レース出る）
3. 出力を「今週の確認連絡」としてレースごとに簡潔にまとめて報告する。各レース: 場・R・レース名、軸(Sランク馬番)、券種ごとの買い目と点数・合計金額、**スマホ投票用のコンパクト買い目**（📱ブロック）。
4. タイム指数は未取得(None)である旨を明記し、「本命として賭けるレースは新聞のタイム指数を貼れば --tsi で精度が上がる」と添える。

厳守:
- 購入・投票・入金は絶対にしない。買い目の提示（確認連絡）まで。GOは人間が出す。
- INET-ID/暗証番号/パスワード/Cookie等の認証情報を読まない・保存しない・netkeibaにログインしない。
- 予算10000円・100円単位・最低ライン200%(シナリオ保証)は RULES.md の通り predict.py が担保する。勝手に崩さない。
- レース結果はこの時点では未確定。results.jsonl への記録は結果確定後に別途行う。
```

---

## 携帯で買う（重要）
確認連絡は **Claudeモバイルアプリのセッションにそのまま届く**（ルーチンはクラウド実行）。
買い目は `--mobile` の 📱ブロックで券種ごと・馬番昇順に出るので、スマホの投票アプリに上から入力しやすい。

ネット投票の最短ルート（**認証情報は本システムでは一切扱わない・ログインもしない**）:
1. **netkeiba公式のIPAT/SPAT4連携**を使う。IPAT(JRA)/SPAT4(地方)のID登録は
   **netkeiba自身の設定画面で、あなたの手で一度だけ**行う（このリポジトリのコードは介在しない）。
2. スマホでnetkeibaにログイン済みの状態で、確認連絡の買い目をアプリのカート/投票画面に入れる。
3. **入金・最終確認・購入(GO)は必ず自分**。本システムは買い目提示まで。
- ※旧 `--cart`（ブックマークレット）はPCのオッズ画面用で**スマホでは動かない**。スマホは 📱ブロックを見て入力。

## 毎日の期待値スキャン（土日以外も）
「毎日、期待値レースがあれば教えて」用。別ルーチンとして登録:
- **cron**: `13 11 * * *`（毎日11:13頃）など。地方は平日も開催。
- **プロンプト**（コピペ）:
```
keiba/RULES.md と keiba/SOP.md を読んでから:
1. cd keiba
2. python pick_races.py <今日のYYYYMMDD> --ev --mobile --budget 10000
   （候補レースをモデル+オッズで評価し、GO=期待値プラスのレースだけ拾う）
3. GO該当レースだけを「今日の期待値レース」として、軸(Sランク)・期待回収%・買い目(📱スマホ用)で報告。
   該当0件なら「無理に張らない日」と正直に伝える。
厳守: 購入・入金・GOは人間。認証情報を扱わない・netkeibaにログインしない。
```
- 母数を広げたい時は `--all`、場を絞る時は `--tracks 川崎,大井` を足す。

## 補足
- **cron の土日**: `分 時 * * 6,0`（6=土, 0=日）。最小間隔は1時間。時刻は各自の地方時。
- **一時停止**: ルーチン詳細の **Repeats** トグルでオフ。
- **手動でも同じ結果**: `python pick_races.py <YYYYMMDD> --run` をいつでも実行可能。
- **場を絞る**: `--tracks 川崎,福島` 等。重賞だけにしたい時は本数 `--n` を絞る。
- セッション内だけの簡易スケジュールが欲しい時は `/loop` や CronCreate もあるが、
  **週をまたぐ恒久運用は Routines 一択**（セッション終了・コンテナ回収の影響を受けない）。
