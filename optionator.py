# This is a python script to execute option strategies in 5Paisa and Shoonya
import time
from datetime import datetime

import toml
import typer
from py5paisa import FivePaisaClient
from tabulate import tabulate

from common import slice_for_freeze_qty, execute_orders
from noren_api import NorenApi
from shoonya import get_master_scrip_nfo, return_index_expiry

app = typer.Typer()

config = {}
with open("user-config.toml", "r") as f:
    config = toml.load(f, _dict=dict)


@app.command()
def trade(
        strategy_config_path: str,
        is_demo: bool = typer.Option(
            False,
            "--demo",
            "-d",
            help="Enables dry-run mode and does not place actual orders",
        ),
):
    # Read strategy config
    with open(strategy_config_path, "r") as f:
        strategy = toml.load(f, _dict=dict)

    # Make some assertions
    scrip = strategy.get('scrip')
    assert scrip in ["BANKNIFTY", "NIFTY", "FINNIFTY"]

    # Automatically get the closest expiry
    if not strategy.get('expiry'):
        master_df = get_master_scrip_nfo()
        expiry = return_index_expiry(master_df, scrip)

        # Convert from 08JUN23 -> 20230608
        expiry = datetime.strptime(expiry, '%d%b%y')
        formatted_expiry = expiry.strftime('%Y%m%d')

        strategy['expiry'] = formatted_expiry

    for user_id in config["users"]:
        user = config["users"][user_id]
        broker = user["broker"]
        name = user.get('name')
        client = None

        if broker == "5paisa":
            email = user["email"]
            passwd = user["passwd"]
            dob = user["dob"]
            client = FivePaisaClient(
                email=email,
                passwd=passwd,
                dob=dob,
                cred=config["users"][user_id]["app-cred"],
            )
            client.login()
            typer.secho(
                f"Logged In! Broker: {user['broker']} | User ID: {email} | Name: {name}")
        elif broker == "shoonya":
            userid = user.get('user')
            pwd = user.get('passwd')
            vc = f"{userid}_U"
            app_key = user.get('app_key')
            imei = "abcd1234"

            import pyotp
            totp = pyotp.TOTP(user.get('totp_key')).now()

            client = NorenApi(host='https://api.shoonya.com/NorenWClientTP/',
                              websocket='wss://api.shoonya.com/NorenWSTP/')
            if ret := client.login(
                    userid=userid,
                    password=pwd,
                    twoFA=totp,
                    vendor_code=vc,
                    api_secret=app_key,
                    imei=imei,
            ):
                typer.secho(
                    f"Logged In! Broker: {user['broker']} | User ID: {userid} | Name: {name}| Token: {ret['susertoken']}")

        typer.secho("Summary of orders to be placed")
        typer.secho(f"Scrip: {strategy['scrip'].upper()}")
        orders = []

        # Get exits
        exits = strategy.get("exit", {})
        hedge_gap = exits.get("hedge_gap", 0)
        exits_strikes = exits.get("strikes", "")
        exits_pe = int(exits_strikes.split("-")[0]) if exits_strikes else 0
        if exits_pe > 0:
            exit_qty = strategy["clients"][name]["exit_qty"]
            orders.extend(
                (
                    {"strike": exits_pe, "opt": "PE", "qty": exit_qty},
                    {
                        "strike": exits_pe - hedge_gap,
                        "opt": "PE",
                        "qty": -exit_qty,
                    },
                )
            )
        exits_ce = int(exits_strikes.split("-")[1]) if exits_strikes else 0
        if exits_ce > 0:
            exit_qty = strategy["clients"][name]["exit_qty"]
            orders.extend(
                (
                    {"strike": exits_ce, "opt": "CE", "qty": exit_qty},
                    {
                        "strike": exits_ce + hedge_gap,
                        "opt": "CE",
                        "qty": -exit_qty,
                    },
                )
            )
        # Get entries
        entries = strategy.get("entry", {})
        hedge_gap = entries.get("hedge_gap", 0)
        entries_strike = entries.get("strikes", "")
        entries_pe = int(entries_strike.split("-")[0]) if entries_strike else 0
        if entries_pe > 0:
            entry_qty = strategy["clients"][name]["entry_qty"]
            orders.extend(
                (
                    {"strike": entries_pe, "opt": "PE", "qty": -entry_qty},
                    {
                        "strike": entries_pe - hedge_gap,
                        "opt": "PE",
                        "qty": entry_qty,
                    },
                )
            )
        entries_ce = int(entries_strike.split("-")[1]) if entries_strike else 0
        if entries_ce > 0:
            entry_qty = strategy["clients"][name]["entry_qty"]
            orders.extend(
                (
                    {"strike": entries_ce, "opt": "CE", "qty": -entry_qty},
                    {
                        "strike": entries_ce + hedge_gap,
                        "opt": "CE",
                        "qty": entry_qty,
                    },
                )
            )
        orders = sorted(orders, key=lambda d: d["qty"], reverse=True)

        buys, orders_sliced, sells = slice_for_freeze_qty(orders, strategy)

        typer.secho(
            f"Orders: \n{tabulate(orders_sliced, headers='keys', tablefmt='pretty')}"
        )

        proceed = typer.confirm("Are you sure you want to proceed and place orders?")
        if not proceed:
            continue
        typer.echo("Placing Orders!")

        for order in buys:
            execute_orders(client, is_demo, order, strategy, broker)

        time.sleep(2)

        for order in sells:
            execute_orders(client, is_demo, order, strategy, broker)


if __name__ == "__main__":
    app()
