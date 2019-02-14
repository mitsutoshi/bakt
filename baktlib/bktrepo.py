from typing import List

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from baktlib.models import Order, Execution, Position
from decimal import Decimal


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
    print(t.loc[:, ['id', 'side', 'amount', 'opened_at', 'open_price', 'open_amount',
                    'open_fee', 'closed_at', 'close_price', 'close_fee', 'pnl']])


def print_graph(executions: pd.DataFrame,
                trades: List[Position],
                buy_pos_size: List[float],
                sell_pos_size,
                realized_pnl,
                unrealized_pnl,
                ltp_hst,
                buy_volume,
                sell_volume,
                times,
                orders,
                executions_me: List[Execution],
                result):
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
    ax_market.set_title('Orders', fontsize=title_fsize)
    ax_market.set_xlabel('Time', fontsize=label_fsize)
    ax_market.set_ylabel('Price', fontsize=label_fsize)
    ax_market.plot(range(len(ltp_hst)), ltp_hst, color='orange', label='Price')

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
    if buy_volume:
        ax_market_2.bar(range(len(buy_volume)), buy_volume, color='g', alpha=0.5, label='Buy Volume')
    if sell_volume:
        ax_market_2.bar(range(len(sell_volume)), sell_volume, color='r', alpha=0.5, label='Sell Volume')

    #
    # グラフ２
    #

    # 軸１、実現損益
    ax_pnl = axes[1][1]  # type: Axes
    ax_pnl.set_title('Realized Profit and Loss', fontsize=title_fsize)
    ax_pnl.set_xlabel('Time', fontsize=label_fsize)
    ax_pnl.set_ylabel('Price', fontsize=label_fsize)
    if realized_pnl:
        ax_pnl.fill_between(range(0, len(realized_pnl)), realized_pnl, color='orange', alpha=1, linestyle='solid',
                            label='Realized PnL')
    ax_pnl.hlines(0, xmin=0, xmax=len(realized_pnl), colors='r', linestyles='dotted')
    ax_pnl.grid()
    ax_pnl.legend(loc='upper left')

    #
    # グラフ３
    #

    # 軸１、保有ポジション量
    ax_pos = axes[2][0]  # type: Axes
    ax_pos.set_title('Position', fontsize=title_fsize)
    if buy_pos_size or sell_pos_size:
        ax_pos.set_ylabel('Size', fontsize=label_fsize)
        ax_pos.bar(range(0, len(buy_pos_size)), buy_pos_size, color='g', alpha=0.5, label='Long position size')
        ax_pos.bar(range(0, len(sell_pos_size)), sell_pos_size, color='r', alpha=0.5, label='Short position size')
        ax_pos.legend(loc='upper left')

    # 軸２、含み損益
    ax_pos_2 = ax_pos.twinx()  # type: Axes
    if unrealized_pnl:
        ax_pos_2.set_ylabel('Price', fontsize=label_fsize)
        ax_pos_2.plot(range(0, len(unrealized_pnl)), unrealized_pnl, color='blue', alpha=1, linestyle='solid',
                      label='Unrealized Pnl')
        ax_pos_2.hlines(0, xmin=0, xmax=len(unrealized_pnl), colors='r', linestyles='dotted')
        ax_pos_2.legend(loc='upper right')

    #
    # グラフ４
    #

    # トレード別損益ヒストグラム
    pnl = []
    total_pnl = 0
    for t in trades:
        total_pnl += t.pnl
        pnl.append(total_pnl)
    ax_hist = axes[2][1]  # type: Axes
    ax_hist.set_title('Realized Profit and Loss Histgram', fontsize=title_fsize)
    ax_hist.set_xlabel('Price', fontsize=label_fsize)
    ax_hist.set_ylabel('Count', fontsize=label_fsize)
    if pnl:
        ax_hist.hist(pnl, bins=20, color='orange', alpha=0.5, label='Realized Profit and Loss')
        ax_hist.vlines(x=0, ymin=0, ymax=1, colors='r', linestyles='solid')

    # plt.xticks(color=None)
    ax_text = axes[0][0]  # type: Axes
    ax_text.axis('off')
    # ax_text.tick_params(axis='both', color=None, length=0)
    ax_text.spines["right"].set_color("none")
    ax_text.spines["left"].set_color("none")
    ax_text.spines["top"].set_color("none")
    ax_text.spines["bottom"].set_color("none")


    fsize = 20
    label_x = 0.04
    value_x = 0.25
    ax_text.text(label_x, 0.1, "Number of orders", fontsize=fsize)
    ax_text.text(value_x, 0.1, "{:,} (contracted: {:,}, canceled: {:,}, active: {:,})".format(
        result['num_of_orders'], result['num_of_completed_orders'], result['num_of_canceled_orders'], result['num_of_active_orders']), fontsize=fsize)

    ax_text.text(label_x, 0.2, "Number of executions", fontsize=fsize)
    ax_text.text(value_x, 0.2, "{:,}".format(result['num_of_executions']), fontsize=fsize)

    ax_text.text(label_x, 0.3, "Profit and Loss", fontsize=fsize)
    ax_text.text(value_x, 0.3, "{:,} JPY".format(result['total_pnl']), fontsize=fsize)

    ax_text.text(label_x, 0.4, "Size of executions", fontsize=fsize)
    ax_text.text(value_x, 0.4, "{:,.8} BTC".format(result['size_of_executions']), fontsize=fsize)

    ax_text.text(label_x, 0.5, "Win percent", fontsize=fsize)
    ax_text.text(value_x, 0.5, "{:.2%} (win: {:,}, lose: {:,}, even: {:,})".format(
        result['num_of_win'] / result['num_of_completed_orders'],
        result['num_of_win'], result['num_of_lose'], result['num_of_even']), fontsize=fsize)

    ax_text.text(0.02, 0.6, "Test result", fontsize=28)

    # テキスト２
    ax_text_r = axes[0][1]  # type: Axes
    ax_text_r.axis('off')
    ax_text_r.spines["right"].set_color("none")
    ax_text_r.spines["left"].set_color("none")
    ax_text_r.spines["top"].set_color("none")
    ax_text_r.spines["bottom"].set_color("none")

    ax_text.text(0.8, 0.8, "Back Test Report 2019-02-14 19:00", fontsize=32)

    # plt.suptitle('bakt', fontsize=32)
    # plt.subplots_adjust(hspace=0.9)

    plt.savefig('./hoge.png')
    plt.show()
