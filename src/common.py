import requests
import importlib
import os

from web3 import Web3
from typing import Any

from web3.providers.rpc.utils import ExceptionRetryConfiguration
from web3_multi_provider import FallbackProvider

from constants import (
    RPC_URLS,
    CHAIN_ID_TO_NAME,
    AVERAGE_BLOCKS,
    CHAIN_RPC_STATE_OVERRIDES,
)

_WEB3_MULTI_PROVIDER_TEST_PATCHED = False


# NOTE: Patch web3-multi-provider library to work with our test environment.
# FallbackProvider address normalization is not working with Docker service names.
def _patch_web3_multi_provider_for_tests() -> None:
    global _WEB3_MULTI_PROVIDER_TEST_PATCHED
    if _WEB3_MULTI_PROVIDER_TEST_PATCHED:
        return

    http_provider_proxy_module = importlib.import_module(
        "web3_multi_provider.http_provider_proxy"
    )
    http_async_provider_proxy_module = importlib.import_module(
        "web3_multi_provider.async_multi_http_provider"
    )
    util_module = importlib.import_module("web3_multi_provider.util")

    original_normalize_provider = util_module.normalize_provider

    def normalize_provider_for_tests(provider: Any) -> Any:
        if provider == "http://hardhat-ethereum:8545":
            return "hardhat-ethereum:8545"
        return original_normalize_provider(provider)

    util_module.normalize_provider = normalize_provider_for_tests
    http_provider_proxy_module.normalize_provider = normalize_provider_for_tests
    http_async_provider_proxy_module.normalize_provider = normalize_provider_for_tests
    _WEB3_MULTI_PROVIDER_TEST_PATCHED = True


def get_w3(chain_id: int) -> Web3:
    if os.environ.get("ENV") == "test":
        _patch_web3_multi_provider_for_tests()

    fallback_provider = FallbackProvider(
        RPC_URLS[chain_id],
        exception_retry_configuration=ExceptionRetryConfiguration(
            errors=(ConnectionError, requests.HTTPError, requests.Timeout),
            retries=3,
            backoff_factor=0.125,
        ),
        request_kwargs={"timeout": 3},
    )

    return Web3(fallback_provider)


def get_state_override_status(chain_id: int) -> bool:
    return CHAIN_RPC_STATE_OVERRIDES.get(chain_id, False)


def _find_block(
    w3: Web3,
    target_timestamp: int,
    average_block: float,
    closest_block: int,
    closest_block_timestamp: int,
    recursion_limit: int = 10,
) -> int:
    if abs(closest_block_timestamp - target_timestamp) < 2 * average_block:
        if closest_block_timestamp < target_timestamp:
            if closest_block_timestamp + average_block < target_timestamp:
                return closest_block + 2
            return closest_block + 1
        else:
            if closest_block_timestamp < target_timestamp + average_block:
                return closest_block

            if closest_block_timestamp < target_timestamp + 2 * average_block:
                return closest_block - 1

            return closest_block - 2

    closest_block = closest_block + int(
        (target_timestamp - closest_block_timestamp) / average_block
    )
    if recursion_limit == 0:
        return closest_block
    return _find_block(
        w3,
        target_timestamp,
        average_block,
        closest_block,
        w3.eth.get_block(closest_block)["timestamp"],
        recursion_limit - 1,
    )


def find_block(chain_id: int, target_timestamp: int) -> int:
    average_block = AVERAGE_BLOCKS[chain_id]
    try:
        response = requests.get(
            f"https://coins.llama.fi/block/{CHAIN_ID_TO_NAME[chain_id]}/{target_timestamp}"
        ).json()
        if response["timestamp"] > target_timestamp:
            return response["height"] - 1
        else:
            return response["height"]
    except:
        w3 = get_w3(chain_id)
        block = w3.eth.get_block("latest")
        block_number = block["number"] - int(
            (block["timestamp"] - target_timestamp) / average_block
        )

        return _find_block(
            w3,
            target_timestamp,
            average_block,
            block_number,
            w3.eth.get_block(block_number)["timestamp"],
        )
