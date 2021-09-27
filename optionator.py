# This is a python script to execute option strategies in 5Paisa
import time

import toml
import typer
from py5paisa import FivePaisaClient
from py5paisa.order import Order
from tabulate import tabulate
from typer.colors import *

app = typer.Typer()
config = {}
with open("user-config.toml", "r") as f:
    config = toml.load(f, _dict=dict)


def get_scripcode(client, symbol, strike, expiry, opt):
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
    req = [{"Exch": "N", "ExchType": "D", "Symbol": sym, "Expiry": expiry, "StrikePrice": strike, "OptionType": opt}]

    res = client.fetch_market_feed(req)
    token = res["Data"][0]["Token"]
    return token, sym


@app.command()
def trade(
    user_id: str,
    strategy_config_path: str,
    is_demo: bool = typer.Option(False, "--demo", "-d", help="Enables dry-run mode and does not place actual orders"),
):
    user = config["users"][user_id]
    email = user["email"]
    passwd = user["passwd"]
    dob = user["dob"]

    client = FivePaisaClient(email=email, passwd=passwd, dob=dob, cred=config["app-cred"])
    client.login()
    typer.secho(f"User : {email}", fg=GREEN)
    with open(strategy_config_path, "r") as f:
        strategy = toml.load(f, _dict=dict)
    typer.secho(f"Summary of orders to be placed")
    typer.secho(f"Scrip: {strategy['scrip'].upper()}")

    typer.secho(f"Buying: \n{tabulate(strategy['buy'],headers='keys', tablefmt='pretty')}", fg=GREEN)
    typer.secho(f"Selling: \n{tabulate(strategy['sell'],headers='keys', tablefmt='pretty')}", fg=RED)

    proceed = typer.confirm("Are you sure you want to proceed and place orders?")
    if not proceed:
        raise typer.Abort()
    typer.echo("Placing Orders!")

    for buy in strategy.get("buy", []):
        token, sym = get_scripcode(client, strategy["scrip"], buy["strike"], buy["expiry"], buy["opt"])
        order = Order(
            order_type="B",
            exchange="N",
            exchange_segment="D",
            scrip_code=token,
            quantity=buy["qty"],
            price=0,
            is_intraday=False,
            atmarket=True,
        )

        order_status = {} if is_demo else client.place_order(order)
        if order_status.get("Message") == "Success" or is_demo:
            typer.secho(f"{sym} qty:{buy['qty']} - order placed successfully!", fg=GREEN)
        else:
            raise typer.Abort()
    
    time.sleep(2)

    for sell in strategy.get("sell", []):
        token, sym = get_scripcode(client, strategy["scrip"], sell["strike"], sell["expiry"], sell["opt"])
        order = Order(
            order_type="S",
            exchange="N",
            exchange_segment="D",
            scrip_code=token,
            quantity=sell["qty"],
            price=0,
            is_intraday=False,
            atmarket=True,
        )

        order_status = {} if is_demo else client.place_order(order)
        if order_status.get("Message") == "Success" or is_demo:
            typer.secho(f"{sym} qty:{-sell['qty']} - order placed successfully!", fg=RED)
        else:
            raise typer.Abort()


if __name__ == "__main__":
    app()
