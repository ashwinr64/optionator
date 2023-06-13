import os
import zipfile
from datetime import datetime

import pandas as pd
import requests
import typer


def get_scripcode_shoonya(client, symbol, strike, expiry, opt):
    # Convert the input date string to a datetime object
    date = datetime.strptime(expiry, '%Y%m%d')

    # Format the datetime object as '08JUN23'
    formatted_date = date.strftime('%d%b%y').upper()

    scrip = f"{symbol}{formatted_date}{opt[0]}{strike}"
    ret = client.searchscrip("NFO", scrip)
    return scrip, ret['values'][0]['token']


def get_master_scrip_nfo():
    root = 'https://shoonya.finvasia.com/'
    masters = ['NFO_symbols.txt.zip']

    for zip_file in masters:
        url = root + zip_file
        typer.secho("Downloading Master Scrip List!")
        r = requests.get(url, allow_redirects=True)
        open(zip_file, 'wb').write(r.content)
        file_to_read = zip_file.replace(".zip", "")

        try:
            with zipfile.ZipFile(zip_file) as z:
                z.extractall()
        except Exception as e:
            print("Invalid file")

        df = pd.read_csv(file_to_read)

        os.remove(zip_file)
        os.remove(file_to_read)

        typer.secho("Master Scrip List Downloaded Successfully!")
        return df


def return_index_expiry(master_df, scrip="FINNIFTY", expiry="weekly"):
    master_df = master_df.loc[master_df['Symbol'] == scrip]
    expiries = list(master_df.Expiry.unique())

    expiries.sort(key=lambda d: datetime.strptime(d, "%d-%b-%Y"))

    for i in range(len(expiries)):
        date = expiries[i]
        date_split = date.split('-')
        day = date_split[0]
        month = date_split[1]
        year = int(date_split[2]) - 2000

        expiries[i] = f"{day}{month}{year}"

    if expiry == "weekly":
        return expiries[0]
    elif expiry == "monthly":
        # TODO: Write logic for monthly expiry
        return expiries[0]
