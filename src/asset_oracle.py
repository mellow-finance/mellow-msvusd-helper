from web3 import Web3
from eth_abi import decode

import os
import requests
import json
import time
from typing import Tuple, Dict, Any

from common import get_w3, find_block
from constants import (
    AGGREGATOR_ABI,
    ERC4626_ABI,
    MULTICALL_ADDRESS,
    MULTICALL_ABI,
    PYTH_ABI,
)


def _fill_prices(
    w3s: Dict[int, Tuple[Web3, int]],
    prices: Dict[Tuple[int, str], int],
    chain_id: int,
    asset: str,
    config: Dict[str, Dict[str, Any]],
) -> int:
    if (chain_id, asset) in prices:
        return prices[(chain_id, asset)]

    asset_config = config[str(chain_id)][asset]

    if asset_config["type"] == "min-usd":
        w3, block_number = w3s[asset_config["chain_id"]]
        aggregated_prices = []
        for oracle_address in asset_config["oracle_addresses"]:
            oracle_price = (
                w3.eth.contract(address=oracle_address, abi=AGGREGATOR_ABI)
                .functions.latestAnswer()
                .call(block_identifier=block_number)
            )
            aggregated_prices.append(oracle_price)
        price = min(aggregated_prices)
        if "capped_value" in asset_config:
            price = min(price, asset_config["capped_value"])
        prices[(chain_id, asset)] = price
        return price
    elif asset_config["type"] == "usd":
        w3, block_number = w3s[asset_config["chain_id"]]
        price = (
            w3.eth.contract(address=asset_config["oracle_address"], abi=AGGREGATOR_ABI)
            .functions.latestAnswer()
            .call(block_identifier=block_number)
        )
        if "capped_value" in asset_config:
            price = min(price, asset_config["capped_value"])
        prices[(chain_id, asset)] = price
        return price
    elif asset_config["type"] == "ref":
        price = _fill_prices(
            w3s, prices, asset_config["chain_id"], asset_config["asset"], config
        )
        prices[(chain_id, asset)] = price
        return price
    elif asset_config["type"] == "erc4626":
        underlying_price = _fill_prices(
            w3s, prices, asset_config["chain_id"], asset_config["asset"], config
        )
        w3, block_number = w3s[asset_config["chain_id"]]
        price = (
            w3.eth.contract(address=asset, abi=ERC4626_ABI)
            .functions.convertToAssets(underlying_price)
            .call(block_identifier=block_number)
        )
        prices[(chain_id, asset)] = price
        return price
    elif asset_config["type"] == "pyth":
        w3, block_number = w3s[asset_config["chain_id"]]
        result = (
            w3.eth.contract(address=asset_config["pyth"], abi=PYTH_ABI)
            .functions.getPriceUnsafe(asset_config["oracle_id"])
            .call(block_identifier=block_number)
        )
        price = int(10 ** (8 + int(result[2])) * int(result[0]))
        if "capped_value" in asset_config:
            price = min(price, asset_config["capped_value"])
        prices[(chain_id, asset)] = price
        return price
    elif asset_config["type"] == "pyth-hermes":
        w3, block_number = w3s[asset_config["chain_id"]]
        timestamp = w3.eth.get_block(block_number)["timestamp"]
        url = "https://hermes.pyth.network/v2/updates/price/{}?ids%5B%5D={}"
        result = requests.get(url.format(timestamp, asset_config["oracle_id"])).json()
        result = result["parsed"][0]["price"]
        price = int(10 ** (8 + int(result["expo"])) * int(result["price"]))
        if "capped_value" in asset_config:
            price = min(price, asset_config["capped_value"])
        prices[(chain_id, asset)] = price
        return price
    else:
        raise Exception("Invalid asset type")


def get_prices(
    vault: str, timestamp: int = 0
) -> Tuple[int, Dict[Tuple[int, str], Tuple[int, int]]]:
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    config = json.load(open(os.path.join(data_dir, f"{vault}.json"), "r"))

    if not timestamp:
        timestamp = int(time.time())

    w3s = {}
    for chain_id in config:
        chain_id = int(chain_id)
        w3 = get_w3(chain_id)
        w3s[chain_id] = (w3, find_block(chain_id, timestamp))

    prices = {}
    batches = {}
    for chain_id in config:
        for asset in config[chain_id]:
            asset_config = config[chain_id][asset]
            if asset_config["type"] == "usd":
                if asset_config["chain_id"] not in batches:
                    batches[asset_config["chain_id"]] = set()
                batches[asset_config["chain_id"]].add(asset_config["oracle_address"])

    cached_values = {}
    for chain_id in batches:
        calls = []
        for oracle_address in batches[chain_id]:
            calls.append([oracle_address, "0x50d25bcd"])
        w3, block_number = w3s[chain_id]
        multicall = w3.eth.contract(address=MULTICALL_ADDRESS, abi=MULTICALL_ABI)
        results = multicall.functions.aggregate(calls).call(
            block_identifier=block_number
        )[1]
        for i, call in enumerate(calls):
            cached_values[(chain_id, call[0])] = decode(["int256"], results[i])[0]

    for chain_id in config:
        for asset in config[chain_id]:
            asset_config = config[chain_id][asset]
            if asset_config["type"] == "usd":
                price = cached_values[
                    (asset_config["chain_id"], asset_config["oracle_address"])
                ]
                if "capped_value" in asset_config:
                    price = min(price, asset_config["capped_value"])
                prices[(int(chain_id), asset)] = price

    response = {}

    for chain_id in config:
        for asset in config[chain_id]:
            _fill_prices(w3s, prices, int(chain_id), asset, config)
            response[(int(chain_id), asset)] = (
                prices[(int(chain_id), asset)],
                config[chain_id][asset]["decimals"],
            )

    return (timestamp, response)


if __name__ == "__main__":
    response = get_prices("msvUSD")
    print(response)
