from typing import List

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from baktlib.models import Order, Execution, Position

pd.options.display.width = 300
pd.set_option('display.width', 300)


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


def print_graph(orders, result, dst):

    num_trade = result['num_of_timeframes']
    title_fsize = 22
    label_fsize = 16
    figsize = (42, 32)
    dpi = 48

    fig, axes = plt.subplots(nrows=5, ncols=1, figsize=figsize, dpi=dpi, sharex=True, sharey=False)  # type: Figure, Tuple(Axes, Axes)
    plt.suptitle(f"Back Test Report {result['datetime']} ", fontsize=18)
    plt.subplots_adjust(hspace=0, wspace=0)
    plt.margins(0, 0)

    #
    # グラフ１：相場価格、出来高、注文価格
    #

    # 軸１、相場価格
    ax_mkt = axes[1]  # type: Axes
    ax_mkt.set_ylabel('Market Price', fontsize=label_fsize)
    ax_mkt.tick_params(labelbottom='off', bottom='off')
    ax_mkt.plot(range(len(result['last_prices'])), result['last_prices'], color='blue', label='Price')

    # 軸１、注文価格
    max_order_num = 0
    for o in orders:
        max_order_num = max(max_order_num, len(o))
    for i in range(max_order_num):
        buy_prices = [os[i].price if os and len(os) > i and os[i].side == 'BUY' else None for os in orders]
        sell_prices = [os[i].price if os and len(os) > i and os[i].side == 'SELL' else None for os in orders]
    ax_mkt.plot(range(len(buy_prices)), buy_prices, '.', color='g', markersize=12, label='buy order price')
    ax_mkt.plot(range(len(sell_prices)), sell_prices, '.', color='r', markersize=12, label='sell order price')
    # ax_mkt.grid()
    ax_mkt.legend(loc='upper left')

    # 軸２、売買種類別出来高
    mbs = result['market_buy_size']
    mss = result['market_sell_size']
    ax_mkt_2 = ax_mkt.twinx()  # type: Axes
    ax_mkt_2.set_ylabel('Market Volume', fontsize=label_fsize)
    ax_mkt_2.legend(loc='upper right')
    ax_mkt_2.bar(range(len(mbs)), mbs, color='g', alpha=0.5, label='Buy Volume')
    ax_mkt_2.bar(range(len(mss)), mss, color='r', alpha=0.5, label='Sell Volume')
    ax_mkt_2.legend(loc='upper right')

    #
    # グラフ２：Realized Gain/Loss
    #

    # 軸１、実現損益
    real_g = result['realized_gain']
    unreal_g = result['realized_gain'] + result['unrealized_gain']
    ax_pnl = axes[2]  # type: Axes
    ax_pnl.tick_params(labelbottom='off', bottom='off')
    ax_pnl.set_ylabel('Price', fontsize=label_fsize)
    ax_pnl.fill_between(range(0, len(real_g)), real_g, color='blue', alpha=0.7, linestyle='solid', label='Realized Gain/Loss')
    ax_pnl.plot(range(len(unreal_g)), unreal_g, color='pink', alpha=1, linestyle='dotted', label='Unrealized Gain/Loss', linewidth=3)
    ax_pnl.hlines(0, xmin=0, xmax=len(real_g), colors='r', linestyles='dotted')
    # ax_pnl.grid()
    ax_pnl.legend(loc='upper left')

    #
    # グラフ３：ポジション、未実現損益
    #

    # 軸１、保有ポジション量
    buy_pos_size = result['buy_pos_size']
    sel_pos_size = result['sell_pos_size']
    ax_pos = axes[3]  # type: Axes
    ax_pos.set_ylabel('Size', fontsize=label_fsize)
    ax_pos.bar(range(0, len(buy_pos_size)), buy_pos_size, color='g', alpha=0.5, label='Long position size')
    ax_pos.bar(range(0, len(sel_pos_size)), sel_pos_size, color='r', alpha=0.5, label='Short position size')
    ax_pos.legend(loc='upper left')

    # 軸２、未実現損益
    ax_pos_2 = ax_pos.twinx()  # type: Axes
    ax_pos_2.set_ylabel('Unrealized PnL', fontsize=label_fsize)
    ax_pos_2.plot(range(0, len(unreal_g)), unreal_g, color='blue', alpha=1, linestyle='solid', label='Unrealized Gain/Loss')
    ax_pos_2.hlines(0, xmin=0, xmax=len(unreal_g), colors='r', linestyles='dotted')
    ax_pos_2.legend(loc='upper right')

    #
    # グラフ４：実現損益のヒストグラム
    #

    # トレード別損益ヒストグラム
    # ax_hist = axes[3]  # type: Axes
    # ax_hist.set_title('Realized Gain/Loss Per Order', fontsize=title_fsize)
    # ax_hist.set_xlabel('Price', fontsize=label_fsize)
    # ax_hist.set_ylabel('Count', fontsize=label_fsize)
    # ax_hist.hist(result['pnl_per_trade'], bins=20, color='blue', alpha=1.0, label='Realized Gain/Loss')
    # if result['pnl_per_trade']:
    #     ax_hist.vlines(x=0, ymin=0, ymax=int(max(result['pnl_per_trade']) / 2), colors='r', linestyles='solid')

    # 約定履歴受信遅延
    w_delay = result['exec_recv_delay_sec']
    ax_delay = axes[4]  # type: Axes
    ax_delay.set_ylabel('Execution delay time (sec)', fontsize=label_fsize)
    ax_delay.plot(range(len(w_delay)), w_delay, color='g', label='Execution receive delay time (sec)')
    ax_delay.legend(loc='upper left')

    # 発注遅延
    o_delay = result['order_delay_sec']
    ax_delay_2 = ax_delay.twinx()
    ax_delay_2.set_ylabel('Order delay time (sec)', fontsize=label_fsize)
    ax_delay_2.bar(range(len(o_delay)), o_delay, color='r', alpha=0.5, label='Order delay time (sec)')
    ax_delay_2.legend(loc='upper right')

    #
    # テキスト領域１（上段左側）
    #

    ax_text = axes[0]  # type: Axes
    ax_text.axis('off')
    ax_text.spines["right"].set_color("none")
    ax_text.spines["left"].set_color("none")
    ax_text.spines["top"].set_color("none")
    ax_text.spines["bottom"].set_color("none")

    fsize = 20
    label_x = 0
    value_x = num_trade / 6
    y_span = 0.1
    y = 1.0

    # 注文セクション

    # 注文回数
    ax_text.text(label_x, y, "Num of orders", fontsize=fsize)
    ax_text.text(value_x, y,
                 f"{result['num_of_orders']:,} (Limit: {result['num_of_limit_orders']:,}"
                 f", Market: {result['num_of_market_orders']:,}"
                 f" / Buy: {result['num_of_buy_orders']:,}, Sell: {result['num_of_sell_orders']:,})", fontsize=fsize)
    y -= y_span

    # 注文サイズ
    ax_text.text(label_x, y, "Order size", fontsize=fsize)
    ax_text.text(value_x, y, "{:,.3f} (Limit: {:,.3f}, Market: {:,.3f} / Average: {:.3f})"
                 .format(result['size_of_orders'], result['size_of_limit_orders'],
                         result['size_of_market_orders'], result['avg_order_size']), fontsize=fsize)
    y -= y_span

    # 注文ステータス別件数
    ax_text.text(label_x, y, "Count per status", fontsize=fsize)
    ax_text.text(value_x, y, "Completed: {:,}, Canceled: {:,}, Active: {:,}".format(result['num_of_completed_orders'],
                         result['num_of_canceled_orders'], result['num_of_active_orders']), fontsize=fsize)
    y -= y_span

    # 約定セクション
    ax_text.text(label_x, y, "Num of exec", fontsize=fsize)
    ax_text.text(value_x, y, f"{result['num_of_exec']:,}", fontsize=fsize)
    y -= y_span
    ax_text.text(label_x, y, "Exec size", fontsize=fsize)
    ax_text.text(value_x, y, f"{result['size_of_exec']:,.8} BTC", fontsize=fsize)
    y -= y_span
    ax_text.text(label_x, y, "Exec %", fontsize=fsize)
    ax_text.text(value_x, y, f"{result['exec_rate']:.2%}", fontsize=fsize)
    y -= y_span

    #
    # テキスト領域２（上段右側）
    #

    label_x = num_trade / 2
    value_x = label_x + label_x / 3
    y = 1.0

    # データ期間
    ax_text.text(label_x, y, "Data duration", fontsize=fsize)
    ax_text.text(value_x, y, f"{result['data_from'][0:16]} - {result['data_to'][0:16]}", fontsize=fsize)
    y -= y_span

    # 通貨 / データ件数 / 出来高
    ax_text.text(label_x, y, "Pair / Count / Size", fontsize=fsize)
    ax_text.text(value_x, y, f"FX_BTC_JPY / {result['data_length']:,} / {result['volume']:,.0f} BTC", fontsize=fsize)
    y -= y_span

    # トレード数
    ax_text.text(label_x, y, "Num of trade", fontsize=fsize)
    ax_text.text(value_x, y, f"{num_trade:,} (Frame: {result['timeframe_sec']:,} sec)", fontsize=fsize)
    y -= y_span

    # 損益
    pnl = result['total_pnl']
    profit = result['profit']
    loss = result['loss']
    exp = result['expected_value']
    pf = result['pf']
    ax_text.text(label_x, y, "Profit and Loss", fontsize=fsize)
    ax_text.text(value_x, y, f"{pnl:,} (Profit: {profit:,}, Loss: {loss:,}, PF: {pf:,}, Expected: {exp:,.1f})",
                 fontsize=fsize)
    y -= y_span

    # 勝率
    ax_text.text(label_x, y, "Win %", fontsize=fsize)
    ax_text.text(value_x, y, f"{result['win_rate']:.2%} (win: {result['num_of_win']:,}, "
    f"lose: {result['num_of_lose']:,}, even: {result['num_of_even']:,} / All: {result['num_of_trades']})",
                 fontsize=fsize)
    y -= y_span

    # DD
    ax_text.text(label_x, y, "DD %", fontsize=fsize)
    ax_text.text(value_x, y, "- %", fontsize=fsize)
    y -= y_span

    ax_text.text(label_x, y, "Process time", fontsize=fsize)
    ax_text.text(value_x, y, f"{__conv_htime(result['duration'])}", fontsize=fsize)

    from datetime import datetime
    timestamp = datetime.strptime(result['datetime'], '%Y-%m-%d %H:%M:%S').strftime('%Y%m%d%H%M')
    plt.savefig(dst + f"/bakt_report_{timestamp}.png")
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
