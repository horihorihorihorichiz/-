# 週末ルーチン設定手順（Ver.100=紙上運用が本線／旧・レース選定も残置）

## ★★最新（2026-08-08〜 / 2026-08-17プロンプト更新）: デイボード+15分前プッシュ通知ルーチン（こちらを登録）
> 8/17更新: 直前判定(confirmed)・watch_log(W10/W11)・notify --heartbeat の3点を追加。
> **登録済みのルーチンにも下のプロンプトを貼り直すこと**（貼り直さないと旧手順のまま回る）。
登録: claude.ai/code/routines → New routine
- 名前: `競馬・週末デイボード運用`
- cron: `3 9 * * 6,0`（土日 9:03 JST）
- リポジトリ: `horihorihorihorichiz/-`（Allowed domainsは旧手順のnetkeiba系と同じ）
- プロンプト（そのまま貼る）:
```
keiba/RULES.md §0 と keiba/CLAUDE.md の競馬節を読んでから、当日運用を開始:
0. pip install -q numpy lightgbm && cd keiba && python3 selfcheck.py  # ALL GREEN必須
1. python3 day_board.py で今日の全場ボードを生成し、SendUserFileで送付
2. python3 paper_rank.py run で発火レースを紙上記帳 / python3 watch_log.py run でW10/W11を記録
3. 以降は終日パトロール: 各買いレース(A近接含む)の発走15分前に
   paper_rank.py run→最新オッズ+馬体重(day_board.refresh_weights)を反映し、
   PushNotificationとチャットで通知(買い目・金額・オッズ→払戻・馬体重±・判定変化)。
   ★発走25分以内の再判定で発火が残ると confirmed=true(=正式な買い)。朝だけ判定して放置すると
     永久にwatch(参考値)にしかならないので、買い候補は必ずT-25〜T-15で再実行する。
   ★同じタイミングで watch_log.py run も回す(W11の10倍+判定がJRA公式オッズで正確になる)。
   ★心拍のたびに python3 notify.py --heartbeat を実行。停止ギャップ(20分以上の空白)と
     期限超過の未送信通知が出たら、遅延分も含めて即送信する(RULES §通知7)。
   発走3分前は paper_rank.py run で凍結。確定後は paper_rank.py settle→結果をプッシュ報告。
   待ち時間は ScheduleWakeup で「次のレースの発走15分前の4分前」に起床を張り、
   ユーザーと会話したら返信の最後に必ず張り直す。保険として15分間隔のCronCreateも張る。
4. 全レース終了後: paper_rank.py stats で日次精算(2日累計・150Rライン進捗)を報告し、
   watch_log.py settle && watch_log.py stats でW10/W11の当日分も精算・報告し、
   まとめmdを SendUserFile で送付、commit & push（ブランチ claude/stoic-ride-p35k9n）
※環境リセット検出時(ファイル欠損/HEADが古い)は git fetch origin claude/stoic-ride-p35k9n
  && git merge --ff-only origin/claude/stoic-ride-p35k9n && pip install -q numpy lightgbm で復旧。
※実弾なし=紙上のみ。購入・投票・GOは人間。認証情報は扱わない・netkeibaにログインしない。
※結果は確定後のみ記録。判定ライン: 精算150Rで回収90%超→少額実弾の相談／70%未満→設計見直し。
```

## ★Ver.100 紙上運用ルーチン（2026-07-12〜の旧本線。上の新版を推奨）
登録: claude.ai/code/routines → New routine
- 名前: `競馬・週末紙上運用(Ver.100)`
- cron: `3 9 * * 6,0`（土日 9:03 JST）
- リポジトリ: `horihorihorihorichiz/-`（環境のAllowed domainsは下記・旧手順のnetkeiba系と同じ）
- プロンプト（そのまま貼る）:
```
keiba/RULES.md §0(Ver.100体制)を読んでから、以下を順に実行:
0. pip install -q numpy lightgbm  # Ver.3モデル用(新環境では毎回必要)
1. cd keiba && python paper.py settle && python paper.py stats   # 前回分の精算と成績
2. python paper.py run <今日のYYYYMMDD>                          # 今日の全JRAレースを紙上運用
3. もし harvest_year.py の収穫が未完了(harvest_year.stateのdoneに20260705が無い)なら
   nohup python3 harvest_year.py >> harvest_year.log 2>&1 & で収穫を再開して先へ進む
4. 収穫完了済みなら月1回程度の再学習: python fit_score.py --l2 0.05 --write &&
   python fit_score.py --surface 芝 --l2 0.08 --write && python fit_score.py --surface ダ --l2 0.08 --write &&
   python fit.py --test <直近2週末の日付8桁カンマ区切り> --write
5. 日曜のみ: python win5.py --dry でWIN5のキャリーオーバーを確認。繰越ありなら
   python win5.py --budget 5000 でフォーメーション案を作り報告に含める（繰越なし=見送りの一言でOK）
6. paper.py stats の結果と、GOになったレースの買い目(オッズ→払戻付き)をまとめmdにして SendUserFile で送る
7. 変更を commit & push（ブランチ claude/stoic-ride-p35k9n）
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

## 【TODO 2026-08-13】毎朝ルーチンのNAR(大井)対応
現行の毎朝9:03ルーチン(trig_01W62FS4)はJRA開催チェックのみ→大井ナイターの日は起動しない。
次にcreate_trigger/update_triggerツールが使えるセッションで、開催判定を
「JRA(nar=False) or 大井(nar=Trueでvenue=大井)のレースがあれば稼働」に更新すること。
大井の日は夕方〜ナイターパトロール(oi_patterns判定・15分前通知・9分心拍cron必須)。

## 【TODO 2026-08-15】毎朝ルーチンに通知台帳(notify.py)を組込み
update_triggerツールが使えるセッションで trig_01W62FS4 のpromptに以下を追記:
- 記帳時に notify.plan(race_id,"pre15",...) / notify.plan(race_id,"result",...) を登録
- 通知送信直後に notify.mark()、心拍は毎回 python3 notify.py で欠落チェック→即送信
(RULES.md §通知・運用の恒久ルール参照。本文はセッション8/15の下書きを参照)

## 【TODO 2026-08-16】毎朝ルーチンを土日のみに変更(ユーザー指示)
trig_01W62FS4 の cron を "3 0 * * 6,0"(土日9:03JST) に更新する。update_triggerが承認待ちで未完。
次に承認が通るセッション、または claude.ai/code/routines のUIから変更。平日大井は自動起動しない。

---

# ★★ 2026-08-21 更新: 土曜運用の必須手順（監査で判明した抜けを反映）★★

## 起動時刻の是正
RULES §9 は「1R発走の3時間前＝6:30-7:00 に起こす」だが、旧ルーチンの cron は `3 9 * * 6,0`＝**9:03起動**だった。
実測（8/22・36R・初R 09:40）での取り逃し:

| 起動 | 取り逃し |
|---|---|
| 06:30（RULES §9 準拠） | 0 / 684時点 |
| 09:05（旧ルーチン） | **27 / 684 (4%) ・14R分の T-180/T-90/T-60/T-45** |
| 09:40（1R発走） | 62 / 684 (9%) |

→ **開催日は 6:30 に odds_timeline を起こす**。オッズ時系列は後から作り直せない唯一のデータ。

## 開催日の必須コマンド（旧プロンプトに無かったもの）
```bash
cd keiba
# ① 6:30 — オッズ時系列の収集を起こす（最優先。これだけは遅らせない）
nohup python3 odds_timeline.py watch > logs/odds_timeline_$(date +%Y%m%d).log 2>&1 &
tail -3 logs/odds_timeline_$(date +%Y%m%d).log   # 「NNレース / 予定NNN時点」が出ることを目視
# ② 起動検査 → 当日ボード
python3 selfcheck.py && python3 day_board.py
# ③ 各レース（発走25分前〜3分前に再実行して confirmed 化・凍結）
python3 paper_rank.py run
python3 watch_log.py run --fast
python3 v99w_rank.py run <race_id> --post <発走HH:MM>     # 5レーン並走
python3 w12_watch.py run <race_id> --post <発走HH:MM>     # W12前向き検証
# ④ 終了後（確定後のみ・捏造禁止）
python3 paper_rank.py settle && python3 paper_rank.py stats
python3 watch_log.py settle && python3 watch_log.py stats
python3 v99w_rank.py settle && python3 v99w_rank.py stats
python3 w12_watch.py settle && python3 w12_watch.py stats
python3 odds_timeline.py settle && python3 odds_timeline.py stats
python3 odds_timeline.py compact --keep-days 14           # 台帳肥大の抑制
```

## 人間がやること（システムが自力でできない）
1. **6:30 に odds_timeline を起こす**（上の①）。起動直後に tail で「NNレース」を目視確認。
   `対象レースなし` が出たら取得障害なので上げ直す（2026-08-21修正で45分は自動再試行し、
   それでも空なら rc=3 で落ちる＝非開催日と区別できる）。
2. **朝・昼・夕の3回、同じ tail で生存確認**。消えていたら上げ直す（取得済みはスキップされる）。
   ロックが残って「既に watch が動いている(pid …)」と出たら、そのPIDが本当に watch か確認して
   違えば `--force`。
3. **selfcheck が ❌ なら表示された fix コマンドを実行してから運用開始**。
   コンテナリセット後は *.pkl（gitignore対象）が無く再生成に数分かかる。
4. **買い候補レースは T-25〜T-15 に必ず再判定を回す**（confirmed 化。パトロール間隔は25分以内）。
5. **道悪の日は `python3 day_board.py --baba` を発走前に叩き直す**（体重/馬場の再取得失敗は黙殺される）。
6. **購入・投票・GO は人間**（変更なし）。システムは買い目提示まで。

## 並走させてはいけないもの
同じ台帳を触る run を2つ同時に走らせない（4台帳とも全書き換えのため後勝ちで消える）。
逐次の二重実行は冪等で安全（実測: 同じ race_id を2回 run しても行は増えない）。
