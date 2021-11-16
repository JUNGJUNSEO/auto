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
        price = current_price * 0.99

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
        if ma_ewm_pvt[-1] - ma_ewm_pvt[-2] < 0:
            return True

    def meet(self):
        # PVT선도가 이동평균선보다 아래 있을 때

        df = pyupbit.get_ohlcv(self.ticker, self.minute)
        pvt, ma_ewm_pvt, ma_pvt, ubb_pvt, lbb_pvt = DataFrame(df).get_pvt()

        if pvt.iloc[-1] < ma_ewm_pvt.iloc[-1]:
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

                # PVT선도가 이동평균선이랑 만날 때 매수 주문 취소
                if Market(self.ticker, self.minute).meet() or Market(self.ticker, 'minute3').down_cancel():
                    return Market(self.ticker, self.minute).order_cancel()

                # 매수가가 구매범위를 초과할 경우 매수 주문 취소
                if price/hope_buy_price > 1.02:
                    return Market(self.ticker, self.minute).order_cancel()

                # 8시 50분일 경우 주문 취소
                now = datetime.datetime.now()
                if now.hour == 8 and now.minute == 50:
                    return Market(self.ticker, self.minute).order_cancel()
            else:
                return True

            time.sleep(1)


def buy(krw_balance):
    # 매수
    tickers = pyupbit.get_tickers(fiat='KRW')

    # 미체결 매수 조회
    for ticker in tickers:
        if upbit.get_order(ticker):
            if Market(ticker, 'minute1').buying():
                return
            else:
                break
    # 매수 시도
    while True:
        for ticker in tickers[-1::-1]:
            if ticker == 'KRW-ORBS':
                continue
            # 8시 50분일 경우 시간 지연을 1시간 정도 함(아침에는 변동성이 너무 크기 때문에.)
            now = datetime.datetime.now()
            if now.hour == 8 and now.minute == 50:
                time.sleep(3600)

            # 현재 가격
            price = pyupbit.get_current_price(ticker)

            # 종목 가격이 잔고 금액을 초과할 경우 continue
            if price > krw_balance:
                continue

            df_day = pyupbit.get_ohlcv(ticker, "day", count=100)
            df_minute60 = pyupbit.get_ohlcv(ticker, "minute60")

            # 거래일이 20일 미만일 경우 continue
            if len(df_day) < 20:
                continue

            # 시초 가격
            open_price = df_day['open'].iloc[-1]

            # 최고 가격
            higt = df_day['high'].iloc[-1]

            # 이동 평균선, BB상단, BB하단
            ma_bb, ubb_bb, lbb_bb = DataFrame(df_day).get_bb()
            pvt, ma_ewm_pvt, ma_pvt, ubb_pvt, lbb_pvt = DataFrame(
                df_minute60).get_pvt()

            cnt1, cnt2 = 0, 0
            max_ma = 0
            check_pvt = False
            for i in range(-12, 0):
                if pvt.iloc[i] > ma_ewm_pvt.iloc[i]:
                    cnt1 += 1
                if pvt.iloc[i] > ubb_pvt.iloc[i]:
                    cnt2 += 1
                max_ma = max(max_ma, ma_ewm_pvt.iloc[i])
            if cnt1 > 6 and cnt2 > 1 and ma_ewm_pvt.iloc[-1] == max_ma and pvt.iloc[-1] > ubb_pvt.iloc[-1]:
                check_pvt = True

            # 매수 시도(0.1 초마다 조건을 확인 후 시도)
            if ubb_bb > higt and check_pvt and not Market(ticker, 'minute1').down_cancel() and not Market(ticker, 'minute3').down_cancel() and not Market(ticker, 'minute5').down_cancel() and not Market(ticker, 'minute10').down_cancel() and not Market(ticker, 'minute15').down_cancel() and not Market(ticker, 'minute1').meet() and price/open_price < 1.065:
                hope_buy_price = Market(ticker, 'minute1').get_price()
                volume = int(krw_balance//hope_buy_price)
                if upbit.buy_limit_order(ticker, hope_buy_price, volume):
                    print(
                        f'{ticker}의 매수 주문이 들어갔습니다. 현재가: {price} 희망가: {hope_buy_price} 수량: {volume}')

                    if Market(ticker, 'minute1').buying():
                        return
            else:
                print(f'{ticker}구매 조건에 맞지 않습니다.')

            # 주문 외 요청은 초당 30번 가능
            time.sleep(0.1)


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

        df_minute1 = pyupbit.get_ohlcv(ticker, "minute1")
        pvt, ma_ewm_pvt, ma_pvt, ubb_pvt, lbb_pvt = DataFrame(
            df_minute1).get_pvt()

        if pvt.iloc[-1] > ubb_pvt.iloc[-1]:
            while (pvt.iloc[-1] > ubb_pvt.iloc[-1] or not Market(ticker, 'minute1').meet()):
                df_minute1 = pyupbit.get_ohlcv(ticker, "minute1")
                pvt, ma_ewm_pvt, ma_pvt, ubb_pvt, lbb_pvt = DataFrame(
                    df_minute1).get_pvt()
                print('오른다~')
                time.sleep(1)
            upbit.sell_market_order(ticker, coin_balance)
        else:
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
    # 매수 주문
    buy(krw_balance*0.9995)
