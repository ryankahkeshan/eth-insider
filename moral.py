from moralis import evm_api
import constants as cons
from datetime import datetime, timedelta
import etherscan
import eth

def make_params(**kwargs):
    params = {}
    for key,value in kwargs.items():
        params[key] = value
    return params

# getWalletBalances retrieves eth and eth tokens in wallet. Returns info such as
# ca, balance of token, usd price & value, & more
def get_wallet_balances(wallet = cons.ZACH):
    result = evm_api.wallets.get_wallet_token_balances_price(
        api_key=cons.MORALIS_KEY,
        params=make_params(chain='eth',address=wallet)
    )
    print(result)

# 30 CU - 20 RL
def get_profitablity(wallet = cons.ZACH):
    result = evm_api.wallets.get_wallet_profitability_summary(
        api_key=cons.MORALIS_KEY,
        params=make_params(chain='eth',address=wallet)
    )
    return result

# 50 CU - 20 RL
def get_transfers_by_contract(ca, cu = None):
    params = make_params(chain='eth',order='ASC',address=ca,limit=100,**({'cursor': cu} if cu is not None else {}))

    result = evm_api.token.get_token_transfers(
        api_key=cons.MORALIS_KEY,
        params=params,
    )
    return result['result'], result['cursor']

# returns all buys, meaning all txns that have pool as a from address
# pages * 50 CU - 20 RL
def get_buys(ca,pools, exceptions, pages):
    all_txns = []
    # get all transactions
    for i in range(pages):
        print(f"FETCHING PAGE {i}")
        txns, res = get_transfers_by_contract(ca,res) if i != 0 else get_transfers_by_contract(ca)
        all_txns.extend(txns)
        if res == None: break
    # filter for only buys from token's pools and not in exceptions
    return list(filter(lambda txn: True if (txn['from_address'] in pools)
                        and (txn['to_address'] not in exceptions) else False, all_txns))

# deprecated
def get_sells(ca,pool,pages):
    all_txns = []
    # get all transactions
    for i in range(pages):
        txns, res = get_transfers_by_contract(ca,res) if i != 0 else get_transfers_by_contract(ca)
        all_txns.extend(txns)
    # filter for only buys from specific pool
    sells = list(filter(lambda txn: True if txn['to_address'] == pool else False, all_txns))
    for i in sells:
        print(i['from_address'])

# filters out potential scams
# pages * 50 CU - 20 RL
def get_transfers_by_wallet(add, pages):
    cursor = None
    count = 0
    answer = []
    while True:
        result = evm_api.token.get_wallet_token_transfers(
            api_key=cons.MORALIS_KEY,
            params=make_params(chain='eth',order='DESC',address=add, **({'cursor': cursor} if cursor is not None else {})),
        )
        rem_spam = list(filter(lambda x:x['security_score']!= None, result['result']))
        answer.extend(rem_spam)
        # get next pages
        if count >= pages-1 or result['cursor'] == None: break
        else: 
            cursor = result['cursor']
            count += 1
    return answer

# in transfers.txt
# 150 CU - 30 RL
def get_wallet_history(add):
    result = evm_api.wallets.get_wallet_history(
        api_key=cons.MORALIS_KEY,
        params=make_params(chain='eth',order='DESC',address=add,
                           include_internal_transactions=True),
    )
    print(result)

# 50 CU - 20 RL
def get_pnl_breakdown(add):
    result = evm_api.wallets.get_wallet_profitability(
        api_key=cons.MORALIS_KEY,
        params=make_params(chain='eth',address=add),
    )
    return result

# 50 CU - 20 RL
def get_token_price(ca, block = None):
    try:
        if block == None:
            result = evm_api.token.get_token_price(
                api_key=cons.MORALIS_KEY,
                params=make_params(chain='eth',address=ca)
            )
        else:
            result = evm_api.token.get_token_price(
                api_key=cons.MORALIS_KEY,
                params=make_params(chain='eth',address=ca,to_block=block)
            )
        return result
    except:
        return None

# 50 CU
# tokens should be of the form [ca, ca, ca,...] and valid
def get_multiple_prices(tokens, block):
    res = {}
    try:
        if len(tokens) == 0: return res
        elif len(tokens) == 1:
            coin_data = get_token_price(tokens[0], int(block))
            if coin_data:
                res[coin_data['tokenAddress']] = coin_data['usdPriceFormatted']
            else: res[tokens[0]] = None
            return res
        
        body_tokens = list(map(lambda x: {"token_address": x, "to_block": block}, tokens))
        body = {"tokens": body_tokens}

        result = evm_api.token.get_multiple_token_prices(
            api_key=cons.MORALIS_KEY,
            body=body,
            params=make_params(chain='eth'),
        )

        for coin in result:
            ca = coin['tokenAddress']
            if eth.is_valid_eth_address(ca):
                res[ca] = coin['usdPriceFormatted']
        return res
    except Exception as e:
        print(f"ERROR: MORALIS GET_MULTIPLE_PRICES_AT_BLOCK\n{e}")

