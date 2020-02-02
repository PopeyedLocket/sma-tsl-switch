import time
import subprocess
import sys
sys.path.insert(0, './')
from poloniex import poloniex
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
pd.set_option('display.max_rows', 8)
pd.set_option('display.max_columns', 100)
pd.set_option('display.width', 1000)
import numpy as np



''' NOTES

    STRATEGY DESCRIPTION:

        Switch back and forth between a long and short TSL (just tracking, no investment).
        When SMA is going up, invest in the long TSL, and when SMA is going down invest in the short TSL.

    EXPERIMENT DESCRIPTION:
    
        for each coin in COINS:
            for each sma window length w in SMA_WINDOWS:

                high-light when the sma is + slope and when its - slope
                    + is green
                    - is red

                for each TSL value (percent offset from current price) x in TSL_VALUES:

                    determine the p/l for each section of the SMA trend (when it is with it, and when it is against it)

                        when the sma trend direction switches we have no idea how long its going to stay in this direction
                            when it lasts a short time we take a loss if we invest in the beginning
                            when it lasts a long time we make a profit if we invest in the beginning
                            when it lasts a short time we avoid taking a loss if we don't invest in the beginning
                            when it lasts a long time we missed making a profit if we don't invest in the beginning

                            if we choose a sma window that is really large and a tsl value that is really small relative
                            to the sma window, the sma trend will stay a long time

                            We could to a min abs(+/-) threshold > 0 to invest than
                            And just have it immediately invest
                            And just have it wait for the next tsl to trigger an investment
                            TRY BOTH


                    plot 1: price, sma, trend, highlight when sign_of_sma_slope == sign_of_trend_slope, tsl_long, tsl_short
                    plot 2: current p/l of tsl_long and tsl_short
                    plot 3: total p/l of tsl_long, total p/l of tsl_short, net p/l

        Hopefully the profits made when the SMA is correct outway the losses when the SMA is wrong.
        I expect an x value significantly smaller than w will perform the best
        because we're trying to catch the volitility of a trend.

    TO DO:

        plot tsls to verify they are working properly
            its basically done ... just:
                skim through it
                clean up the plot helper fn a bit
                then move on

        do tsl pl

        then make backup_tsl_test2.py
            update description to explain different between first backup and 2nd
                1st backup has tsl constant on both sides
                2nd backup has tsls switching back and forth

        then make it so that investments are made in tandem with the sma
            and explain the different between the tests

    IDEA:


        In the market there are people with different sized portfolios
        If someone who has large portolio goes long on an asset
        the ...

            ... Use bollinger bands!

            for w in WINDOW_SIZES:
                
                if standard deviation of the price is smooth and consistent
                (aka if the boolinger band's value hasn't changed that much over the timespan of the windows)
                (aka if the sum of the all the changes in volitility (aka change in standard deviation of the price)
                over the timespan of the window is close to zero ... )

                AND

                The the SMA slope is above a threshold of Y

                    Then set a trailing stop loss at an x value of 2*pi (95 % chance it doesn't get triggered)
                
            Note:
                if Y is steep we'll be late to buy in
                if Y is shallow we'll take more losses
                The larger the slope the faster it will break
                if Y is zero
                    this would then be a predictive algorithm
                        and trades would be made based off likelihoods, not 


        what if the distance the next timestep's value is from the previous timesteps moving average the more exponential the weights will become.
        A difference of 0 from the previous moving average will weight them equally for a simple moving average, but a large distance will make the
        weights very exponential. The equation for could be:

                w[i] = t[i] ^ (1 + d)

                d = absolute value of percentage distance of current timestep's price from previous timestep's moving average 
                        this value will vary from 0.00 to 1.00

            ... this could yeild an SMA that doesn't lag !!!

            ... or not, the lag is what makes it useful in the first place because it smooths out the smaller scale volitility

    '''

# constants
QUERI_POLONIEX = False
BACKTEST_DATA_FILE = './price_data_multiple_coins-BTC_ETH_XRP_LTC_ZEC_XMR_STR_DASH_ETC-2hr_intervals-08_01_2018_7am_to_08_01_2019_4am.csv'
LONG_TSLS_FILES = './data/long/'
SHORT_TSLS_FILES = './data/short/'
TETHER = 'USDT'
COINS = [
    'BTC',
    'ETH',
    'XRP',
    'LTC',
    'ZEC',
    'XMR',
    'STR',
    'DASH',
    'ETC',
]
COINS = ['ETH']
PAIRS = [TETHER + '_' + coin for coin in COINS]
TF = 0.0025 # TF = trading fee
# SMA_WINDOWS = [9, 19, 29, 39, 49, 59, 69, 79, 89, 99] # most accurate if they're all odd integers
SMA_WINDOWS = [100]#[10, 20, 30, 40, 50, 100, 200, 300, 400, 500] # most accurate if they're all odd integers
TSL_VALUES = [0.05]#[0.0025, 0.005, 0.01, 0.025, 0.05, 0.10, 0.20]

# pprint constants
DEBUG_WITH_CONSOLE = True
DEBUG_WITH_LOGFILE = True
DEBUG_LOGFILE_PATH = './log.txt'
DEFAULT_INDENT = '|  '
DEFAULT_DRAW_LINE = False


# pretty print the string
# arguments:
#   string = what will be printed
#   indent = what an indent looks like
#   num_indents = number of indents to put in front of the string
#   new_line_start = print a new line in before the string
#   new_line_end = print a new line in after the string
#   draw_line = draw a line on the blank line before or after the string
def pprint(string='',
    indent=DEFAULT_INDENT,
    num_indents=0,
    new_line_start=False,
    new_line_end=False,
    draw_line=DEFAULT_DRAW_LINE):

    if DEBUG_WITH_CONSOLE:

        total_indent0 = ''.join([indent] * num_indents)
        total_indent1 = ''.join([indent] * (num_indents + 1))

        if new_line_start:
            print(total_indent1 if draw_line else total_indent0)

        print(total_indent0 + string)

        if new_line_end:
            print(total_indent1 if draw_line else total_indent0)

    if DEBUG_WITH_LOGFILE:

        f = open(DEBUG_LOGFILE_PATH, 'a')

        new_indent = '\t'

        total_indent0 = ''.join([new_indent] * num_indents)
        total_indent1 = ''.join([new_indent] * (num_indents + 1))

        if new_line_start:
            f.write((total_indent1 if draw_line else total_indent0) + '\n')

        # all these regex's are to make tabs in the string properly
        # asdfasdf is to make sure there's no false positives
        # when replacing the indent
        indent2 = re.sub('\|', 'asdfasdf', indent)
        string = re.sub(indent2, new_indent, re.sub('\|', 'asdfasdf', string))
        f.write(total_indent0 + string + '\n')

        if new_line_end:
            f.write((total_indent1 if draw_line else total_indent0) + '\n')

        f.close()


# setup connection to servers
def poloniex_server():

    API_KEY = '...'
    SECRET_KEY = '...'

    return poloniex(API_KEY, SECRET_KEY)

# get backtesting data
def get_past_prices_from_poloniex(
    startTime, endTime, period, num_periods, conn, save=True):

    # get history data from startTime to endTime
    startTime_unix = time.mktime(startTime.timetuple())
    endTime_unix = time.mktime(endTime.timetuple())

    # get price history data for each pair into a dictionary
    dct = { pair :
        conn.api_query("returnChartData", {
            'currencyPair': pair,
            'start': startTime_unix,
            'end': endTime_unix,
            'period': period
        }) for pair in PAIRS}

    # create 'unix_date' and 'datetime' columns
    df = pd.DataFrame()
    dates = [dct[PAIRS[0]][t]['date'] for t in num_periods]
    df['unix_date'] = pd.Series(dates)
    df['datetime'] = df['unix_date'].apply(
        lambda unix_timestamp : \
        datetime.fromtimestamp(unix_timestamp))

    # remove unneeded data
    for pair, data in dct.items():
        coin = pair[len(TETHER + '_'):]
        data2 = [data[t]['close'] for t in num_periods]
        df[coin] = pd.Series(data2)

    # save df to file
    if save:
        df.to_csv(BACKTEST_DATA_FILE)

    return df
def get_past_prices_from_csv_file():

    # get data from csv file
    df = pd.read_csv(BACKTEST_DATA_FILE, index_col=[0])

    # convert datetime column from string to datetime object
    df['datetime'] = df['datetime'].apply(
        lambda s : datetime.strptime(s, '%Y-%m-%d %H:%M:%S'))

    return df

def init_dct(df):

    # create dct and put time in its own df
    dct = {
        'time_df'   : df[['unix_date', 'datetime']],
        'asset_dct' : {}
    }

    # put price data its own df
    for i, coin in enumerate(COINS):
        dct['asset_dct'][coin] = {
            'price_df' : pd.DataFrame({
                'price'     : df[coin],
                'pct_chng'  : df[coin].pct_change()
            })
        }

    # later stuff (sma and tsl) will go in their own dfs as well
    # no indeces will be dropped and reset
    return dct

def get_sma_dct(dct, output_sma_data=False):

    pct_with_trend_df = pd.DataFrame(columns=COINS, index=SMA_WINDOWS)
    pct_with_trend_df.index.name = 'sma_window   '
    total_ave_pct_with_trend = 0

    for i, coin in enumerate(COINS):
        
        sma_dct = {}

        for j, w in enumerate(SMA_WINDOWS):

            # create a SMA from t0 to t0-w
            price_series = dct['asset_dct'][coin]['price_df']['price']
            sma_label = '%sp_SMA' % w
            sma_series = price_series.rolling(window=w).mean()

            # calculate the trend (another SMA from t0+w/2 to t0-w/2)
            # (by shifting the SMA up w/2 indeces and clipping the ends)
            # ... the trend is an SMA with no lag (impossible to calculate in live trading)
            trend_label = '%sp_trend' % w
            trend_series = sma_series.shift(periods=-int(w/2))

            # determine when the SMA has a similar slope to the trend (both positive or both negative)
            # and when they have opposite slope (one positive one negative)
            sma_with_trend_bool_series = \
                ((sma_series.diff() > 0) & (trend_series.diff() > 0)) | \
                ((sma_series.diff() < 0) & (trend_series.diff() < 0))

            # calculate PERCENT of the time the SMA is with the trend
            pct_with_trend = sma_with_trend_bool_series.value_counts(normalize=True).loc[True] * 100
            pct_with_trend_df.at[w, coin] = pct_with_trend
            total_ave_pct_with_trend += pct_with_trend

            # calculate when the sma has a positive slope
            sma_positive_slope_bool_series = sma_series.diff() > 0

            # also ... create the boolinger bands for this SMA
            std_dev_series = price_series.rolling(window=w).std()

            sma_w_dct = {
                'sma_label'      : sma_label,
                'trend_label'    : trend_label,
                'pct_with_trend' : pct_with_trend,
                'df'             : pd.DataFrame({
                    'trend'                 : trend_series,
                    'sma'                   : sma_series,
                    'sma_with_trend'        : sma_with_trend_bool_series,
                    'sma_positive_slope'    : sma_positive_slope_bool_series,
                    'std_dev'               : std_dev_series,
                    'bollinger_upper_bound' : sma_series + 2 * std_dev_series,
                    'bollinger_lower_bound' : sma_series - 2 * std_dev_series
                })
            }
            sma_dct[w] = sma_w_dct

        # print(coin)
        # for k, v in sma_dct[9].items():
        #     print(k)
        #     print(v)
        #     print()
        # input()

        dct['asset_dct'][coin]['sma_dct'] = sma_dct

    if output_sma_data:

        plot_sma_data(dct)

        print('\nPercent of the time the SMA is with the trend:\n')
        print(pct_with_trend_df)

        total_ave_pct_with_trend /= (len(COINS) * len(SMA_WINDOWS))
        print('\nTotal average percent = %.2f %%\n' % total_ave_pct_with_trend)


    return dct
def plot_sma_data(dct):
    for i, coin in enumerate(COINS):
        price_series = dct['asset_dct'][coin]['price_df']['price']
        for j, w in enumerate(SMA_WINDOWS):
            sma_w_dct = dct['asset_dct'][coin]['sma_dct'][w]
            skip_plotting = plot_sma_data_helper(coin, price_series, sma_w_dct)
            if skip_plotting:
                return
def plot_sma_data_helper(coin, price_series, sma_w_dct):

    fig, axes = plt.subplots(figsize=(11, 6))
    
    axes.plot(price_series,  label='price')
    axes.plot(sma_w_dct['df']['sma'],   label=sma_w_dct['sma_label'])
    axes.plot(sma_w_dct['df']['trend'], label=sma_w_dct['trend_label'])

    # highlight x ranges where the SMA is with the trend
    ranges_sma_with_trend = []
    range_start, range_end = None, None
    for index, value in sma_w_dct['df']['sma_with_trend'].items():
        if value: # True
            if range_start != None:
                pass # continue on ...
            else: # just starting
                range_start = index # started new range
        else: # False
            if range_start != None: # found the end
                range_end = index
                ranges_sma_with_trend.append((range_start, range_end))
                range_start, range_end = None, None
            else:
                pass # continue on ... 
    for range_start, range_end in ranges_sma_with_trend:
        # we have to subtract one (as seen below)
        # b/c something to do with the plotting
        # but the df is correct
        axes.axvspan(range_start -1, range_end -1, facecolor='gray', alpha=0.5)

    # set title
    axes.title.set_text(
        '%s/%s %s is w/ the %s %.2f %% of the time' % (
            coin, TETHER,
            sma_w_dct['sma_label'],
            sma_w_dct['trend_label'],
            sma_w_dct['pct_with_trend']))

    # create legend
    plt.legend(loc=(1.02, 0.40))

    # write text explaining when SMA is with trend
    axes.text(
        1.02, 0.05,
        'time when SMA is\nwith the trend',
        transform=axes.transAxes,
        fontsize=10)

    # place grey rectangle box above text
    axes.text(
        1.02, 0.15, '            ',
        transform=axes.transAxes,
        bbox=dict(
            boxstyle='square',
            facecolor='lightgray',
            edgecolor='none'
        ))

    # adjust subplots and display it
    ''' https://matplotlib.org/3.1.1/api/_as_gen/matplotlib.pyplot.subplots_adjust.html
    subplots_adjust(left=None, bottom=None, right=None, top=None, wspace=None, hspace=None)
        left  = 0.125  # the left side of the subplots of the figure                      percentage
        right = 0.9    # the right side of the subplots of the figure                     percentage
        bottom = 0.1   # the bottom of the subplots of the figure                         percentage
        top = 0.9      # the top of the subplots of the figure                            percentage
        wspace = 0.2   # the amount of width reserved for blank space between subplots    number
        hspace = 0.2   # the amount of height reserved for white space between subplots   number
        '''
    plt.subplots_adjust(
        left   = 0.10,
        right  = 0.85,
        bottom = 0.10,
        wspace = 0.25, hspace=0.5)
    plt.show()

    # determine if we want to continue to plot SMAs or not
    user_input = input('Press s to skip to end of test, or any other key to continue: ')
    return (user_input == 's' or user_input == 'S')

def get_tsl_dct(dct, output_tsl_data=False):

    for i, (coin, coin_data) in enumerate(dct['asset_dct'].items()):
        # print('coin = %s' % coin)
        price_df = coin_data['price_df']
        # print('price_df')
        # print(price_df)
        for j, (w, sma_w_dct) in enumerate(coin_data['sma_dct'].items()):
            # print('sma_window = %d' % int(w))
            sma_df = sma_w_dct['df']
            # print('sma_w_dct')
            # print(sma_w_dct)

            tsl_dct = {}       
            for x in TSL_VALUES:
                # print('x = %.2f' % x)
                tsl_x_dct = get_tsl_dct_helper(coin, w, x, price_df['price'])
                tsl_dct[x] = tsl_x_dct

            dct['asset_dct'][coin]['sma_dct'][w]['tsl_dct'] = tsl_dct

    if output_tsl_data:

        plot_tsl_data(dct)

    return dct
def get_tsl_dct_helper(coin, w, x, price_series, verbose=False):

    columns = {
        'enter_price',   # the price that the trade was entered at
        'stop_loss',     # the price that it will take to exit the trade
        'dxv',           # dxv = dx VALUE (not the percentage), aka difference between enter_price and stop_loss
        'cur_price_pl',  # profit/loss (pl) of the current actual price
        'cur_sl_pl',     # profit/loss (pl) of the current stop loss
        'tot_price_pl',  # profit/loss (pl) of the total (from beginning until now) of the current price
        'tot_sl_pl'      # profit/loss (pl) of the total (from beginning until now) of the current stop loss
    }
    long_df = pd.DataFrame(columns=columns)
    short_df = pd.DataFrame(columns=columns)

    tracking_long = True
    for i, price in enumerate(price_series):

        if verbose:
            print('-' * 100)
            print('i = %d   price = %.4f' % (i, price))
            print('TRACKING LONG' if tracking_long else 'TRACKING SHORT')

        # if your tracking long, update the long function 1st and the short tsl 2nd, and vice versa
        if tracking_long:

            # update long tsl 1st
            triggered = update_long_tsl(x, long_df, price, i, init_tsl=i==0, verbose=verbose)

            # then update the short tsl 2nd
            if not triggered:
                short_df.at[i, 'dxv']         = np.nan
                short_df.at[i, 'stop_loss']   = np.nan
                short_df.at[i, 'enter_price'] = np.nan

            else: # if the long tsl was triggered, start tracking short
                tracking_long = False
                _ = update_short_tsl(x, short_df, price, i, init_tsl=True, verbose=verbose)

        else: # tracking short

            triggered = update_short_tsl(x, short_df, price, i, verbose=verbose)
            
            if not triggered:
                long_df.at[i, 'dxv']         = np.nan
                long_df.at[i, 'stop_loss']   = np.nan
                long_df.at[i, 'enter_price'] = np.nan

            else: # if the short tsl was triggered, start tracking long
                tracking_long = True
                _ = update_long_tsl(x, long_df, price, i, init_tsl=True, verbose=verbose)

        if verbose:
            print('\nlong_df')
            print(long_df)

            print('\nshort_df')
            print(short_df)

        # input()

    return {
        'long_df'  : long_df,
        'short_df' : short_df
    }
def update_long_tsl(x, df, price, i, init_tsl=False, verbose=False):

    # update TSL variables
    sl   = df.at[i, 'stop_loss']   = df.loc[i-1, 'stop_loss']   if i != 0 else np.nan  # sl = (previous) stop loss
    dxv  = df.at[i, 'dxv']         = df.loc[i-1, 'dxv']         if i != 0 else np.nan
    entp = df.at[i, 'enter_price'] = df.loc[i-1, 'enter_price'] if i != 0 else np.nan
    triggered = False

    if init_tsl:
        if verbose: print('initializing long tsl')
        dxv = df.at[i, 'dxv']   = price * x  # update dxv
        df.at[i, 'stop_loss']   = price - dxv # set new tsl
        df.at[i, 'enter_price'] = price # update new entrance price
    elif price <= sl:  # stop loss triggered!
        if verbose: print('long tsl: stop loss triggered!')
        triggered = True
    elif price <= sl + dxv and price > sl: # else it stayed within its stop loss
        if verbose: print('long tsl: price stayed within its stop loss')
        # pass
    elif price > sl + dxv: # else it went up, thus dragging the stop loss up also
        if verbose: print('long tsl: price went up')
        df.at[i, 'stop_loss'] = price - dxv
    else:
        if verbose: print('LONG TSL FUCKED UP!')

    return triggered
def update_short_tsl(x, df, price, i, init_tsl=False, verbose=False):

    # update TSL variables
    sl   = df.at[i, 'stop_loss']   = df.loc[i-1, 'stop_loss']   if i != 0 else np.nan  # sl = (previous) stop loss
    dxv  = df.at[i, 'dxv']         = df.loc[i-1, 'dxv']         if i != 0 else np.nan
    entp = df.at[i, 'enter_price'] = df.loc[i-1, 'enter_price'] if i != 0 else np.nan
    triggered = False

    if init_tsl:
        if verbose: print('initializing short tsl')
        dxv = df.at[i, 'dxv']   = price * x  # update dxv
        df.at[i, 'stop_loss']   = price + dxv # set new tsl
        df.at[i, 'enter_price'] = price # update new entrance price
    elif price >= sl:  # stop loss triggered!
        if verbose: print('short tsl: stop loss triggered!')
        triggered = True
    elif price >= sl - dxv and price < sl: # else it stayed within its stop loss
        if verbose: print('short tsl: price stayed within its stop loss')
        # pass
    elif price < sl - dxv: # else it went down, thus dragging the stop loss down also
        if verbose: print('short tsl: price went down')
        df.at[i, 'stop_loss'] = price + dxv
    else:
        if verbose: print('SHORT TSL FUCKED UP')

    return triggered
def plot_tsl_data(dct):

    # create date_labels and x_tick_indeces
    first_date = df['datetime'].iloc[0]
    date_fmt = '%m-%d-%Y'
    date_labels = [first_date.strftime(date_fmt)]
    x_tick_indeces = [0]
    previous_month = first_date.strftime('%m')
    for i, row in df.iterrows():
        current_month = row['datetime'].strftime('%m')
        if current_month != previous_month:
            date_labels.append(row['datetime'].strftime(date_fmt))
            x_tick_indeces.append(i)
        previous_month = current_month
    last_date = df['datetime'].iloc[-1]
    if last_date != date_labels[-1]:
        date_labels.append(last_date.strftime(date_fmt))
        x_tick_indeces.append(df['datetime'].tolist().index(last_date))
    # for i, l in zip(x_tick_indeces, date_labels):
    #     print(i, l)

    # plot each TSL
    for i, coin in enumerate(COINS):
        price_series = dct['asset_dct'][coin]['price_df']['price']
        for j, w in enumerate(SMA_WINDOWS):
            sma_w_dct = dct['asset_dct'][coin]['sma_dct'][w]
            for k, x in enumerate(TSL_VALUES):
                tsl_x_dct = sma_w_dct['tsl_dct'][x]
                skip_plotting = plot_tsl_data_helper(date_labels, x_tick_indeces, coin, price_series, sma_w_dct, x, tsl_x_dct)
                if skip_plotting:
                    return
def plot_tsl_data_helper(date_labels, x_tick_indeces, coin, price_series, sma_w_dct, x, tsl_x_dct):

    long_x_str,  long_df  = '%s' % (100*x), tsl_x_dct['long_df']
    short_x_str, short_df = '%s' % (100*x), tsl_x_dct['short_df']

    sma_data = sma_w_dct['df']['sma']
    sma_lbl  = '%s' % sma_w_dct['sma_label']

    bollinger_lbl = 'bollinger bands (2 std devs)'
    bollinger_upper_bound = sma_w_dct['df']['bollinger_upper_bound']
    bollinger_lower_bound = sma_w_dct['df']['bollinger_lower_bound']

    fig, ax = plt.subplots(
        nrows=3, ncols=1,
        num='stop loss = %s' % (long_x_str),
        figsize=(10.5, 6.5),
        sharex=True, sharey=False)

    _legend_loc, _b2a = 'center left', (1, 0.5) # puts legend ouside plot

    ax[0].plot(price_series,          color='black', label='price')
    ax[0].plot(sma_data,              color='blue',  label=sma_lbl)
    ax[0].plot(bollinger_upper_bound, color='blue',  label=bollinger_lbl, linestyle='--')
    ax[0].plot(bollinger_lower_bound, color='blue',  label=None, linestyle='--')
    # blink gym $15/month
    ax[0].plot(long_df['stop_loss'],  color='green', label='%.1f %% long TSL ' % x)
    ax[0].plot(short_df['stop_loss'], color='red',   label='%.1f %% short TSL ' % x)
    ax[0].legend(loc=_legend_loc, bbox_to_anchor=_b2a)
    ax[0].grid()
    # ax[0].yaxis.grid()  # draw horizontal lines
    ax[0].yaxis.set_zorder(-1.0)  # draw horizontal lines behind histogram bars
    ax[0].set_title('Price, SMA, and TSL Chart')
    ax[0].set_xticks(x_tick_indeces)
    ax[0].set_xticklabels('')

    # highlight SMA slope + green
    # highlight SMA slope - red
    def highlight_sma_slope(up=True, color='green'):
        ranges_sma_direction = []
        range_start, range_end = None, None
        for index, value in sma_w_dct['df']['sma_positive_slope'].items():
            if value == up: # True
                if range_start != None:
                    pass # continue on ...
                else: # just starting
                    range_start = index # started new range
            else: # False
                if range_start != None: # found the end
                    range_end = index
                    ranges_sma_direction.append((range_start, range_end))
                    range_start, range_end = None, None
                else:
                    pass # continue on ... 
        for range_start, range_end in ranges_sma_direction:
            ax[0].axvspan(range_start, range_end, color=color, alpha=0.5)
    highlight_sma_slope(up=True,  color='green')
    highlight_sma_slope(up=False, color='red')

    # ax[1].plot(long_df['cur_price_pl'],  color='green', label='Long Current Stop Loss P/L')
    # ax[1].plot(short_df['cur_price_pl'], color='red',   label='Short Current Stop Loss P/L')
    # ax[1].legend(loc=_legend_loc, bbox_to_anchor=_b2a)
    # ax[1].grid()
    # # ax[1].yaxis.grid()  # draw horizontal lines
    # # ax[1].yaxis.set_zorder(-1.0)  # draw horizontal lines behind histogram bars
    # ax[1].set_title('Current TSL Profit/Loss')
    # ax[1].set_xticks(x_tick_indeces)
    # ax[1].set_xticklabels('')
    # ax[1].yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0, decimals=1))

    # ax[2].plot(long_df['tot_sl_pl'],  color='green', label='Total Long Stop Loss P/L')
    # ax[2].plot(short_df['tot_sl_pl'], color='red',   label='Total Short Stop Loss P/L')
    # ax[2].legend(loc=_legend_loc, bbox_to_anchor=_b2a)
    # ax[2].grid()
    # # ax[2].yaxis.grid()  # draw horizontal lines
    # ax[2].yaxis.set_zorder(-1.0)  # draw horizontal lines behind histogram bars
    # ax[2].set_title('Total TSL Profit/Loss')
    # ax[2].set_xticks(x_tick_indeces)
    # ax[2].set_xticklabels(date_labels, ha='right', rotation=45)  # x axis should show date_labeles
    # ax[2].yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0, decimals=1))

    # plt.tight_layout()
    fig.subplots_adjust(
        right=0.75,
        left=0.075,
        bottom=0.15,
        top=0.95) # <-- Change the 0.02 to work for your plot.

    plt.show()

    # determine if we want to continue to plot SMAs or not
    user_input = input('Press s to skip to end of test, or any other key to continue: ')
    return (user_input == 's' or user_input == 'S')

def get_tsl_dct_from_csv_files(coin, df0, tsl_vals):
    dct = {
        'price' : df0['price'],
        'long'  : {
            '%.2f%%' % (100*x) :
                pd.read_csv(
                    LONG_TSLS_FILES + coin + '/long%.2f.csv' % (100*x),
                    index_col=[0])
            for x in tsl_vals},
        'short' : {
            '%.2f%%' % (100*x) :
                pd.read_csv(
                    SHORT_TSLS_FILES + coin + '/short%.2f.csv' % (100*x),
                    index_col=[0])
            for x in tsl_vals}
    }
    return dct

def print_dct(dct):

    # print(dct['asset_dct']['BTC'])
    # return

    print('time_df:')
    print(dct['time_df'])

    print('\nasset_dct:')
    for i, (coin, coin_data) in enumerate(dct['asset_dct'].items()):
        print('coin: %s' % coin)
        price_df = coin_data['price_df']
        print('price_df:')
        print(price_df)
        print('sma_dct:')
        for j, (w, sma_dct) in enumerate(coin_data['sma_dct'].items()):
            print('sma_window: %d' % int(w))
            sma_df = sma_dct['df']
            print('sma_w_dct:')
            for k,v in sma_dct.items():
                print(k)
                print(v)
                print()

            return


if __name__ == '__main__':

    conn = poloniex_server()

    # variables
    startTime = datetime(2018, 8, 1, 0, 0, 0)  # year, month, day, hour, minute, second
    endTime   = datetime(2019, 8, 1, 0, 0, 0)
    # period = duration of time steps between rebalances
    #   300 s   900 s    1800 s   7200 s   14400 s   86400 s
    #   5 min   15 min   30 min   2 hrs    4 hrs     1 day
    period = 2 * 60 * 60  # duration of intervals between updates

    # determines the proper number of time steps from startTime to endTime for the given period
    num_periods = range(int((endTime - startTime).total_seconds() / period))

    # import backtest data of COIN1 and COIN2 pair
    # columns=[unix_date, datetime, BTC, ETH, XRP, LTC, ZEC, XMR, STR, DASH, ETC]
    df = get_past_prices_from_poloniex(startTime, endTime, period, num_periods, conn) \
        if QUERI_POLONIEX else get_past_prices_from_csv_file()

    # initialize dct object with price data
    dct = init_dct(df)

    # calculate SMA data
    dct = get_sma_dct(dct, output_sma_data=False)

    # get TSL data
    dct = get_tsl_dct(dct, output_tsl_data=True)

    sys.exit()






    pct_with_trend_df = pd.DataFrame(columns=COINS, index=SMA_WINDOWS)
    pct_with_trend_df.index.name = 'sma_window   '
    total_ave_pct_with_trend = 0
    p = True # if p: # plot, else don't plot
    for i, (coin, df) in enumerate(dct.items()):
        for j, w in enumerate(SMA_WINDOWS):

            # Create a SMA from t0 to t0-w
            col1_lbl = '%sp_SMA' % w
            df[col1_lbl] = df['price'].rolling(window=w).mean()

            # Create another SMA from t0+w/2 to t0-w/2
            # (by shifting the real SMA up w/2 indeces and clipping the ends)
            # ... this 2nd SMA will have no lag (but impossible to calculate in live trading)
            col2_lbl = '%sp_trend' % w
            df[col2_lbl] = df[col1_lbl].shift(periods=-int(w/2))
            nan_at_beginning = list(range(int(w-1))) # OR do int(w/2) to clip the col2_lbl
            nan_at_end = list(map(lambda i : (df.shape[0]-1) - i, list(range(int(w/2)))[::-1]))
            indeces_to_clip = nan_at_beginning + nan_at_end
            df.drop(indeces_to_clip, inplace=True) # remove first row (b/c it has a NaN value)
            df.reset_index(drop=True, inplace=True) # reset index accordingly

            # Determine when both SMAs have similar slope (both positive or both negative)
            # and when they have opposite slope (one positive one negative).
            #     when they have similar slope, the 1st SMA is with the trend,
            #     when they have opposite slope, the 1st SMA hasn't realized the trend shift yet.
            df['sma_with_trend'] = \
                ((df[col1_lbl].diff() > 0) & (df[col2_lbl].diff() > 0)) | \
                ((df[col1_lbl].diff() < 0) & (df[col2_lbl].diff() < 0))
            df.drop([0], inplace=True) # remove first row b/c the diff has an NaN here
            df.reset_index(drop=True, inplace=True) # reset index accordingly

            # calculate percent of the time the SMA is with the trend
            pct_with_trend = df['sma_with_trend'].value_counts(normalize=True).loc[True] * 100
            pct_with_trend_df.at[w, coin] = pct_with_trend
            total_ave_pct_with_trend += pct_with_trend

            # highlight when the SMA slope is + green
            # highlight when the SMA slope is - red
            df['sma_positive_slope'] = df[col1_lbl].diff()# > 0

            # do tsl strategy
            tsl_dct = get_tsl_dct_from_price_iteration(coin, df, w, TSL_VALUES)
            # tsl_dct = get_tsl_dct_from_csv_files(coin, df, TSL_VALUES)
            plot_tsl_dct(TSL_VALUES, tsl_dct, df, col1_lbl)

            print('endddd')
            sys.exit()

            # # plot the price, SMA and trend,
            # # and highlight the regions where the sma is with the trend
            # # and create a legend labeling everything and outputting the
            # # percentage of the time the SMA is with the trend            
            # if p:
            #     fig, axes = plt.subplots(figsize=(11, 6))
            #     axes.plot(df['price'],  c='black', label='price')
            #     axes.plot(df[col1_lbl], c='blue',  label=col1_lbl)
            #     axes.plot(df[col2_lbl], c='cyan', label=col2_lbl)
            #     ranges_sma_with_trend = []
            #     range_start, range_end = None, None
            #     for index, value in df['sma_with_trend'].items():
            #         if value: # True
            #             if range_start != None:
            #                 pass # continue on ...
            #             else: # just starting
            #                 range_start = index # started new range
            #         else: # False
            #             if range_start != None: # found the end
            #                 range_end = index
            #                 ranges_sma_with_trend.append((range_start, range_end))
            #                 range_start, range_end = None, None
            #             else:
            #                 pass # continue on ... 
            #     for range_start, range_end in ranges_sma_with_trend:
            #         plt.axvspan(range_start, range_end, color='gray', alpha=0.5)
            #     axes.title.set_text(
            #         '%s/%s %s is w/ the %s %.2f %% of the time' % (
            #             coin, TETHER, col1_lbl, col2_lbl, pct_with_trend))                
            #     plt.legend(loc=(1.02, 0.40))
            #     # adjust subplots and display it
            #     ''' https://matplotlib.org/3.1.1/api/_as_gen/matplotlib.pyplot.subplots_adjust.html
            #     subplots_adjust(left=None, bottom=None, right=None, top=None, wspace=None, hspace=None)
            #         left  = 0.125  # the left side of the subplots of the figure                      percentage
            #         right = 0.9    # the right side of the subplots of the figure                     percentage
            #         bottom = 0.1   # the bottom of the subplots of the figure                         percentage
            #         top = 0.9      # the top of the subplots of the figure                            percentage
            #         wspace = 0.2   # the amount of width reserved for blank space between subplots    number
            #         hspace = 0.2   # the amount of height reserved for white space between subplots   number
            #         '''
            #     plt.subplots_adjust(
            #         left   = 0.10,
            #         right  = 0.85,
            #         bottom = 0.10,
            #         wspace = 0.25, hspace=0.5)

            #     plt.show()
            #     user_input = input('Press s to skip to end of test, or any other key to continue: ')
            #     p = not (user_input == 's' or user_input == 'S')


    print('\nPercent of the time the SMA is with the trend:\n')
    print(pct_with_trend_df)

    total_ave_pct_with_trend /= (len(COINS) * len(SMA_WINDOWS))
    print('\nTotal average percent = %.2f %%\n' % total_ave_pct_with_trend)

