import requests
import constants as cons
from datetime import datetime, timedelta
from pymongo import MongoClient

client = MongoClient('localhost', 27017) 
db = client.crypto

class Txn:
    def __init__(self, type, time, block):
        self.type = type
        self.time = time
        self.block = block
        self.inwards = None 
        self.out = None
        self.flag = False

    def __str__(self):
        result = f"{self.type} {self.time}\n"
        if self.inwards:
            result += f"{self.inwards}\n"
        if self.out:
            result += f"{self.out}\n"
        return result

class Position:
    def __init__(self, name, amount, value, price):
        self.name = name
        self.amount = amount
        self.value = value
        self.price = price
    
    def __str__(self):
        return f"Name: {self.name}, Amount: {self.amount}, Value: {self.value}, Price: {self.price}"

# returns None if address is a contract, returns -1 if limit is reached
def get_txns(address, start = None, end = None, limit = None):
    try:
        if start == None and end == None:
            url = f"https://api.zerion.io/v1/wallets/{address}/transactions/?currency=usd&page[size]=100&filter[operation_types]=trade,send&filter[asset_types]=fungible&filter[chain_ids]=ethereum&filter[trash]=only_non_trash"
        else: url = f"https://api.zerion.io/v1/wallets/{address}/transactions/?currency=usd&page[size]=100&filter[operation_types]=trade,send&filter[chain_ids]=ethereum&filter[min_mined_at]={start}&filter[max_mined_at]={end}&filter[trash]=only_non_trash"

        headers = {
            "accept": "application/json",
            "authorization": cons.ZERION_KEY
        }

        response = requests.get(url, headers=headers)
        response = response.json()
        # wallet is actually a contract, return None
        if 'errors' in response:
            if response['errors'][0]['detail'] == 'untrackable wallet address':
                return None
            else: raise ValueError(f"ERROR FETCHING TXNS OF {address}")
        all_txns = []
        all_txns.extend(list(response['data']))

        num_pages = 1
        # pagination
        while 'next' in response['links']:
            if num_pages >= limit: return -1
            url = response['links']['next']
            response = requests.get(url, headers=headers)
            response = response.json()
            all_txns.extend(list(response['data']))
            num_pages += 1

        result = []
        for txn_data in all_txns:
            txn = txn_data['attributes']
            type = txn['operation_type']
            time = txn['mined_at']
            block = txn['mined_at_block']
            transaction = Txn(type, time, block)
            
            trans = txn['transfers']
            trans_len = len(trans)
            if trans_len == 0: continue # false txn (hash dne)
            first = trans[0]
            if type == 'trade':
                txn_in = {
                    'symbol': None,
                    'ca': None,
                    'price': 0,
                    'amount': 0,
                    'value': 0
                }
                txn_out = {
                    'symbol': None,
                    'ca': None,
                    'price': 0,
                    'amount': 0,
                    'value': 0
                }
                for i in range(trans_len):
                    if 'nft_info' in trans[i]:
                        transaction.flag = True
                        break

                    symbol = trans[i]['fungible_info']['symbol'].upper()
                    price = trans[i]['price']
                    quantity = trans[i]['quantity']['float']
                    val = trans[i]['value']
                    if (quantity == None or val == None or price == None):
                        transaction.flag = True
                        break
                    if trans[i]['direction'] == 'in':
                        txn_in['symbol'] = symbol
                        if not txn_in['symbol'] in cons.AVOID:
                            txn_in['ca'] = trans[i]['fungible_info']['implementations'][0]['address']
                        txn_in['price'] = price
                        txn_in['amount'] += quantity
                        txn_in['value'] += val
                    elif trans[i]['direction'] == 'out':
                        txn_out['symbol'] = symbol
                        if not txn_out['symbol'] in cons.AVOID:
                            txn_out['ca'] = trans[i]['fungible_info']['implementations'][0]['address']
                        txn_out['price'] = price
                        txn_out['amount'] += quantity
                        txn_out['value'] += val
                if transaction.flag: continue
                transaction.inwards = txn_in
                transaction.out = txn_out
            elif type == 'send':
                if 'nft_info' in first: continue
                txn_out = {
                    'symbol': first['fungible_info']['symbol'].upper(),
                    'ca': None,
                    #'ca': first['fungible_info']['implementations'][0]['address'],
                    'price': first['price'],
                    'amount': first['quantity']['float'],
                    'value': first['value']
                }
                if not txn_out['symbol'] in cons.AVOID:
                    txn_out['ca'] = first['fungible_info']['implementations'][0]['address']
                if txn_out['price'] == None or txn_out['value'] == None or txn_out['amount'] == None:
                    transaction.flag = True
                    continue
                transaction.out = txn_out
            result.append(transaction)
        return result
    except Exception as e:
        print(f"ERROR: ZERION.GET_TXNS:\n{e}")
    

def get_positions(address):
    try: 
        url = f"https://api.zerion.io/v1/wallets/{address}/positions/?filter[positions]=only_simple&currency=usd&filter[chain_ids]=ethereum&filter[trash]=only_non_trash&sort=value"

        headers = {
            "accept": "application/json",
            "authorization": cons.ZERION_KEY
        }

        response = requests.get(url, headers=headers)
        response = response.json()['data']
        all_holdings = {}
        for position in response:
            data = position['attributes']
            name = data['fungible_info']['symbol'].upper()
            amount = data['quantity']['float']
            value = data['value']
            price = data['price']
            pos = Position(name, amount, value, price)
            all_holdings[name] = pos
        return all_holdings
    except Exception as e:
        print(f"ERROR ZERION GET_POSITIONS:\n{e}")


