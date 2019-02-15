from typing import List

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from baktlib.models import Order, Execution, Position


def print_orders(orders: List[Order]):
    t = pd.DataFrame(data={'id': [o.id for o in orders],
                           'created_at': [o.created_at for o in orders],
                           'side': [o.side for o in orders],
                           'type': [o.type for o in orders],
                           'price': [o.price for o in orders],
                           'size': [o.size for o in orders],
                           'status': [o.status for o in orders],
                           'open_size': [o.open_size for o in orders]})
    print('\n[Orders]\n')
    print(t.loc[:, ['id', 'created_at', 'side', 'type', 'size', 'price', 'status', 'open_size']])


def print_executions(orders: List[Order]):
    executions = []  # type: List[Execution]
    for o in orders:
        executions.extend(o.executions)
    t = pd.DataFrame(data={'created_at': [o.created_at for o in executions],
                           'side': [o.side for o in executions],
                           'price': [o.price for o in executions],
                           'size': [o.size for o in executions],
                           'order_id': [o.order_id for o in executions]})
    print('\n[Executions]\n')
    print(t.loc[:, ['created_at', 'side', 'size', 'price', 'order_id']])


def print_trades(trades: List[Position]):
    t = pd.DataFrame(data={'id': [o.id for o in trades],
                           'open_order_id': [o.open_order_id for o in trades],
                           'side': [o.side for o in trades],
                           'amount': [o.amount for o in trades],
                           'opened_at': [o.opened_at for o in trades],
                           'open_price': [o.open_price for o in trades],
                           'open_fee': [o.open_fee for o in trades],
                           'open_amount': [o.open_amount for o in trades],
                           'closed_at': [o.closed_at for o in trades],
                           'close_price': [o.close_price for o in trades],
                           'close_fee': [o.close_fee for o in trades],
                           'pnl': [o.pnl for o in trades]})
    print('\n[Trades]\n')
    print(t.sort_values('id').loc[:, ['id', 'open_order_id', 'side', 'amount', 'opened_at', 'open_price', 'open_amount',
                                      'open_fee', 'closed_at', 'close_price', 'close_fee', 'pnl']])


def print_positions(trades: List[Position]):
    t = pd.DataFrame(data={'id': [o.id for o in trades],
                           'open_order_id': [o.open_order_id for o in trades],
                           'side': [o.side for o in trades],
                           'amount': [o.amount for o in trades],
                           'opened_at': [o.opened_at for o in trades],
                           'open_price': [o.open_price for o in trades],
                           'open_fee': [o.open_fee for o in trades],
                           'open_amount': [o.open_amount for o in trades],
                           'closed_at': [o.closed_at for o in trades],
                           'close_price': [o.close_price for o in trades],
                           'close_fee': [o.close_fee for o in trades],
                           'pnl': [o.pnl for o in trades]})
    print('\n[Positions]\n')
    print(t.sort_values('id').loc[:, ['id', 'open_order_id', 'side', 'amount', 'opened_at', 'open_price', 'open_amount',
                                      'open_fee', 'closed_at', 'close_price', 'close_fee', 'pnl']])


def print_graph(orders, result):
    title_fsize = 22
    label_fsize = 16
    figsize = (36, 24)
    dpi = 96

    fig, axes = plt.subplots(nrows=3, ncols=2, figsize=figsize, dpi=dpi)  # type: Figure, Tuple(Axes, Axes)
    plt.subplots_adjust(right=2)

    #
    # グラフ１：相場価格、出来高、注文価格
    #

    # 軸１、相場価格
    ax_market = axes[1][0]  # type: Axes
    ax_market.set_title('Market & Orders', fontsize=title_fsize)
    ax_market.set_xlabel('Time', fontsize=label_fsize)
    ax_market.set_ylabel('Price', fontsize=label_fsize)
    ax_market.plot(range(len(result['last_prices'])), result['last_prices'], color='blue', label='Price')

    # 軸１、注文価格
    max_order_num = 0
    for o in orders:
        max_order_num = max(max_order_num, len(o))
    for i in range(max_order_num):
        buy_prices = [os[i].price if os and len(os) > i and os[i].side == 'BUY' else None for os in orders]
        sell_prices = [os[i].price if os and len(os) > i and os[i].side == 'SELL' else None for os in orders]
        ax_market.plot(range(len(buy_prices)), buy_prices, '.', color='g', markersize=12, label='buy order price')
        ax_market.plot(range(len(sell_prices)), sell_prices, '.', color='r', markersize=12, label='sell order price')
    ax_market.grid()
    ax_market.legend(loc='upper left')

    # 軸２、売買種類別出来高
    ax_market_2 = ax_market.twinx()  # type: Axes
    ax_market_2.set_ylabel('Volume', fontsize=label_fsize)
    ax_market_2.legend(loc='upper right')
    ax_market_2.bar(range(len(result['market_buy_size'])), result['market_buy_size'], color='g', alpha=0.5,
                    label='Buy Volume')
    ax_market_2.bar(range(len(result['market_sell_size'])), result['market_sell_size'], color='r', alpha=0.5,
                    label='Sell Volume')

    #
    # グラフ２：Realized Gain/Loss
    #

    # 軸１、実現損益
    ax_pnl = axes[1][1]  # type: Axes
    ax_pnl.set_title('Realized Gain/Loss', fontsize=title_fsize)
    ax_pnl.set_xlabel('Time', fontsize=label_fsize)
    ax_pnl.set_ylabel('Price', fontsize=label_fsize)
    ax_pnl.fill_between(range(0, len(result['realized_gain'])), result['realized_gain'], color='blue', alpha=1,
                        linestyle='solid',
                        label='Realized Gain/Loss')
    ax_pnl.hlines(0, xmin=0, xmax=len(result['realized_gain']), colors='r', linestyles='dotted')
    ax_pnl.grid()
    ax_pnl.legend(loc='upper left')

    #
    # グラフ３：ポジション、未実現損益
    #

    # 軸１、保有ポジション量
    ax_pos = axes[2][0]  # type: Axes
    ax_pos.set_title('Position', fontsize=title_fsize)
    ax_pos.set_ylabel('Size', fontsize=label_fsize)
    ax_pos.bar(range(0, len(result['buy_pos_size'])), result['buy_pos_size'], color='g', alpha=0.5,
               label='Long position size')
    ax_pos.bar(range(0, len(result['sell_pos_size'])), result['sell_pos_size'], color='r', alpha=0.5,
               label='Short position size')
    ax_pos.legend(loc='upper left')

    # 軸２、未実現損益
    ax_pos_2 = ax_pos.twinx()  # type: Axes
    ax_pos_2.set_ylabel('Price', fontsize=label_fsize)
    ax_pos_2.plot(range(0, len(result['unrealized_gain'])), result['unrealized_gain'], color='blue', alpha=1,
                  linestyle='solid',
                  label='Unrealized Gain/Loss')
    ax_pos_2.hlines(0, xmin=0, xmax=len(result['unrealized_gain']), colors='r', linestyles='dotted')
    ax_pos_2.legend(loc='upper right')

    #
    # グラフ４：実現損益のヒストグラム
    #

    # トレード別損益ヒストグラム
    ax_hist = axes[2][1]  # type: Axes
    ax_hist.set_title('Realized Gain/Loss Histgram', fontsize=title_fsize)
    ax_hist.set_xlabel('Price', fontsize=label_fsize)
    ax_hist.set_ylabel('Count', fontsize=label_fsize)
    ax_hist.hist(result['pnl_per_trade'], bins=20, color='blue', alpha=1.0, label='Realized Gain/Loss')
    ax_hist.vlines(x=0, ymin=0, ymax=1, colors='r', linestyles='solid')

    ax_text = axes[0][0]  # type: Axes
    ax_text.axis('off')
    ax_text.spines["right"].set_color("none")
    ax_text.spines["left"].set_color("none")
    ax_text.spines["top"].set_color("none")
    ax_text.spines["bottom"].set_color("none")

    fsize = 19
    label_x = 0.05
    value_x = 0.25
    y_span = 0.06
    y_subtitle = 0.70
    y = 0.60

    ax_text.text(0.01, y_subtitle, "Test result", fontsize=28)

    # 注文セクション
    ax_text.text(0.03, y, "Orders", fontsize=fsize)
    y -= y_span

    # 注文回数
    ax_text.text(label_x, y, "Number of orders", fontsize=fsize)
    ax_text.text(value_x, y,
                 f"{result['num_of_orders']:,} (Limit: {result['num_of_limit_orders']:,}"
                 f", Market: {result['num_of_market_orders']:,}"
                 f" / Buy: {result['num_of_buy_orders']:,}, Sell: {result['num_of_sell_orders']:,})", fontsize=fsize)
    y -= y_span

    # 注文サイズ
    ax_text.text(label_x, y, "Size", fontsize=fsize)
    ax_text.text(value_x, y, "{:,} BTC (Limit: {:,}, Market: {:,} / Average size: {:,})"
                 .format(result['size_of_orders'],
                         result['size_of_limit_orders'],
                         result['size_of_market_orders'],
                         result['avg_order_size']), fontsize=fsize)
    y -= y_span

    ax_text.text(label_x, y, "Status", fontsize=fsize)
    ax_text.text(value_x, y, "Completed: {:,}, Canceled: {:,}, Active: {:,}"
                 .format(result['num_of_completed_orders'],
                         result['num_of_canceled_orders'],
                         result['num_of_active_orders']), fontsize=fsize)
    y -= y_span

    # 約定セクション
    ax_text.text(0.03, y, "Executions", fontsize=fsize)
    y -= y_span

    ax_text.text(label_x, y, "Number of executions", fontsize=fsize)
    ax_text.text(value_x, y, f"{result['num_of_exec']:,}", fontsize=fsize)
    y -= y_span

    ax_text.text(label_x, y, "Size", fontsize=fsize)
    ax_text.text(value_x, y, f"{result['size_of_exec']:,.8} BTC", fontsize=fsize)
    y -= y_span

    # 約定率
    ax_text.text(label_x, y, "Execution %", fontsize=fsize)
    ax_text.text(value_x, y, f"{result['exec_rate']:.2%}", fontsize=fsize)
    y -= y_span

    ax_text.text(0.03, y, "Profit and Loss", fontsize=fsize)
    ax_text.text(value_x, y, f"{result['total_pnl']:,} JPY (Profit: {result['profit']:,}"
    f", Loss: {result['loss']:,}, PF: {result['pf']:,})", fontsize=fsize)
    y -= y_span

    ax_text.text(0.03, y, "Win %", fontsize=fsize)
    ax_text.text(value_x, y, f"{result['win_rate']:.2%} (win: {result['num_of_win']:,}, "
    f"lose: {result['num_of_lose']:,}, even: {result['num_of_even']:,} / All: {result['num_of_trades']})",
                 fontsize=fsize)
    y -= y_span

    # テキスト２

    # test conditions
    # 1. データの期間
    # 2. 取引時間の間隔
    # 3. トレード数

    ax_text_r = axes[0][1]  # type: Axes
    ax_text_r.text(0.01, y_subtitle, "Test conditions", fontsize=28)
    ax_text_r.axis('off')
    ax_text_r.spines["right"].set_color("none")
    ax_text_r.spines["left"].set_color("none")
    ax_text_r.spines["top"].set_color("none")
    ax_text_r.spines["bottom"].set_color("none")

    # label_x = 0.05
    # value_x = 0.25
    y = 0.6

    # 通貨ペア
    ax_text_r.text(label_x, y, "Symbol", fontsize=fsize)
    ax_text_r.text(value_x, y, "FX_BTC_JPY", fontsize=fsize)
    y -= y_span

    # データ期間
    ax_text_r.text(label_x, y, "Data duration", fontsize=fsize)
    ax_text_r.text(value_x, y, f"From: {result['data_from']}, To: {result['data_to']}", fontsize=fsize)
    y -= y_span

    # データ件数
    ax_text_r.text(label_x, y, "Number of data", fontsize=fsize)
    ax_text_r.text(value_x, y, f"{result['data_length']:,}", fontsize=fsize)
    y -= y_span

    # 時間枠
    ax_text_r.text(label_x, y, "Time frame of trade", fontsize=fsize)
    ax_text_r.text(value_x, y, f"{result['timeframe_sec']:,} seconds", fontsize=fsize)
    y -= y_span

    # トレード数
    ax_text_r.text(label_x, y, "Number of time frame", fontsize=fsize)
    ax_text_r.text(value_x, y, f"{result['num_of_timeframes']:,}", fontsize=fsize)
    y -= y_span

    ax_text.text(0.65, 0.85, f"Back Test Report {result['datetime']} ", fontsize=32)
    # ({__conv_htime(result['duration'])})

    # plt.suptitle('bakt', fontsize=32)
    # plt.subplots_adjust(hspace=0.9)

    plt.savefig('./hoge.png')
    plt.show()


def __conv_htime(seconds: int) -> str:
    if seconds < 60:
        return f"{round(seconds)} seconds"
    elif seconds < 3600:
        return f"{seconds // 60} min {round(seconds % 60)} sec"
    else:
        h = seconds // 3600
        m = (seconds - h * 3600) // 60
        s = round(seconds % 60)
        return f"{h} h {m} m {s} s"
