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

    def get_macd(self):
        '''
        Golden Cross MACD and MACD선이 증가 할 때

        '''
        ma5_ema = self.close.ewm(span=5).mean()
        ma20_ema = self.close.ewm(span=20).mean()

        # MACD
        macd = ma5_ema - ma20_ema
        macd_signal = macd.ewm(span=5).mean().iloc[-1]

        if macd.iloc[-1] > macd_signal and macd.iloc[-1] > macd.iloc[-2]:
            return True

    def get_bb(self):
        '''
        볼린저밴드

        '''
        # 상한선 (UBB) : 중심선 + (표준편차 × 2)
        # 하한선 (LBB) : 중심선 - (표준편차 × 2)
        ma = self.close.rolling(20).mean()
        std = self.close.rolling(20).std()
        ubb = ma.iloc[-1] + 2*std.iloc[-1]
        lbb = ma.iloc[-1] - 2*std.iloc[-1]

        return ma, ubb, lbb

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

    def get_price(self):
        # 매수 가격을 결정
        current_price = pyupbit.get_current_price(self.ticker)
        price = current_price * 0.995

        price_str = str(price)
        dot = price_str.index('.')
        length = len(price_str[:dot])
        if length == 1:
            if price_str[0] == '0':
                price = round(price, 3)  # 0.0원
            else:
                price = round(price, 2)  # 1원
        elif length == 2:
            price = round(price, 1)  # 10원
        elif length == 3:
            price = round(price)  # 100원
        elif length == 4:
            price = (round(price)//5)*5  # 1,000원
        elif length == 5:
            price = (round(price)//10)*10  # 10,000원
        elif length == 6:
            price = (round(price)//100)*100  # 100,000원
        elif length == 7:
            price = (round(price)//1000)*1000  # 1,000,000원
        return price

    def order_cancel(self):
        # 주문 취소
        upbit.cancel_order(upbit.get_order(self.ticker)[0]['uuid'])
        return True

    def down_cancel(self):
        # 이동평균선의 기울기가 음수일 경우

        df = pyupbit.get_ohlcv(self.ticker, self.minute)
        pvt, ma_ewm_pvt, ma_pvt, ubb_pvt, lbb_pvt = DataFrame(
            df).get_pvt()
        if ma_ewm_pvt.iloc[-1] - ma_ewm_pvt.iloc[-2] < 0:
            return True

    def meet(self):
        # PVT선도가 UPP보다 위에 있을 때

        df = pyupbit.get_ohlcv(self.ticker, self.minute)
        pvt, ma_ewm_pvt, ma_pvt, ubb_pvt, lbb_pvt = DataFrame(df).get_pvt()

        if pvt.iloc[-1] > ubb_pvt.iloc[-1]:
            return True

    def buying(self):
        # 매수 체결 중

        order = upbit.get_order(self.ticker)[0]
        hope_buy_price = float(order['price'])
        count = 0
        while True:
            # 매수 시도

            price = pyupbit.get_current_price(self.ticker)
            if upbit.get_order(self.ticker):
                print(
                    f'{self.ticker}의 매수 체결 중 입니다. 현재가: {price} 희망가: {hope_buy_price} 격차: {round((price/hope_buy_price)*100, 2)} %')

                # 매수 시간이 20분을 초과할 매수 주문 취소.
                count += 1
                if count == 1200:
                    return Market(self.ticker, self.minute).order_cancel()

                # 매수가가 구매범위를 초과할 경우 매수 주문 취소
                if price/hope_buy_price > 1.015:
                    return Market(self.ticker, self.minute).order_cancel()

                # 8시 50분일 경우 주문 취소
                now = datetime.datetime.now()
                if now.hour == 8 and now.minute == 50:
                    return Market(self.ticker, self.minute).order_cancel()

                if not Market(self.ticker, 'minute30').meet():
                    return Market(self.ticker, self.minute).order_cancel()

            else:
                return True

            time.sleep(1)

    def get_percentage(self):
        df = pyupbit.get_ohlcv(self.ticker, self.minute)
        pvt, ma_ewm_pvt, ma_pvt, ubb_pvt, lbb_pvt = DataFrame(df).get_pvt()

        cnt1, cnt2 = 0, 0
        for i in range(-7, 0):
            if pvt.iloc[i] > ma_ewm_pvt.iloc[i]:
                cnt1 += 1
            if pvt.iloc[i] > ubb_pvt.iloc[i]:
                cnt2 += 1
        # and pvt.iloc[-1] > ubb_pvt.iloc[-1]
        if cnt1 > 3 and cnt2 > 0:
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

    # 미체결 매수 조회
    for ticker in tickers:
        if upbit.get_order(ticker):
            if Market(ticker, 'minute1').buying():
                return

    chosen_ticker = list()
    for ticker in tickers:
        df_day = pyupbit.get_ohlcv(ticker, "day", count=100)

        # 거래일이 20일 미만일 경우 continue
        if len(df_day) < 20:
            continue
        #
        if Market(ticker, 'minute60').get_percentage() and not Market(ticker, 'minute30').get_nw():
            chosen_ticker.append(ticker)
        time.sleep(0.1)
    # 매수 시도
    while chosen_ticker:
        for ticker in chosen_ticker:

            # 8시 50분일 경우 시간 지연을 1시간 정도 함(아침에는 변동성이 너무 크기 때문에.)
            now = datetime.datetime.now()
            if now.hour == 8 and now.minute == 50:
                time.sleep(3600)

            # 현재 가격
            price = pyupbit.get_current_price(ticker)

            # 종목 가격이 잔고 금액을 초과할 경우 continue
            if price > krw_balance:
                continue

            # 매수 시도(0.1 초마다 조건을 확인 후 시도)
            if Market(ticker, 'minute30').get_nw() and Market(ticker, 'minute30').meet():
                if Market(ticker, 'minute5').get_nw() and Market(ticker, 'minute5').meet() and not Market(ticker, 'minute5').down_cancel():
                    hope_buy_price = Market(ticker, 'minute1').get_price()
                    volume = int(krw_balance//hope_buy_price)
                    if upbit.buy_limit_order(ticker, hope_buy_price, volume):
                        print(
                            f'{ticker}의 매수 주문이 들어갔습니다. 현재가: {price} 희망가: {hope_buy_price} 수량: {volume}')

                        if Market(ticker, 'minute1').buying():
                            return
                # else:
                #     if Market(ticker, 'minute3').down_cancel() and Market(ticker, 'minute5').down_cancel() and Market(ticker, 'minute10').down_cancel() and Market(ticker, 'minute15').down_cancel():
                #         chosen_ticker.remove(ticker)
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

        if current_price / avg_buy_price > 1.02:
            if Market(ticker, 'minute1').meet():
                continue
            else:
                upbit.sell_limit_order(ticker, current_price, coin_balance)

        if avg_buy_price / current_price > 1.02:
            upbit.sell_limit_order(ticker, avg_buy_price, coin_balance)

        print(f'현재시간: {now} 구매 종목: {ticker} 수량: {coin_balance} 구매가: {avg_buy_price} 현재가: {current_price} 수익률: {round((current_price/avg_buy_price)*100, 2)} %')

        time.sleep(1)


while True:
    try:
        balances = upbit.get_balances()
        krw_balance = float(balances[0]['balance'])
        # 매수된 ticker
        if len(balances) > 1:
            ticker = 'KRW-' + balances[1]['currency']

            sell(ticker)

            continue
        # 매수 주문
        buy(10000*0.9995)
    except:
        continue
