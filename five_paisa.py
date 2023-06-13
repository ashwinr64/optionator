def get_scripcode_5paisa(client, symbol, strike, expiry, opt):
    """Copied from https://github.com/5paisa/py5paisa/blob/master/py5paisa/strategy.py"""
    month = {
        "01": "JAN",
        "02": "FEB",
        "03": "MAR",
        "04": "APR",
        "05": "MAY",
        "06": "JUN",
        "07": "JUL",
        "08": "AUG",
        "09": "SEP",
        "10": "OCT",
        "11": "NOV",
        "12": "DEC",
    }
    date = expiry[6:]
    mon = month[expiry[4:6]]
    year = expiry[:4]
    symbol = symbol.upper()
    strike_f = "{:.2f}".format(float(strike))
    sym = f"{symbol} {date} {mon} {year} {opt} {strike_f}"
    req = [
        {
            "Exch": "N",
            "ExchType": "D",
            "Symbol": sym,
            "Expiry": expiry,
            "StrikePrice": strike,
            "OptionType": opt,
        }
    ]

    res = client.fetch_market_feed(req)
    token = res["Data"][0]["Token"]
    return token, sym
