import asyncio
import datetime
import hashlib
import json
import time
import urllib
from datetime import datetime as dt

import requests
import websockets
from loguru import logger


class Position:
    prd: str
    exch: str
    instname: str
    symname: str
    exd: int
    optt: str
    strprc: float
    buyqty: int
    sellqty: int
    netqty: int

    def encode(self):
        return self.__dict__


class ProductType:
    Delivery = "C"
    Intraday = "I"
    Normal = "M"
    CF = "M"


class FeedType:
    TOUCHLINE = 1
    SNAPQUOTE = 2


class PriceType:
    Market = "MKT"
    Limit = "LMT"
    StopLossLimit = "SL-LMT"
    StopLossMarket = "SL-MKT"


class BuyorSell:
    Buy = "B"
    Sell = "S"


def reportmsg(msg):
    pass
    # print(msg)
    # logger.debug(msg)


def reporterror(msg):
    pass
    # print(msg)
    # logger.error(msg)


def reportinfo(msg):
    pass
    # print(msg)
    # logger.info(msg)


class NorenApi:
    __service_config = {
        "host": "http://wsapihost/",
        "routes": {
            "authorize": "/QuickAuth",
            "logout": "/Logout",
            "forgot_password": "/ForgotPassword",
            "change_password": "/Changepwd",
            "watchlist_names": "/MWList",
            "watchlist": "/MarketWatch",
            "watchlist_add": "/AddMultiScripsToMW",
            "watchlist_delete": "/DeleteMultiMWScrips",
            "placeorder": "/PlaceOrder",
            "modifyorder": "/ModifyOrder",
            "cancelorder": "/CancelOrder",
            "exitorder": "/ExitSNOOrder",
            "product_conversion": "/ProductConversion",
            "orderbook": "/OrderBook",
            "tradebook": "/TradeBook",
            "singleorderhistory": "/SingleOrdHist",
            "searchscrip": "/SearchScrip",
            "TPSeries": "/TPSeries",
            "optionchain": "/GetOptionChain",
            "holdings": "/Holdings",
            "limits": "/Limits",
            "positions": "/PositionBook",
            "scripinfo": "/GetSecurityInfo",
            "getquotes": "/GetQuotes",
            "span_calculator": "/SpanCalc",
            "option_greek": "/GetOptionGreek",
            "get_daily_price_series": "/EODChartData",
        },
        "websocket_endpoint": "wss://wsendpoint/",
        # 'eoddata_endpoint' : 'http://eodhost/'
    }

    def __init__(self, host, websocket):
        self.__on_open = None
        self.__subscribe_callback = None
        self.__order_update_callback = None
        self.__websocket_connected = False  # True -> Connected, False -> Not Connected
        self.__ws = None

        self.__service_config["host"] = host
        self.__service_config["websocket_endpoint"] = websocket

        self.__subscribers = {}
        self.__market_status_messages = []
        self.__exchange_messages = []
        self.__session = requests.Session()

    def close_websocket(self):
        if self.__websocket_connected:
            self.__websocket_connected = False

    async def start_websocket(
        self,
        subscribe_callback=None,
        order_update_callback=None,
        socket_open_callback=None,
        socket_close_callback=None,
        socket_error_callback=None,
    ):
        self.__order_update_callback = order_update_callback
        self.__subscribe_callback = subscribe_callback
        self.__on_open = socket_open_callback

        if self.__websocket_connected:
            return

        asyncio.create_task(self.websocket_task_async())

    async def websocket_task_async(self):
        url = self.__service_config["websocket_endpoint"]
        self.__ws = await websockets.connect(url, ping_interval=3)
        self.__websocket_connected = True
        logger.info("Websocket connected!")

        # Call on open callback
        await self.__on_open_callback()

        try:
            while self.__websocket_connected:
                await asyncio.sleep(0.05)
                message = await self.__ws.recv()
                res = json.loads(message)

                if self.__subscribe_callback is not None:
                    if res["t"] in ["tk", "tf"]:
                        await self.__subscribe_callback(res)
                        continue
                    if res["t"] in ["dk", "df"]:
                        await self.__subscribe_callback(res)
                        continue

                if res["t"] == "ck" and res["s"] != "OK":
                    logger.error(res)
                    continue

                if (self.__order_update_callback is not None) and res["t"] == "om":
                    await self.__order_update_callback(res)
                    continue

                if self.__on_open and res["t"] == "ck" and res["s"] == "OK":
                    await self.__on_open()
                    continue
        except Exception as e:
            logger.error(e)
        finally:
            await self.__ws.close()
            self.__websocket_connected = False

    async def __on_open_callback(self):
        # prepare the data
        values = {
            "t": "c",
            "uid": self.__username,
            "actid": self.__username,
            "susertoken": self.__susertoken,
            "source": "API",
        }
        payload = json.dumps(values)
        reportmsg(payload)
        await self.__ws.send(payload)

    def login(self, userid, password, twoFA, vendor_code, api_secret, imei):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['authorize']}"
        reportmsg(url)

        # Convert to SHA 256 for password and app key
        pwd = hashlib.sha256(password.encode("utf-8")).hexdigest()
        u_app_key = "{0}|{1}".format(userid, api_secret)
        app_key = hashlib.sha256(u_app_key.encode("utf-8")).hexdigest()
        # prepare the data
        values = {
            "source": "API",
            "apkversion": "1.0.0",
            "uid": userid,
            "pwd": pwd,
            "factor2": twoFA,
            "vc": vendor_code,
            "appkey": app_key,
            "imei": imei,
        }
        payload = f"jData={json.dumps(values)}"
        reportmsg(f"Req:{payload}")

        res = self.__session.post(url, data=payload)
        reportmsg(f"Reply:{res.text}")

        resDict = json.loads(res.text)
        if resDict["stat"] != "Ok":
            return None

        self.__username = userid
        self.__accountid = userid
        self.__password = password
        self.__susertoken = resDict["susertoken"]
        # reportmsg(self.__susertoken)

        return resDict

    def set_session(self, userid, password, usertoken):

        self.__username = userid
        self.__accountid = userid
        self.__password = password
        self.__susertoken = usertoken

        reportmsg(f"{userid} session set to : {self.__susertoken}")

        return True

    def forgot_password(self, userid, pan, dob):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['forgot_password']}"
        reportmsg(url)

        # prepare the data
        values = {"source": "API", "uid": userid, "pan": pan, "dob": dob}
        payload = f"jData={json.dumps(values)}"
        reportmsg(f"Req:{payload}")

        res = self.__session.post(url, data=payload)
        reportmsg(f"Reply:{res.text}")

        resDict = json.loads(res.text)

        return None if resDict["stat"] != "Ok" else resDict

    def logout(self):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['logout']}"
        reportmsg(url)
        # prepare the data
        values = {"ordersource": "API", "uid": self.__username}

        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)
        if resDict["stat"] != "Ok":
            return None

        self.__username = None
        self.__accountid = None
        self.__password = None
        self.__susertoken = None

        return resDict

    async def subscribe(self, instrument, feed_type=FeedType.TOUCHLINE):
        values = {}

        if feed_type == FeedType.TOUCHLINE:
            values["t"] = "t"
        elif feed_type == FeedType.SNAPQUOTE:
            values["t"] = "d"
        else:
            values["t"] = str(feed_type)

        values["k"] = "#".join(instrument) if type(instrument) == list else instrument
        data = json.dumps(values)
        # logger.info(f"Subscribing to {data}")

        await self.__ws.send(data)

    async def unsubscribe(self, instrument, feed_type=FeedType.TOUCHLINE):
        values = {}

        if feed_type == FeedType.TOUCHLINE:
            values["t"] = "u"
        elif feed_type == FeedType.SNAPQUOTE:
            values["t"] = "ud"

        values["k"] = "#".join(instrument) if type(instrument) == list else instrument
        data = json.dumps(values)

        await self.__ws.send(data)

    def get_watch_list_names(self):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['watchlist_names']}"
        reportmsg(url)
        # prepare the data
        values = {"ordersource": "API", "uid": self.__username}
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)
        return None if resDict["stat"] != "Ok" else resDict

    def get_watch_list(self, wlname):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['watchlist']}"
        reportmsg(url)
        # prepare the data
        values = {"ordersource": "API", "uid": self.__username, "wlname": wlname}
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)
        return None if resDict["stat"] != "Ok" else resDict

    def add_watch_list_scrip(self, wlname, instrument):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['watchlist_add']}"
        reportmsg(url)
        # prepare the data
        values = {
            "ordersource": "API",
            "uid": self.__username,
            "wlname": wlname,
            "scrips": "#".join(instrument) if type(instrument) == list else instrument,
        }
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)
        return None if resDict["stat"] != "Ok" else resDict

    def delete_watch_list_scrip(self, wlname, instrument):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['watchlist_delete']}"
        reportmsg(url)
        # prepare the data
        values = {
            "ordersource": "API",
            "uid": self.__username,
            "wlname": wlname,
            "scrips": "#".join(instrument) if type(instrument) == list else instrument,
        }
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)
        return None if resDict["stat"] != "Ok" else resDict

    def place_order(
        self,
        buy_or_sell,
        product_type,
        exchange,
        tradingsymbol,
        quantity,
        discloseqty,
        price_type,
        price=0.0,
        trigger_price=None,
        retention="DAY",
        amo="NO",
        remarks=None,
        bookloss_price=0.0,
        bookprofit_price=0.0,
        trail_price=0.0,
    ):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['placeorder']}"
        reportmsg(url)
        # prepare the data
        values = {
            "ordersource": "API",
            "uid": self.__username,
            "actid": self.__accountid,
            "trantype": buy_or_sell,
            "prd": product_type,
            "exch": exchange,
            "tsym": urllib.parse.quote_plus(tradingsymbol),
            "qty": str(quantity),
            "dscqty": str(discloseqty),
            "prctyp": price_type,
            "prc": str(price),
            "trgprc": str(trigger_price),
            "ret": retention,
            "remarks": remarks,
            "amo": amo,
        }

        # if cover order or high leverage order
        if product_type == "H":
            values["blprc"] = str(bookloss_price)
            # trailing price
            if trail_price != 0.0:
                values["trailprc"] = str(trail_price)

        # bracket order
        if product_type == "B":
            values["blprc"] = str(bookloss_price)
            values["bpprc"] = str(bookprofit_price)
            # trailing price
            if trail_price != 0.0:
                values["trailprc"] = str(trail_price)

        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)
        return None if resDict["stat"] != "Ok" else resDict

    def modify_order(
        self,
        orderno,
        exchange,
        tradingsymbol,
        newquantity,
        newprice_type,
        newprice=0.0,
        newtrigger_price=None,
        bookloss_price=0.0,
        bookprofit_price=0.0,
        trail_price=0.0,
    ):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['modifyorder']}"
        print(url)

        # prepare the data
        values = {
            "ordersource": "API",
            "uid": self.__username,
            "actid": self.__accountid,
            "norenordno": str(orderno),
            "exch": exchange,
            "tsym": urllib.parse.quote_plus(tradingsymbol),
            "qty": str(newquantity),
            "prctyp": newprice_type,
            "prc": str(newprice),
        }

        if newprice_type in ["SL-LMT", "SL-MKT"]:
            if newtrigger_price is None:
                reporterror("trigger price is missing")
                return None

            else:
                values["trgprc"] = str(newtrigger_price)
        # if cover order or high leverage order
        if bookloss_price != 0.0:
            values["blprc"] = str(bookloss_price)
        # trailing price
        if trail_price != 0.0:
            values["trailprc"] = str(trail_price)
            # book profit of bracket order
        if bookprofit_price != 0.0:
            values["bpprc"] = str(bookprofit_price)

        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)
        return None if resDict["stat"] != "Ok" else resDict

    def cancel_order(self, orderno):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['cancelorder']}"
        print(url)

        # prepare the data
        values = {
            "ordersource": "API",
            "uid": self.__username,
            "norenordno": str(orderno),
        }
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        print(res.text)

        resDict = json.loads(res.text)
        return None if resDict["stat"] != "Ok" else resDict

    def exit_order(self, orderno, product_type):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['exitorder']}"
        print(url)

        # prepare the data
        values = {
            "ordersource": "API",
            "uid": self.__username,
            "norenordno": orderno,
            "prd": product_type,
        }
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)
        return None if resDict["stat"] != "Ok" else resDict

    def position_product_conversion(
        self,
        exchange,
        tradingsymbol,
        quantity,
        new_product_type,
        previous_product_type,
        buy_or_sell,
        day_or_cf,
    ):
        """
        Coverts a day or carryforward position from one product to another.
        """
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['product_conversion']}"
        print(url)

        # prepare the data
        values = {
            "ordersource": "API",
            "uid": self.__username,
            "actid": self.__accountid,
            "exch": exchange,
            "tsym": urllib.parse.quote_plus(tradingsymbol),
            "qty": str(quantity),
            "prd": new_product_type,
            "prevprd": previous_product_type,
            "trantype": buy_or_sell,
            "postype": day_or_cf,
        }

        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)

        return None if resDict["stat"] != "Ok" else resDict

    def single_order_history(self, orderno):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['singleorderhistory']}"
        print(url)

        # prepare the data
        values = {"ordersource": "API", "uid": self.__username, "norenordno": orderno}
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)
        # error is a json with stat and msg wchih we printed earlier.
        return None if type(resDict) != list else resDict

    def get_order_book(self):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['orderbook']}"
        reportmsg(url)

        # prepare the data
        values = {"ordersource": "API", "uid": self.__username}
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)

        # error is a json with stat and msg wchih we printed earlier.
        return None if type(resDict) != list else resDict

    def get_trade_book(self):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['tradebook']}"
        reportmsg(url)

        # prepare the data
        values = {
            "ordersource": "API",
            "uid": self.__username,
            "actid": self.__accountid,
        }
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)

        # error is a json with stat and msg wchih we printed earlier.
        return None if type(resDict) != list else resDict

    def searchscrip(self, exchange, searchtext):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['searchscrip']}"
        reportmsg(url)

        if searchtext is None:
            reporterror("search text cannot be null")
            return None

        values = {
            "uid": self.__username,
            "exch": exchange,
            "stext": urllib.parse.quote_plus(searchtext),
        }
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)

        return None if resDict["stat"] != "Ok" else resDict

    def get_option_chain(self, exchange, tradingsymbol, strikeprice, count=2):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['optionchain']}"
        reportmsg(url)

        values = {
            "uid": self.__username,
            "exch": exchange,
            "tsym": urllib.parse.quote_plus(tradingsymbol),
            "strprc": str(strikeprice),
            "cnt": str(count),
        }

        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)

        return None if resDict["stat"] != "Ok" else resDict

    def get_security_info(self, exchange, token):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['scripinfo']}"
        reportmsg(url)

        values = {"uid": self.__username, "exch": exchange, "token": token}
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)

        return None if resDict["stat"] != "Ok" else resDict

    def get_quotes(self, exchange, token):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['getquotes']}"
        reportmsg(url)

        values = {"uid": self.__username, "exch": exchange, "token": token}
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)

        return None if resDict["stat"] != "Ok" else resDict

    def get_time_price_series(
        self, exchange, token, starttime=None, endtime=None, interval=None
    ):
        """
        gets the chart data
        interval possible values 1, 3, 5 , 10, 15, 30, 60, 120, 240
        """
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['TPSeries']}"
        reportmsg(url)

        # prepare the data
        if starttime is None:
            timestring = time.strftime("%d-%m-%Y") + " 00:00:00"
            timeobj = time.strptime(timestring, "%d-%m-%Y %H:%M:%S")
            starttime = time.mktime(timeobj)

        #
        values = {
            "ordersource": "API",
            "uid": self.__username,
            "exch": exchange,
            "token": token,
            "st": str(starttime),
        }

        if endtime is not None:
            values["et"] = str(endtime)
        if interval is not None:
            values["intrv"] = str(interval)

        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)

        # error is a json with stat and msg wchih we printed earlier.
        return None if type(resDict) != list else resDict

    def get_daily_price_series(
        self, exchange, tradingsymbol, startdate=None, enddate=None
    ):
        config = NorenApi.__service_config

        # prepare the uri
        # url = f"{config['eoddata_endpoint']}"
        url = f"{config['host']}{config['routes']['get_daily_price_series']}"
        reportmsg(url)

        # prepare the data
        if startdate is None:
            week_ago = datetime.date.today() - datetime.timedelta(days=7)
            startdate = dt.combine(week_ago, dt.min.time()).timestamp()

        if enddate is None:
            enddate = dt.now().timestamp()

        #
        values = {
            "uid": self.__username,
            "sym": "{0}:{1}".format(exchange, tradingsymbol),
            "from": str(startdate),
            "to": str(enddate),
        }
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"
        # payload = json.dumps(values)
        reportmsg(payload)

        headers = {"Content-Type": "application/json; charset=utf-8"}
        res = self.__session.post(url, data=payload, headers=headers)
        reportmsg(res)

        if res.status_code != 200:
            return None

        if len(res.text) == 0:
            return None

        resDict = json.loads(res.text)

        # error is a json with stat and msg wchih we printed earlier.
        return None if type(resDict) != list else resDict

    def get_holdings(self, product_type=None):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['holdings']}"
        reportmsg(url)

        if product_type is None:
            product_type = ProductType.Delivery

        values = {
            "uid": self.__username,
            "actid": self.__accountid,
            "prd": product_type,
        }
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)

        return None if type(resDict) != list else resDict

    def get_limits(self, product_type=None, segment=None, exchange=None):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['limits']}"
        reportmsg(url)

        values = {"uid": self.__username, "actid": self.__accountid}

        if product_type != None:
            values["prd"] = product_type
            values["seg"] = segment

        if exchange != None:
            values["exch"] = exchange

        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        return json.loads(res.text)

    def get_positions(self):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['positions']}"
        reportmsg(url)

        values = {"uid": self.__username, "actid": self.__accountid}
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        resDict = json.loads(res.text)

        return None if type(resDict) != list else resDict

    def span_calculator(self, actid, positions: list):
        config = NorenApi.__service_config
        # prepare the uri
        url = f"{config['host']}{config['routes']['span_calculator']}"
        reportmsg(url)

        senddata = {"actid": self.__accountid, "pos": positions}
        payload = (
            f"jData={json.dumps(senddata, default=lambda o: o.encode())}"
            + f"&jKey={self.__susertoken}"
        )
        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        return json.loads(res.text)

    def option_greek(
        self, expiredate, StrikePrice, SpotPrice, InterestRate, Volatility, OptionType
    ):
        config = NorenApi.__service_config

        # prepare the uri
        url = f"{config['host']}{config['routes']['option_greek']}"
        reportmsg(url)

        # prepare the data
        values = {
            "source": "API",
            "actid": self.__accountid,
            "exd": expiredate,
            "strprc": StrikePrice,
            "sptprc": SpotPrice,
            "int_rate": InterestRate,
            "volatility": Volatility,
            "optt": OptionType,
        }
        payload = f"jData={json.dumps(values)}" + f"&jKey={self.__susertoken}"

        reportmsg(payload)

        res = self.__session.post(url, data=payload)
        reportmsg(res.text)

        return json.loads(res.text)
