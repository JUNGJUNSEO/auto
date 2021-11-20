import pyupbit
import time
import datetime

f = open("open_api_key.txt", 'rt', encoding='UTF8')
lines = f.readlines()
access = lines[0].strip()
secret = lines[1].strip()
f.close()
upbit = pyupbit.Upbit(access, secret)


class DataFrame:
    def __init__(self, df):
        self.df = df
        self.close = df['close']

    def get_pvt(self):

        PVT = [0]
        for i in range(1, len(self.close)):
            PVT.append(((self.close.iloc[i]-self.close.iloc[i-1]) /
                        self.close.iloc[i-1])*self.df['volume'].iloc[i] + PVT[-1])
        self.df['PVT'] = PVT
        ma = self.df['PVT'].rolling(20).mean()
        ma_ewm = self.df['PVT'].ewm(span=10).mean()
        std = self.df['PVT'].rolling(20).std()
        ubb = ma + 2*std
        lbb = ma - 2*std
        return self.df['PVT'], ma_ewm, ma, ubb, lbb


class Market:
    def __init__(self, ticker, minute):
        self.ticker = ticker
        self.minute = minute

    def order_cancel(self):
        # 주문 취소
        upbit.cancel_order(upbit.get_order(self.ticker)[0]['uuid'])
        return True

    def upper(self):
        # PVT선도가 UPP보다 위에 있을 때

        df = pyupbit.get_ohlcv(self.ticker, self.minute)
        pvt, ma_ewm_pvt, ma_pvt, ubb_pvt, lbb_pvt = DataFrame(df).get_pvt()

        if pvt.iloc[-1] > ubb_pvt.iloc[-1]:
            return True

    def get_nw(self):
        df = pyupbit.get_ohlcv(self.ticker, self.minute)
        pvt, ma_ewm_pvt, ma_pvt, ubb_pvt, lbb_pvt = DataFrame(df).get_pvt()
        diff = []
        for i in range(19, len(pvt)):
            diff.append((i, ubb_pvt[i]-lbb_pvt[i]))
        gap_start = diff[19][1]
        for i, gap in diff:
            if gap / gap_start > 1:
                gap_start = gap
                nw = True
            if gap_start / gap > 1:
                gap_start = gap
                nw = False
        return nw


def buy(krw_balance):
    # 매수
    tickers = pyupbit.get_tickers(fiat='KRW')

    chosen_ticker = list()
    for ticker in tickers:
        df_day = pyupbit.get_ohlcv(ticker, "day", count=100)

        # 거래일이 20일 미만일 경우 continue
        if len(df_day) < 20:
            continue
        #
        if Market(ticker, 'minute60').upper() and Market(ticker, 'minute30').upper() and Market(ticker, 'minute15').upper() and Market(ticker, 'minute10').uppper() and Market(ticker, 'minute5').uppper() and not Market(ticker, 'minute3').get_nw():
            chosen_ticker.append(ticker)
        time.sleep(0.1)
    print(chosen_ticker)
    # 매수 시도
    while chosen_ticker:
        for ticker in chosen_ticker:

            # 매수 시도(0.1 초마다 조건을 확인 후 시도)
            if Market(ticker, 'minute3').get_nw() and Market(ticker, 'minute3').upper():

                if upbit.buy_market_order(ticker, krw_balance):
                    print(f'{ticker}의 매수 주문이 들어갔습니다.')
                    time.sleep(60)

            else:
                print(f'{ticker} 구매 조건에 맞지 않습니다.')

            # 주문 외 요청은 초당 30번 가능
            time.sleep(0.2)


def sell(ticker):
    # 매도
    while True:

        # 매도가 된 경우 return
        if not upbit.get_balance(ticker):
            return

        current_price = pyupbit.get_current_price(ticker)
        avg_buy_price = upbit.get_avg_buy_price(ticker)
        coin_balance = upbit.get_balance(ticker)
        now = datetime.datetime.now()

        if not Market(ticker, 'minute10').uppper():
            upbit.sell_limit_order(ticker, current_price, coin_balance)

        print(f'현재시간: {now} 구매 종목: {ticker} 수량: {coin_balance} 구매가: {avg_buy_price} 현재가: {current_price} 수익률: {round((current_price/avg_buy_price)*100, 2)} %')

        time.sleep(1)


while True:
    balances = upbit.get_balances()
    krw_balance = float(balances[0]['balance'])
    # 매수된 ticker
    if len(balances) > 1:
        ticker = 'KRW-' + balances[1]['currency']

        sell(ticker)

        continue
    print('seo')
    # 매수 주문
    buy(10000*0.9995)
