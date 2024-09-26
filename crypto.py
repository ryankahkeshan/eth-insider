import moral
import constants as cons
import etherscan
from datetime import datetime, timedelta
from pymongo import MongoClient
import concurrent.futures
import zerion
import eth

client = MongoClient('localhost', 27017) 
db = client.crypto

# --------- start of class Coin ---------
class Coin:
    def __init__(self, name, ca):
        self.name = name
        self.ca = ca
        self.amount = 0
        self.bought_usd = 0
        self.sold_usd = 0
        self.bought_amount = 0
        self._cached_price = None
    
    def rpnl(self):
        return self.sold_usd - self.bought_usd
    
    def upnl(self, block):
        rpnl = self.rpnl()
        if self.amount > 0:
            # add 0 upnl to lingering coins
            if self.amount / self.bought_amount < 0.01:
                return rpnl
            # fetch only if not cached
            if self._cached_price == None:
                price_obj = db.block_prices.find_one(
                    {'block': int(block)},
                    {'prices': {'$elemMatch': {'contract_address': self.ca}}, '_id': 0}
                )
                if price_obj and 'prices' in price_obj:
                    coin_price = price_obj['prices'][0]['price']
                    if isinstance(coin_price, str):
                        self._cached_price = float(coin_price)
                    elif coin_price is None:
                        self._cached_price = cons.DNE_COIN_PRICE
                        return None
                else: return rpnl   # coin not in db, shouldn't occur
            # wallet has coin but price cannot be found
            elif self._cached_price == cons.DNE_COIN_PRICE: return None
            holding = self.amount * self._cached_price
            return holding + rpnl
        else: return rpnl

    def upnl_perc(self, block):
        if self.amount < 0 or self.bought_usd <= 0: return 0  # buy before start, or got sent
        upnl = self.upnl(block)
        if upnl == None: return 0
        return 100 * upnl / self.bought_usd
    

    #-------------------------------
    # for live testing

    def live_upnl(self, dict):
        rpnl = self.rpnl()
        if self.amount > 0:
            if self.name in dict.items():
                upnl = dict[self.name].value
                return upnl + rpnl
        return rpnl
    
    def live_upnl_perc(self, dict):
        if self.amount < 0 or self.bought_usd <= 0: return 0
        upnl = self.live_upnl(dict)
        return 100 * upnl / self.bought_usd

    #-------------------------------
    
    def __str__(self):
        return (f"Coin: {self.name}, Amount: {int(self.amount)}, B.Amount: {int(self.bought_amount)}\n"
                f" Bought USD: {int(self.bought_usd)}, Sold USD: {int(self.sold_usd)}")

# --------- end of class Coin ---------


# implementation is hidden (I can't give my edge in the market away)
def insiders_filter(address, ticker, start = None, end = None, block = None):
    return False


# returns buys for coin: ca in pages, format: [(address, time)...]
def find_buy_addresses(ca,pages):
    pools = db.pools.find_one({'contract_address': ca}, {'_id': 0, 'pools': 1})
    if 'pools' in pools:
        pools = pools['pools']
    else: raise ValueError(f"No pool for contract address")
    exceptions = db.exceptions.find_one({'contract_address': ca}, {'_id': 0, 'exceptions': 1})
    if 'exceptions' in exceptions:
        exceptions = exceptions['exceptions']
    else: raise ValueError(f"No exceptions for contract address")

    result = moral.get_buys(ca, pools, exceptions, pages)
    buys = list(map(lambda x: (x['to_address'], x['block_timestamp']), result))
    return buys


# find buys of coin and stores in db
def get_store_buys(coin, pages=1):
    try:
        coin_doc = db.addresses.find_one({'name': coin})
        if not coin_doc:
            print('NAME not in collection')
            return
        coin_address = coin_doc['address']
        result = find_buy_addresses(coin_address, pages)
        # store in case of rate limits to work on later without the need for repetitive queries
        print('UPDATING DATABASE')
        for address, time in result:
            query = {'address': address}
            update = {}
            upsert = False
            doc = db.buys.find_one(query)
            # if not in db
            #   already in and failed
            #   already in and pending
            #   already in and succeeded
            if not doc:
                update = {'$set': {'address': address, 'status': 'pending', 'num_fails': 0, 'time': time}}
                upsert = True
            elif doc['status'] == 'failed':
                if doc['num_fails'] < cons.NUM_FAILS:
                    update = {'$set': {'status': 'pending', 'time': time}}
            elif doc['status'] == 'pending':
                if doc['time'] < time:
                    update = {'$set': {'time': time}}
            if update:
                db.buys.update_one(query, update, upsert)
        print('FINISHED')
    except Exception as e:
        print(f"ERROR:\n{e}")


# gets pending wallets in db and filters them
def find_insiders(coin, start, end):
    # pipeline to get oldest pending address
    pipeline = [
        {
            '$match': { 'status': 'pending' }
        },
        {
            '$sort': { 'time': 1 }
        },
        {
            '$limit': 1
        }
    ]
    try:
        coin_doc = db.addresses.find_one({'name': coin})
        if not coin_doc:
            print('NAME not in collection')
            return
        block = etherscan.get_block_number(int(end/1000))
        while True:
            buyer_doc = list(db.buys.aggregate(pipeline))
            if buyer_doc:
                buyer_doc = buyer_doc[0]
            else: 
                print('NO PENDING ADDRESSES')
                break
            result = insiders_filter(buyer_doc['address'], coin, start, end, block)
            if result:
                db.buys.update_one({'_id': buyer_doc['_id']},
                                   {'$set': {'status': 'passed'}})
                db.insiders.insert_one({'address':buyer_doc['address'], 'coin': coin})
                print(f"INSIDER FOUND: {buyer_doc['address']}")
            else:
                db.buys.update_one({'_id': buyer_doc['_id']},
                                   {'$set': {'status': 'failed'},
                                    '$inc': {'num_fails': 1}})
                print(f"FAILED: {buyer_doc['address']}")
    except Exception as e:
        print(f"ERROR:\n{e}")
    print('FINSIHED')


# prints summary of insiders in the db
def getInsiders(coin, start, end):
    res = db.insiders.find()
    count = 0
    for i in res: 
        count += 1
        print('------------------------------------------------------------------------')
        address = i['address']
        print(f"\n{count}. {address}:\n")
        insiders_filter(address, coin, start, end)
        print('------------------------------------------------------------------------\n\n')



# live wallet tester 
def isWalletGood(address, start, end):
    coins = {}  # dict of all coins
    txn_log = zerion.get_txns(address, start, end)
    all_holdings = zerion.get_positions(address)
    for txn in txn_log:
        if txn.type == 'trade':
            # inwards
            in_coin = txn.inwards['symbol']
            if in_coin not in cons.AVOID:
                # add to dict if necessary
                if in_coin not in coins:
                    ca = txn.inwards['ca']
                    coins[in_coin] = Coin(in_coin,ca)
                coins[in_coin].amount += txn.inwards['amount']
                coins[in_coin].bought_amount += txn.inwards['amount']
                if not txn.out['value'] == None:
                    coins[in_coin].bought_usd += txn.out['value']
                elif not txn.inwards['value'] == None:
                    coins[in_coin].bought_usd += txn.inwards['value']
            # outwards
            out_coin = txn.out['symbol']
            if out_coin not in cons.AVOID:
                if out_coin not in coins:
                    ca = txn.out['ca']
                    coins[out_coin] = Coin(out_coin, ca)
                coins[out_coin].amount -= txn.out['amount']
                if not txn.inwards['value'] == None:
                    coins[out_coin].sold_usd += txn.inwards['value']
                elif not txn.out['value'] == None:
                    coins[in_coin].sold_usd += txn.inwards['value']
        elif txn.type == 'send':
            coin = txn.out['symbol']
            if coin not in cons.AVOID:
                if coin not in coins:
                    ca = txn.out['ca']
                    coins[coin] = Coin(coin, ca)
                coins[coin].amount -= txn.out['amount']
                if not txn.out['value'] == None:
                    coins[coin].sold_usd += txn.out['value']
    
    rem = []    # remove spam coins
    for coin_name, coin in coins.items():
        upnl_perc = coin.live_upnl_perc(all_holdings)
        if upnl_perc == 0: rem.append(coin_name)
    for coin in rem:
        del coins[coin]
    for coin_name, coin in coins.items():
        print(coin_name, "\n", coin, f"Profit: ${int(coin.live_upnl(all_holdings))}", 
              f"{int(coin.live_upnl_perc(all_holdings))}%")
    
    