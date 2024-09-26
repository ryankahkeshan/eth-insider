import requests
import constants
import math

def get_eth(address):
    url = ("https://api.etherscan.io/api"
                "?module=account"
                "&action=balance"
                f"&address={address}"
                "&tag=latest"
                f"&apikey={constants.ETHERSCAN_KEY}"
            )
    response = requests.get(url)
    eth = float(response.json()["result"]) * constants.WEI_TO_ETH
    url = ("https://api.etherscan.io/api"
            "?module=stats"
            "&action=ethprice"
            f"&apikey={constants.ETHERSCAN_KEY}"
          )
    eth_price = float(requests.get(url).json()['result']['ethusd'])
    return eth, eth_price


def get_erc20(wallet, token):
    url = (
        "https://api.etherscan.io/api"
        "?module=account"
        "&action=tokenbalance"
        f"&contractaddress={token}"
        f"&address={wallet}"
        f"&tag=latest&apikey={constants.ETHERSCAN_KEY}"
    )
    try: 
        response = requests.get(url)
        if (status := response.json()['status']) != '1':
            print(f"ERROR: STATUS: {status}, RESULT: {response.json()['result']}")
            return
        ammount = float(response.json()['result'])
        return constants.wei_to_eth(ammount)
    except:
        print("ERROR WHILE FETCHING TOKEN BALANCE")
        return 0

# deprecated
def num_txns(address):
    url = (
        "https://api.etherscan.io/api"
        "?module=account"
        "&action=tokentx"
        f"&address={address}"
        "&startblock=0"
        "&endblock=99999999"
        "&offset=100"
        "&sort=asc"
        f"&apikey={constants.ETHERSCAN_KEY}"
    )

    try:
        response = requests.get(url).json()['result']
        # filter to avoid most spams, then add 25%, a low shot approximation
        # is ok in our case as we don't want to filter out potential wallets
        filt = list(filter(lambda x:x['from'] == address, response))
        return math.ceil(len(filt)*1.25)
    except Exception as e:
        print(f"ERROR:\n{e}")


def get_block_number(time):
    url = (
        "https://api.etherscan.io/api"
        "?module=block"
        "&action=getblocknobytime"
        f"&timestamp={time}"
        "&closest=before"
        f"&apikey={constants.ETHERSCAN_KEY}"
    )
    try:
        response = requests.get(url).json()
        return int(response['result'])
    except Exception as e:
        print(f"ERROR:\n{e}")
