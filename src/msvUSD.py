import json
import socket
import subprocess
import time
import os
import shutil
from contextlib import contextmanager
from web3 import Web3
import argparse
from typing import List, Tuple, Dict, Any

from asset_oracle import get_prices
from common import get_state_override_status, get_w3, find_block
from constants import (
    INSTANCE_ABI,
    ORACLE_HELPER_ABI,
    ORACLE_ABI,
    MEZO_CHAIN_ID,
    ORACLE_HELPER_MEZO,
    PYTH_ABI,
    PYTH_ADDRESS_MEZO,
    RPC_URLS,
)

USDC = "0x04671C72Aab5AC02A03c1098314b1BB6B560c197"
USDT = "0xeB5a5d39dE4Ea42C2Aa6A57EcA2894376683bB8E"
MUSD = "0xdD468A1DDc392dcdbEf6db6e34E89AA338F9F186"

USDC_ORACLE_ID = "0xeaa020c61cc479712813461ce153894a96a6c00b21ed0cfc2798d1f9a9e9c94a"
USDT_ORACLE_ID = "0x2b89b9dc8fdf9f34709a5b106b472f0f39bb6ca9ce04b0fd7f2e971688e2e53b"
MUSD_ORACLE_ID = "0x0617a9b725011a126a2b9fd53563f4236501f32cf76d877644b943394606c6de"

PYTH_ORACLE_IDS = {USDC: USDC_ORACLE_ID, USDT: USDT_ORACLE_ID, MUSD: MUSD_ORACLE_ID}

VAULT_SYMBOL = "msvUSD"
VAULT_ADDRESS = "0x07AFFA6754458f88db83A72859948d9b794E131b"
ORACLE_ADDRESS = "0xe3FDB2436c0F6B16F6b6ed903B90bE8BF0D0Cf85"

ANVIL_RETRIES = 3


def get_distribution_data(timestamp: int = 0) -> Tuple[List, Dict]:
    data = load_data()
    timestamp, prices_of = get_prices(VAULT_SYMBOL, timestamp)
    return get_distributions(data, timestamp, prices_of), prices_of


def _start_anvil_fork(
    chain_id: int, block_number: int, state_overrides: List[Dict]
) -> Tuple:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    if not shutil.which("anvil"):
        raise RuntimeError(
            "Anvil (from Foundry) is required for chains without RPC state override support. "
            "Install Foundry: https://book.getfoundry.sh/getting-started/installation"
        )

    proc = subprocess.Popen(
        [
            "anvil",
            "--fork-url",
            RPC_URLS[chain_id][0],
            "--fork-block-number",
            str(block_number),
            "--port",
            str(port),
            "--host",
            "127.0.0.1"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        fork_w3 = Web3(Web3.HTTPProvider(f"http://127.0.0.1:{port}"))
        for _ in range(30):
            try:
                if fork_w3.is_connected():
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError(f"Anvil fork for chain {chain_id} did not start in time")

        for item in state_overrides:
            fork_w3.provider.make_request(
                "anvil_setCode",
                [Web3.to_checksum_address(item["address"]), item["bytecode"]],
            )

        return proc, fork_w3
    except Exception:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        raise


@contextmanager
def _anvil_fork(chain_id: int, block_number: int, state_overrides: List[Dict]):
    last_error = None
    for attempt in range(ANVIL_RETRIES):
        if attempt > 0:
            time.sleep(1)
        try:
            proc, fork_w3 = _start_anvil_fork(chain_id, block_number, state_overrides)
            break
        except Exception as e:
            last_error = e
    else:
        raise last_error
    try:
        yield fork_w3
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise


def get_pending_deposits(
    prices_of: Dict[str, Any], chain_id: int, block_number: int
) -> List[Dict[str, Any]]:
    data = load_data()
    pending_deposits = []
    w3 = get_w3(chain_id)
    override_status = get_state_override_status(chain_id)
    state_overrides = data[chain_id]

    if override_status:
        instance = w3.eth.contract(
            address=Web3.to_checksum_address(state_overrides[0]["address"]),
            abi=INSTANCE_ABI,
        )
        (
            pending_assets,
            pending_balances,
        ) = instance.functions.collectPendingDeposits().call(
            block_identifier=block_number,
            state_override={
                Web3.to_checksum_address(item["address"]): {"code": item["bytecode"]}
                for item in state_overrides
            },
        )
    else:
        with _anvil_fork(chain_id, block_number, state_overrides) as fork_w3:
            instance = fork_w3.eth.contract(
                address=Web3.to_checksum_address(state_overrides[0]["address"]),
                abi=INSTANCE_ABI,
            )
            (
                pending_assets,
                pending_balances,
            ) = instance.functions.collectPendingDeposits().call()

    for index in range(len(pending_assets)):
        asset = pending_assets[index]
        balance = pending_balances[index]
        price, decimals = prices_of[(chain_id, asset)]
        usd_value = balance * price // 10**decimals
        pending_deposits.append(
            {
                "chain_id": chain_id,
                "block_number": block_number,
                "subvault": VAULT_ADDRESS,
                "asset": asset,
                "balance": balance,
                "balance_decimals": decimals,
                "metadata": "PendingDeposits",
                "value": usd_value,
                "value_decimals": 8,
            }
        )
    return pending_deposits


def get_distributions(
    data: Dict[int, Dict],
    timestamp: int,
    prices_of: Dict[Tuple[int, str], Tuple[int, int]],
) -> List[Dict[str, Any]]:
    distribution: List[Dict[str, Any]] = []
    for chain_id in data:
        w3 = get_w3(chain_id)
        state_overrides = data[chain_id]
        override_status = get_state_override_status(chain_id)

        block_number = find_block(chain_id, timestamp)

        if override_status:
            instance = w3.eth.contract(
                address=Web3.to_checksum_address(state_overrides[0]["address"]),
                abi=INSTANCE_ABI,
            )
            response = instance.functions.collect().call(
                block_identifier=block_number,
                state_override={
                    Web3.to_checksum_address(item["address"]): {
                        "code": item["bytecode"]
                    }
                    for item in state_overrides
                },
            )
        else:
            with _anvil_fork(chain_id, block_number, state_overrides) as fork_w3:
                instance = fork_w3.eth.contract(
                    address=Web3.to_checksum_address(state_overrides[0]["address"]),
                    abi=INSTANCE_ABI,
                )
                response = instance.functions.collect().call()

        for subvault, asset, value, metadata in response:
            price, decimals = prices_of[(chain_id, asset)]
            usd_value = value * price // 10**decimals
            distribution.append(
                {
                    "chain_id": chain_id,
                    "block_number": block_number,
                    "subvault": subvault,
                    "asset": asset,
                    "balance": value,
                    "balance_decimals": decimals,
                    "metadata": metadata,
                    "value": usd_value,
                    "value_decimals": 8,
                }
            )
    return distribution


def calculate_total_assets_usd(
    data: Dict[int, Dict],
    timestamp: int,
    prices_of: Dict[Tuple[int, str], Tuple[int, int]],
) -> int:
    total_assets = 0
    response = get_distributions(data, timestamp, prices_of)
    for item in response:
        total_assets += item["value"]
    return total_assets


def load_data():
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    path = os.path.join(data_dir, VAULT_SYMBOL)
    data = {
        1: json.load(open(f"{path}:ethereum.json", "r")),
        42161: json.load(open(f"{path}:arbitrum.json", "r")),
        8453: json.load(open(f"{path}:base.json", "r")),
        31612: json.load(open(f"{path}:mezo.json", "r")),
    }
    return data


def get_pyth_price_d18(w3: Web3, oracle_id: str, block_number: int):
    pyth = w3.eth.contract(address=PYTH_ADDRESS_MEZO, abi=PYTH_ABI)
    result = pyth.functions.getPriceUnsafe(oracle_id).call(
        block_identifier=block_number
    )
    price = int(result[0])
    decimal_shift = int(result[2])
    return int(10**18 * price * 10**decimal_shift)


def get_relative_price(
    w3: Web3,
    block_number: int,
    asset: str,
    asset_decimals: int,
    base_asset: str,
    base_asset_decimals: int,
) -> int:
    asset_price_d18 = get_pyth_price_d18(w3, PYTH_ORACLE_IDS[asset], block_number)
    base_asset_price_d18 = get_pyth_price_d18(
        w3, PYTH_ORACLE_IDS[base_asset], block_number
    )
    return (
        10 ** (18 + base_asset_decimals - asset_decimals)
        * asset_price_d18
        // base_asset_price_d18
    )


def get_report(
    fixed_timestamp: int,
    reward_asset: str,
    reward_amount: float,
    print_logs: bool = False,
    symbol_override=None,
) -> List[Tuple[str, int]]:
    timestamp, prices_of = get_prices(
        VAULT_SYMBOL if not symbol_override else symbol_override, fixed_timestamp
    )

    data = load_data()
    total_assets = calculate_total_assets_usd(data, timestamp, prices_of)
    extra_rewards = []
    if reward_asset and reward_amount:
        reward_asset = reward_asset.lower()
        rewards = float(reward_amount)

        remappings = {"usdc": USDC, "usdt": USDT, "musd": MUSD}
        if reward_asset not in remappings:
            raise Exception("Invalid reward asset")

        extra_rewards.append((MEZO_CHAIN_ID, remappings[reward_asset], rewards))

        for chain_id, asset, amount in extra_rewards:
            price, _ = prices_of[(chain_id, asset)]
            total_assets += int(price * amount)
            if print_logs:
                print(f"rewards asset = {asset}, reward amount = {amount}")

    if print_logs:
        if extra_rewards:
            print(f"{VAULT_SYMBOL} tvl with rewards: {round(total_assets/1e8, 2)}$")
        else:
            print(f"{VAULT_SYMBOL} tvl: {round(total_assets/1e8, 2)}$")

    base_asset = (
        MEZO_CHAIN_ID,
        USDC,
    )

    base_asset_price, base_asset_decimals = prices_of[base_asset]
    total_assets = total_assets * 10**base_asset_decimals // base_asset_price
    if print_logs:
        if extra_rewards:
            print(f"{VAULT_SYMBOL} tvl with rewards: {round(total_assets/1e6, 2)} USDC")
        else:
            print(f"{VAULT_SYMBOL} tvl: {round(total_assets/1e6, 2)} USDC")

    w3 = get_w3(MEZO_CHAIN_ID)

    block_number = find_block(MEZO_CHAIN_ID, timestamp)
    asset_prices = [
        [USDC, 0],
        [MUSD, get_relative_price(w3, block_number, MUSD, 18, USDC, 6)],
        [USDT, get_relative_price(w3, block_number, USDT, 6, USDC, 6)],
    ]

    oracle_helper = w3.eth.contract(
        address=ORACLE_HELPER_MEZO, abi=ORACLE_HELPER_ABI
    )
    prices_d18 = oracle_helper.functions.getPricesD18(
        VAULT_ADDRESS, total_assets, asset_prices
    ).call(block_identifier=block_number)

    short_response = []
    for x, y in zip(
        [USDC, MUSD, USDT],
        prices_d18,
    ):
        short_response.append([x, str(y)])
    return short_response, timestamp


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixed-timestamp", type=int, default=0)
    parser.add_argument("--reward-asset", type=str, default="")
    parser.add_argument("--reward-amount", type=float, default=0.0)
    parser.add_argument("--distribution", type=bool, default=False)
    parser.add_argument("--config", type=str, default="")

    args = parser.parse_args()

    if args.distribution:
        timestamp, prices_of = get_prices(VAULT_SYMBOL, args.fixed_timestamp)
        data = load_data()
        response = get_distributions(data, timestamp, prices_of)
        with open(f"./distributions/{VAULT_SYMBOL}_{timestamp}.json", "w") as f:
            json.dump(response, f, indent=2)
    else:
        report, timestamp = get_report(
            args.fixed_timestamp,
            args.reward_asset,
            args.reward_amount,
            print_logs=True,
            symbol_override=args.config,
        )
        print("OracleReport:", str(report).replace("'", '"'))

        # apy calculation
        w3 = get_w3(MEZO_CHAIN_ID)
        block_number = find_block(MEZO_CHAIN_ID, timestamp)
        oracle_contract = w3.eth.contract(address=ORACLE_ADDRESS, abi=ORACLE_ABI)
        prev_report = oracle_contract.functions.getReport(USDC).call(
            block_identifier=block_number
        )
        current_report = [int(report[0][1]), timestamp]
        report_apy = (
            (prev_report[0] / current_report[0])
            ** (365 * 24 * 3600 / (current_report[1] - prev_report[1]))
            - 1
        ) * 100
        print(f"apy: {round(report_apy, 5)}%")

        if args.fixed_timestamp:
            print("at fixed timestamp: {}".format(args.fixed_timestamp))
        else:
            print("at timestamp: {}".format(timestamp))
