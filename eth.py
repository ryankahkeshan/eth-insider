import re 

def is_valid_eth_address(address):
    return bool(re.match(r"^0x[a-fA-F0-9]{40}$", address))