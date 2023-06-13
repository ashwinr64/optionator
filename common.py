import typer
from typer.colors import GREEN, RED

from constants import freeze_qty
from five_paisa import get_scripcode_5paisa
from shoonya import get_scripcode_shoonya


def slice_for_freeze_qty(orders, strategy):
    # Slicing for freeze limit
    orders_sliced = []
    for order in orders:
        scrip = strategy["scrip"]
        qty = order["qty"]
        abs_qty = abs(qty)
        max_qty = freeze_qty.get(scrip, 0)

        if max_qty == 0 or abs_qty <= max_qty:
            orders_sliced.append(order)
        else:
            sign = 1 if qty > 0 else -1
            num_slices = abs_qty // max_qty

            orders_sliced.extend(
                {
                    "strike": order["strike"],
                    "opt": order["opt"],
                    "qty": max_qty * sign,
                }
                for _ in range(num_slices)
            )
            abs_rem_qty = abs_qty % max_qty
            if abs_rem_qty != 0:
                rem_qty = abs_rem_qty * sign
                orders_sliced.append({
                    "strike": order["strike"],
                    "opt": order["opt"],
                    "qty": rem_qty
                })
    buys = [d for d in orders_sliced if d["qty"] > 0]
    sells = [d for d in orders_sliced if d["qty"] < 0]
    return buys, orders_sliced, sells


def execute_orders(client, is_demo, order, strategy, broker):
    scrip = strategy["scrip"]
    expiry = strategy["expiry"]
    strike = order["strike"]
    opt = order["opt"]
    qty = order["qty"]
    abs_qty = abs(qty)
    ord_type = "B" if qty > 0 else "S"
    if broker == "5paisa":
        token, sym = get_scripcode_5paisa(client, scrip, strike, expiry, opt)
        order_status = {} if is_demo else client.place_order(OrderType=ord_type, Exchange='N', ExchangeType='D',
                                                             ScripCode=token, Qty=abs_qty, Price=0)
        if order_status.get("Message") != "Success" and not is_demo:
            raise typer.Abort()
        fg = GREEN if qty > 0 else RED
        typer.secho(f"{sym} qty:{qty} - order placed successfully!", fg=fg)
    elif broker == "shoonya":
        scrip, token = get_scripcode_shoonya(client, scrip, strike, expiry, opt)
        order_status = {} if is_demo else client.place_order(buy_or_sell=ord_type, product_type='M',
                                                             exchange='NFO', tradingsymbol=scrip,
                                                             quantity=abs_qty, discloseqty=0, price_type='MKT', price=0,
                                                             trigger_price=None,
                                                             retention='DAY',
                                                             # amo="YES"
                                                             )
        if not is_demo and order_status['stat'] != 'Ok':
            raise typer.Abort()

        fg = GREEN if qty > 0 else RED
        typer.secho(f"{scrip} qty:{qty} - order placed successfully!", fg=fg)
