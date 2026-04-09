# game-promo-hub チュートリアル

実際のユースケースに沿って、Discordスラッシュコマンドの使い方を段階的に説明します。

---

## ストーリー1: 新しいゲームをボットに登録する

**シナリオ**: あなたは「庭小人の冒険」という新しいインディーゲームの開発を始めました。ボットに情報を登録して宣伝の準備をします。

### Step 1-1: ゲームを登録する (`/game_add`)

Discordで `/game_add` と入力すると、ゲーム登録モーダルが開きます。

**モーダルの入力例**:

| 項目 | 入力例 |
|---|---|
| ゲームID | `niwa-kobito` |
| 日本語名 | `庭小人の冒険` |
| 英語名 | `Garden Gnome Adventure` |
| ジャンル | `パズルアクション` |
| ハッシュタグ | `#庭小人,#indiegame,#IndieGameDev` |
| 補足 | `platform=Steam`<br>`status=development`<br>`circle=ねこのおでこ`<br>`elevator_ja=庭に潜む小人を操って謎を解くパズルアクション` |

> **補足欄について**: `key=value` の形式で複数の情報を入力できます。`platform`、`status`、`circle`、`steam_url`、`elevator_ja`、`elevator_en`、`target_audience` などが設定可能です。

**入力後の結果**: ゲームが登録されると、登録内容を示すEmbed（ID・名前・ハッシュタグ）が表示されます。

---

### Step 1-2: 登録されているゲームを確認する (`/game_list`)

複数のゲームを開発している場合、一覧で確認できます。

```
/game_list
```

**表示例**:
```
登録ゲーム一覧
────────────────────────
庭小人の冒険 (niwa-kobito)
  status: development
  platform: Steam
  hashtags: #庭小人 #indiegame #IndieGameDev

VOID RED (void-red)
  status: development
  platform: Steam
  hashtags: #VOIDRED #indiegame
```

---

## ストーリー2: 進捗・アピールポイント・素材を追加する

**シナリオ**: ゲームの開発が進み、新しいステージが完成しました。この情報をボットに追加して、後でプロモツイートに活用できるようにします。

### Step 2-1: 進捗ログを追加する (`/progress_add`)

```
/progress_add game_id:niwa-kobito excitement:3 tweetable:True
```

**パラメータ説明**:
| パラメータ | 説明 | 例 |
|---|---|---|
| `game_id` | ゲームID | `niwa-kobito` |
| `excitement` | テンションレベル (1〜3) | `3`（3が最も高い） |
| `tweetable` | ツイート候補に含めるか | `True` / `False` |

コマンドを実行するとモーダルが開きます。

**モーダルの入力例**:

| 項目 | 入力例 |
|---|---|
| マイルストーン | `Stage 5 完成` |
| 進捗内容 | `新ステージ「霧の庭」を実装完了。新ギミックとして「水たまりジャンプ」を追加した。` |
| 宣伝ヒント | `新しいギミックの動画クリップがある。視覚的に映えるので投稿素材にしたい。` |
| 日付 | `2025-01-15`（デフォルトは今日） |

> **excitement について**: 3はマイルストーン達成などの重要な出来事に使います。2は通常の進捗、1は軽微な更新に使います。AIが下書きを生成する際に、高い excitement の進捗が優先されます。

---

### Step 2-2: アピールポイントを追加する (`/appeal_add`)

ゲームの強みや特徴を登録します。プロモ下書き生成時に参照されます。

```
/appeal_add game_id:niwa-kobito
```

モーダルが開きます。

**モーダルの入力例**:

| 項目 | 入力例 |
|---|---|
| カテゴリ | `mechanics` |
| 優先度 | `3` |
| タイトル | `直感的な謎解きシステム` |
| 内容 | `庭の環境を利用したパズル。水・土・風の3要素を組み合わせて謎を解く。チュートリアル不要で直感的にプレイできる。` |
| 宣伝ヒント | `「考えるより感じろ」というキャッチコピーが合いそう。GIFアニメが映えるゲームプレイ。` |

**カテゴリの種類**:
| カテゴリ | 説明 |
|---|---|
| `mechanics` | ゲームシステム・操作性 |
| `art` | アートスタイル・グラフィック |
| `story` | ストーリー・世界観 |
| `technical` | 技術的な特徴 |
| `general` | その他 |

---

### Step 2-3: 素材ファイルを登録する (`/asset_add`)

スクリーンショットやGIFをDiscordに添付して登録します。

```
/asset_add game_id:niwa-kobito file:[ファイルを添付] description:霧の庭ステージのゲームプレイGIF recommended_for:milestone
```

**パラメータ説明**:
| パラメータ | 説明 |
|---|---|
| `game_id` | ゲームID |
| `file` | 添付する画像・GIF・動画ファイル |
| `description` | 素材の説明文 |
| `recommended_for` | 推奨用途（下記参照） |

**`recommended_for` の種類**:
| 値 | 用途 |
|---|---|
| `initial` | ゲーム紹介・初回ツイート向け |
| `milestone` | マイルストーン達成ツイート向け |
| `technical` | 技術的な内容のツイート向け |
| `character` | キャラクター紹介ツイート向け |
| `any` | 汎用（どのツイートにも使える） |

**登録結果**: 素材ID・ファイル名・用途がEmbed表示されます。ファイルは `assets/niwa-kobito/` ディレクトリに保存されます。

---

## ストーリー3: AIでプロモツイートの下書きを生成・承認する

**シナリオ**: 素材の準備ができたので、AIを使ってツイートの下書きを生成します。生成された下書きを確認して承認するか、再生成を選択します。

### Step 3-1: プロモ下書きを生成する (`/promo_draft`)

```
/promo_draft game_id:niwa-kobito mode:milestone lang:both tone:excited
```

**パラメータ説明**:
| パラメータ | 選択肢 | 説明 |
|---|---|---|
| `game_id` | — | ゲームID（必須） |
| `mode` | `progress` / `appeal` / `milestone` / `random` / `technical` / `character` / `art` / `story` | 下書きの内容を決めるモード |
| `lang` | `ja` / `en` / `both` | 言語（`both` で日本語・英語の2本同時生成） |
| `tone` | `excited` / `casual` / `technical` / `mysterious` | ツイートのトーン |

**モードの使い分け**:
| モード | 用途 |
|---|---|
| `progress` | 最近の進捗をもとにした開発日記風ツイート |
| `appeal` | ゲームの魅力・特徴を紹介するツイート |
| `milestone` | マイルストーン達成を報告するツイート |
| `random` | AIが最適な内容を自動判断（初回はこれがおすすめ） |
| `technical` | 技術的な内容を深掘りするツイート |
| `character` | キャラクター紹介ツイート |
| `art` | アートワーク・ビジュアル系ツイート |
| `story` | ストーリー・世界観を紹介するツイート |

**生成結果の例**:
```
プロモ下書き
────────────────────────
ゲーム: 庭小人の冒険 (niwa-kobito)
モード: milestone
トーン: excited
ハッシュタグ: #庭小人 #indiegame #IndieGameDev

日本語:
🌿 新ステージ「霧の庭」が完成しました！
水たまりをジャンプ台にする新ギミックが気持ちよすぎて開発中に何度もやり直した笑
#庭小人 #indiegame

English:
🌿 New stage "Misty Garden" is complete!
The new puddle-jumping mechanic is so satisfying we kept replaying it during dev!
#GardenGnome #indiegame

推奨素材: gameplay_mist.gif
戦略メモ: マイルストーン達成を祝うエネルギッシュなツイート。GIFとセットで投稿するとエンゲージが高まる。

[承認してキューへ追加] [再生成] [キャンセル]
```

---

### Step 3-2: 承認または再生成を選択する

生成された下書きを確認して次のアクションを選択します：

| ボタン | 動作 |
|---|---|
| **承認してキューへ追加** | 下書きを承認し、投稿スケジュールキューへ追加する |
| **再生成** | 同じ設定で新しい下書きを生成し直す |
| **キャンセル** | 下書きを破棄する |

> **ポイント**: `lang=both` で生成した場合、日本語と英語が1つのグループとして承認されます。スケジューラが自動的に連続投稿（スレッド形式）します。

---

### Step 3-3: 既存の下書きを確認する (`/draft_list`)

承認待ちの下書きや承認済みキューを一覧で確認できます。

```
/draft_list
```

特定ゲームのみ絞り込む場合:

```
/draft_list game_id:niwa-kobito
```

**表示例**:
```
下書き一覧 / niwa-kobito
────────────────────────
⏳ 承認待ち (2 件)
#12 [ja] casual — 🌿 新ステージ「霧の庭」が完成しました...
#13 [en] casual — 🌿 New stage "Misty Garden" is compl...

✅ 承認済みキュー (1 件)
grp:abc123 [ja, en] niwa-kobito 2025-01-15
```

---

## ストーリー4: 定期投稿スロットを設定してキューを管理する

**シナリオ**: 承認済みの下書きが溜まってきました。毎日決まった時間に自動投稿されるよう、スロットを設定します。

### Step 4-1: 投稿スロットを追加する (`/schedule_slot_add`)

毎日投稿したい時刻を登録します。時刻はJST（日本標準時）で指定します。

```
/schedule_slot_add time_jst:08:00
```

複数のスロットを追加できます:

```
/schedule_slot_add time_jst:12:00
/schedule_slot_add time_jst:20:00
```

> **おすすめの投稿時間帯**: 朝8時・昼12時・夜20〜22時が国内のエンゲージメントが高い時間帯です。分析結果 (`/analytics_report`) で最適な時間帯を確認し、スロットを調整できます。

---

### Step 4-2: 投稿スロットを確認する (`/schedule_slot_list`)

```
/schedule_slot_list
```

**表示例**:
```
投稿スロット一覧
────────────────────────
#1  08:00 JST
#2  12:00 JST
#3  20:00 JST
```

---

### Step 4-3: 承認済みキューを確認する (`/schedule_queue_list`)

自動投稿を待っている承認済み下書きを確認します。

```
/schedule_queue_list
```

上限件数を指定する場合（デフォルト10件、最大20件）:

```
/schedule_queue_list limit:20
```

**表示例**:
```
承認済みキュー
────────────────────────
grp:abc123
  game: niwa-kobito
  approved_at: 2025-01-15
  langs: ja, en

single:45
  game: void-red
  approved_at: 2025-01-14
  langs: ja
```

---

### Step 4-4: キューから取り消す (`/schedule_queue_cancel`)

間違って承認した下書きをキューから外します。

```
/schedule_queue_cancel queue_id:grp:abc123
```

単一の下書きの場合:

```
/schedule_queue_cancel queue_id:single:45
```

> **スケジューラの動作**: 設定したスロットの時刻になると、スケジューラが承認済みキューから自動的に1件を選んでX/Twitterに投稿します。複数ゲームがある場合は均等にローテーションされます。

---

### Step 4-5: スロットを削除する (`/schedule_slot_remove`)

不要になったスロットを削除します。スロットIDは `/schedule_slot_list` で確認できます。

```
/schedule_slot_remove slot_id:2
```

---

## ストーリー5: 分析レポートで投稿を改善する

**シナリオ**: 数週間分のツイートデータが溜まりました。何のツイートが反響を呼んでいるか分析して、今後の戦略を改善します。

### Step 5-1: メトリクスを取得する (`/analytics_fetch`)

X/Twitter APIから各ツイートのインプレッション数・いいね数・リツイート数などを取得してDBに保存します。

```
/analytics_fetch game_id:niwa-kobito
```

> **注意**: このコマンドは過去90日以内のツイートを対象に、まだメトリクスが取得されていないツイートのみを更新します。実行後に `/analytics_report` で分析します。

---

### Step 5-2: 分析レポートを生成する (`/analytics_report`)

AIがツイートデータを分析して、改善提案を生成します。

```
/analytics_report game_id:niwa-kobito
```

特定の月を指定する場合（デフォルトは今月）:

```
/analytics_report game_id:niwa-kobito period:2025-01
```

**表示例**:
```
分析レポート niwa-kobito / 2025-01
────────────────────────
最適時間帯: 20:00〜22:00
最適トーン:  excited
最適素材:   GIF

避けるべきパターン:
・テキストのみの投稿（エンゲージ率が低い）
・平日昼12時台（インプレッションが少ない）

次の戦略:
マイルストーン系のツイートとGIF素材の組み合わせが高エンゲージ。
次の2週間はmilestoneモード + excitedトーンを中心に3日に1回投稿。

推奨スケジュール: 週2〜3回 / 月・水・金
```

---

### Step 5-3: エンゲージメント上位投稿を確認する (`/analytics_top`)

どのツイートが最も反響を呼んだかを確認します。

```
/analytics_top game_id:niwa-kobito
```

上位件数を指定する場合（デフォルト5件、最大10件）:

```
/analytics_top game_id:niwa-kobito limit:10
```

**表示例**:
```
Top 5 / niwa-kobito
────────────────────────
#1  4.82%  ❤️156  🔁43
🌿 新ステージ「霧の庭」が完成しました！水たまりをジャンプ台...
https://x.com/your_account/status/...

#2  3.21%  ❤️98  🔁21
庭小人の冒険、Steam ウィッシュリスト登録受け付け中です...
https://x.com/your_account/status/...
```

> **活用方法**: 上位ツイートのトーン・モード・素材の組み合わせを参考にして `/promo_draft` のパラメータを選ぶと、効果的なツイートを生成しやすくなります。

---

## まとめ：典型的なワークフロー

```
① ゲーム登録
   /game_add → ゲーム情報を登録

② 情報の蓄積（日常的に繰り返す）
   /progress_add → 開発の進捗を記録
   /appeal_add   → ゲームの魅力・特徴を追加
   /asset_add    → スクリーンショット・GIFを登録

③ 下書き生成（週1〜3回）
   /promo_draft → AI がツイート下書きを生成
   → 内容を確認して「承認」or「再生成」or「キャンセル」

④ キュー確認
   /draft_list          → 承認待ち・承認済みを確認
   /schedule_queue_list → 自動投稿待ちキューを確認

⑤ 自動投稿（スロット設定後は自動）
   /schedule_slot_add  → 投稿時刻を設定
   → 設定時刻に承認済みキューから自動投稿

⑥ 分析・改善（月1回程度）
   /analytics_fetch  → メトリクスを取得
   /analytics_report → AI が改善提案を生成
   /analytics_top    → 上位投稿を確認
   → 分析結果を参考に次の下書き生成のパラメータを調整
```

---

## コマンドクイックリファレンス

| コマンド | 必須パラメータ | 主なオプション |
|---|---|---|
| `/game_add` | なし（モーダルで入力） | — |
| `/game_list` | — | — |
| `/progress_add` | `game_id` | `excitement` (1-3), `tweetable` |
| `/appeal_add` | `game_id` | — |
| `/asset_add` | `game_id`, `file` | `description`, `recommended_for` |
| `/promo_draft` | `game_id` | `mode`, `lang`, `tone` |
| `/draft_list` | — | `game_id` |
| `/schedule_slot_add` | `time_jst` (HH:MM) | — |
| `/schedule_slot_list` | — | — |
| `/schedule_slot_remove` | `slot_id` | — |
| `/schedule_queue_list` | — | `limit` (1-20) |
| `/schedule_queue_cancel` | `queue_id` | — |
| `/analytics_fetch` | `game_id` | — |
| `/analytics_report` | `game_id` | `period` (YYYY-MM) |
| `/analytics_top` | `game_id` | `limit` (1-10) |
