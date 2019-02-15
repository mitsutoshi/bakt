bakt
====

[![CircleCI](https://circleci.com/gh/mitsutoshi/bakt.svg?style=svg)](https://circleci.com/gh/mitsutoshi/bakt)

## データ

### 約定履歴

約定履歴のレイアウトは、取引所から配信されるレイアウトにに従います。ただし、一部のレイアウトについて、オプションの項目を付与した約定履歴を扱うことができます。

#### bitflyer

##### File type

* tsv
* csv

##### Layout

* exec_date
* id
* side
* price
* size
* buy_child_order_acceptance_id
* sell_child_order_acceptance_id
* recv_delay_ms (**optional**): 受信遅延時間（ミリ秒） 

##### Sample

```csv
2019-02-04T03:00:00.017,785249417,SELL,369499,0.22,JRF20190204-025959-447562,JRF20190204-025959-297223
```
