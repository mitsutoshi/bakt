bakt
====

[![CircleCI](https://circleci.com/gh/mitsutoshi/bakt.svg?style=svg)](https://circleci.com/gh/mitsutoshi/bakt)

## 概要

暗号通貨の自動売買ストラテジーのバックテストを行うためのツールです。

* 分割約定に対応。
* 注文が有効になるまでの遅延時間を指定可能。
* 注文の有効時間を指定可能。時間経過による取引所内での注文キャンセルやAPIで注文キャンセルする戦略のテストが可能。
* 成行注文は未対応。（2019/2/15時点）

## 入力データ

### 約定履歴

約定履歴のレイアウトは、取引所から配信されるレイアウトに従います。ただし、一部のレイアウトについて、オプションの項目を付与した約定履歴を扱うことができます。

#### bitFlyer

##### File type

* tsv
* csv

### 約定履歴

|項目名|必須|出力内容|
|---|---|---|
|id|Yes|約定ID|
|exec_date|Yes|約定日時（UTF）|
|price|Yes|約定価格|
|size|Yes|約定サイズ（BTC）|
|side|Yes|テイク方向（BUY/SELL）|
|buy_child_order_acceptance_id|Yes|買い注文ID|
|sell_child_order_acceptance_id|Yes|売り注文ID|
|delay|No|受信遅延時間（秒）・・・約定日時と実際にその約定履歴を受信した日時の差の秒数です。浮動小数点数で表します。|

##### Sample

```csv
2019-02-04T03:00:00.017,785249417,SELL,369499,0.22,JRF20190204-025959-447562,JRF20190204-025959-297223
```

## 使用方法

### Configuration

設定ファイルを作成します。

sample.conf

```
hoge
```

### 実行

```bash
$ ./backt.py -f sample.conf
```


### 実行結果

#### レポートファイル

テスト結果は画像ファイルとして出力します。

#### ログファイル

実行すると、ログファイルとして`logs/bakt.log`が出力されます。バックテストの詳細を確認する場合は、このログファイルは毎回上書きします。

