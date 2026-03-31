import os
from dotenv import load_dotenv

load_dotenv()

ETHEREUM_CHAIN_ID = 1
ARBITRUM_CHAIN_ID = 42161
BASE_CHAIN_ID = 8453
MEZO_CHAIN_ID = 31612

ORACLE_HELPER_ETHEREUM = "0x000000005F543c38d5ea6D0bF10A50974Eb55E35"
ORACLE_HELPER_MEZO = "0x00000002FC616d31133ab9AD626E43a94674D5B6"

CHAIN_ID_TO_NAME = {
    ETHEREUM_CHAIN_ID: "ethereum",
    ARBITRUM_CHAIN_ID: "arbitrum",
    BASE_CHAIN_ID: "base",
    MEZO_CHAIN_ID: "mezo",
}

AVERAGE_BLOCKS = {
    ETHEREUM_CHAIN_ID: 12.0,
    ARBITRUM_CHAIN_ID: 1.0,
    BASE_CHAIN_ID: 1.0,
    MEZO_CHAIN_ID: 1.0,
}

CHAIN_NAME_TO_ID = {
    "ethereum": ETHEREUM_CHAIN_ID,
    "arbitrum": ARBITRUM_CHAIN_ID,
    "base": BASE_CHAIN_ID,
    "mezo": MEZO_CHAIN_ID,
}

CHAIN_RPC_STATE_OVERRIDES = {
    ETHEREUM_CHAIN_ID: True,
    ARBITRUM_CHAIN_ID: True,
    BASE_CHAIN_ID: True,
    MEZO_CHAIN_ID: False,
}


def _unique_urls(*urls: str | None) -> list[str]:
    return list(dict.fromkeys(u for u in urls if u is not None and u != ""))


RPC_URLS: dict[int, list[str]] = {
    ETHEREUM_CHAIN_ID: _unique_urls(
        os.environ.get("RPC_URL"),
        "https://lb.drpc.live/ethereum/AkFudnd9E0EuuidkFQPqRtsUNV5CxasR7rSMruxS_uXt",
        "https://rpc.mevblocker.io",
        "https://eth.drpc.org",
    ),
    ARBITRUM_CHAIN_ID: _unique_urls(
        os.environ.get("ARBITRUM_RPC_URL"),
        "https://arbitrum.drpc.org",
    ),
    BASE_CHAIN_ID: _unique_urls(
        os.environ.get("BASE_RPC_URL"),
        "https://mainnet.base.org",
        "https://base.drpc.org",
    ),
    MEZO_CHAIN_ID: _unique_urls(
        os.environ.get("MEZO_RPC_URL"),
        "https://mezo.drpc.org",
        "https://rpc-internal.mezo.org",
        "https://mainnet.mezo.public.validationcloud.io",
    ),
}

INSTANCE_ABI = [
    {
        "type": "function",
        "name": "collect",
        "inputs": [],
        "outputs": [
            {
                "name": "balances",
                "type": "tuple[]",
                "internalType": "struct ICollector.Balance[]",
                "components": [
                    {"name": "holder", "type": "address", "internalType": "address"},
                    {"name": "asset", "type": "address", "internalType": "address"},
                    {"name": "balance", "type": "int256", "internalType": "int256"},
                    {"name": "metadata", "type": "string", "internalType": "string"},
                ],
            }
        ],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "collectPendingDeposits",
        "inputs": [],
        "outputs": [
            {"name": "assets", "type": "address[]", "internalType": "address[]"},
            {"name": "balances", "type": "uint256[]", "internalType": "uint256[]"},
        ],
        "stateMutability": "view",
    },
]

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    }
]


ORACLE_HELPER_ABI = [
    {
        "inputs": [
            {"internalType": "contract Vault", "name": "vault", "type": "address"},
            {"internalType": "uint256", "name": "totalAssets", "type": "uint256"},
            {
                "components": [
                    {"internalType": "address", "name": "asset", "type": "address"},
                    {"internalType": "uint256", "name": "priceD18", "type": "uint256"},
                ],
                "internalType": "struct OracleHelper.AssetPrice[]",
                "name": "assetPrices",
                "type": "tuple[]",
            },
        ],
        "name": "getPricesD18",
        "outputs": [
            {"internalType": "uint256[]", "name": "pricesD18", "type": "uint256[]"}
        ],
        "stateMutability": "view",
        "type": "function",
    }
]

WSTETH_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "_wstETHAmount", "type": "uint256"}
        ],
        "name": "getStETHByWstETH",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    }
]

ORACLE_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "asset", "type": "address"}],
        "name": "getReport",
        "outputs": [
            {
                "components": [
                    {"internalType": "uint224", "name": "priceD18", "type": "uint224"},
                    {"internalType": "uint32", "name": "timestamp", "type": "uint32"},
                    {"internalType": "bool", "name": "isSuspicious", "type": "bool"},
                ],
                "internalType": "struct IOracle.DetailedReport",
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    }
]

AGGREGATOR_ABI = [
    {
        "inputs": [],
        "name": "latestAnswer",
        "outputs": [{"internalType": "int256", "name": "", "type": "int256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

ERC4626_ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "shares", "type": "uint256"}],
        "name": "convertToAssets",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    }
]

MULTICALL_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11"
MULTICALL_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "target", "type": "address"},
                    {"internalType": "bytes", "name": "callData", "type": "bytes"},
                ],
                "internalType": "struct Multicall3.Call[]",
                "name": "calls",
                "type": "tuple[]",
            }
        ],
        "name": "aggregate",
        "outputs": [
            {"internalType": "uint256", "name": "blockNumber", "type": "uint256"},
            {"internalType": "bytes[]", "name": "returnData", "type": "bytes[]"},
        ],
        "stateMutability": "payable",
        "type": "function",
    },
]

PYTH_ADDRESS = "0x4305FB66699C3B2702D4d05CF36551390A4c69C6"
PYTH_ADDRESS_MEZO = "0x2880aB155794e7179c9eE2e38200202908C17B43"
PYTH_ABI = [
    {
        "inputs": [{"internalType": "bytes32", "name": "id", "type": "bytes32"}],
        "name": "getPriceUnsafe",
        "outputs": [
            {
                "components": [
                    {"internalType": "int64", "name": "price", "type": "int64"},
                    {"internalType": "uint64", "name": "conf", "type": "uint64"},
                    {"internalType": "int32", "name": "expo", "type": "int32"},
                    {
                        "internalType": "uint256",
                        "name": "publishTime",
                        "type": "uint256",
                    },
                ],
                "internalType": "struct PythStructs.Price",
                "name": "price",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
]
