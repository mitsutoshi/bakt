from typing import List

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from baktlib.models import Order, Position


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
                sell_volume):

    title_fsize = 22
    label_fsize = 16
    figsize = (16, 24)
    dpi = 60

    fig, axes = plt.subplots(nrows=3, ncols=1, figsize=figsize, dpi=dpi)  # type: Figure, Tuple(Axes, Axes)

    # マーケットグラフ（軸１、価格）
    ax_market = axes[0]  # type: Axes
    ax_market.set_title('Market', fontsize=title_fsize)
    ax_market.set_xlabel('Time', fontsize=label_fsize)
    ax_market.set_ylabel('Price', fontsize=label_fsize)
    ax_market.plot(range(0, len(ltp_hst)), ltp_hst, color='orange', label='Price')
    ax_market.grid()
    ax_market.legend()

    # マーケットグラフ（軸２、売買種類別出来高）
    ax_market_2 = ax_market.twinx()
    ax_market_2.set_ylabel('Volume', fontsize=label_fsize)
    if buy_volume:
        ax_market_2.bar(range(0, len(buy_volume)), buy_volume, color='g', alpha=0.5, label='Buy Volume')
    if sell_volume:
        ax_market_2.bar(range(0, len(sell_volume)), sell_volume, color='r', alpha=0.5, label='Sell Volume')
    ax_market_2.legend()

    # 損益グラフ（軸１、実現損益、未実現損益）
    ax_pnl = axes[1]  # type: Axes
    ax_pnl.set_title('Trade result', fontsize=title_fsize)
    ax_pnl.set_xlabel('Time', fontsize=label_fsize)
    ax_pnl.set_ylabel('Price', fontsize=label_fsize)
    if realized_pnl:
        ax_pnl.fill_between(range(0, len(realized_pnl)), realized_pnl, color='orange', alpha=0.5, linestyle='solid',
                            label='Realized PnL')
    if unrealized_pnl:
        ax_pnl.plot(range(0, len(unrealized_pnl)), unrealized_pnl, color='blue', alpha=0.5, linestyle='solid',
                    label='Unrealized Pnl')
    ax_pnl.hlines(0, xmin=0, xmax=len(realized_pnl), colors='r', linestyles='dotted')
    ax_pnl.grid()
    ax_pnl.legend()

    # 損益グラフ（軸２、保有ポジション量）
    if buy_pos_size or sell_pos_size:
        ax_pnl_2 = ax_pnl.twinx()  # type: Axes
        ax_pnl_2.set_ylabel('Position', fontsize=label_fsize)
        ax_pnl_2.bar(range(0, len(buy_pos_size)), buy_pos_size, color='g', alpha=0.5, label='Long position size')
        ax_pnl_2.bar(range(0, len(sell_pos_size)), sell_pos_size, color='r', alpha=0.5, label='Short position size')
        ax_pnl_2.legend()

    # グラフ３（トレード別損益ヒストグラム）
    pnl = []
    total_pnl = 0
    for t in trades:
        total_pnl += t.pnl
        pnl.append(total_pnl)
    ax_hist = axes[2]  # type: Axes
    ax_hist.set_title('Realized Profit and Loss Histgram', fontsize=title_fsize)
    ax_hist.set_xlabel('Price', fontsize=label_fsize)
    ax_hist.set_ylabel('Count', fontsize=label_fsize)
    if pnl:
        ax_hist.hist(pnl, bins=20, label='Realized Profit and Loss')
        ax_hist.vlines(x=0, ymin=0, ymax=max(pnl), colors='r', linestyles='dotted')

    # plt.suptitle('bakt', fontsize=32)
    # plt.subplots_adjust(hspace=0.9)
    plt.savefig('./hoge.png')
    plt.show()
