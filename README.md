# msvUSD Helper

Scripts for computing the msvUSD oracle report and balance distributions across Ethereum, Arbitrum, Base, and Mezo chains.

## Requirements

- Python 3.11+
- Node.js + Yarn
- [Foundry](https://book.getfoundry.sh/getting-started/installation) — `anvil` is required for Mezo chain, which does not support RPC state overrides

## Setup

```bash
./install.sh
```

This installs Python dependencies and Foundry (if `anvil` is not already on your PATH).

Copy `.env.example` to `.env` and fill in the RPC URLs:

```bash
cp .env.example .env
```

### Environment Variables

| Variable | Description |
|---|---|
| `RPC_URL` | Ethereum mainnet RPC |
| `ARBITRUM_RPC_URL` | Arbitrum One RPC |
| `BASE_RPC_URL` | Base mainnet RPC |
| `MEZO_RPC_URL` | Mezo mainnet RPC |

All variables are optional — public fallback RPCs are used when not set.

## Configuration

Asset price configuration is split per chain:

| File | Chain |
|---|---|
| `msvUSD.json` | Asset oracle config (all chains) |
| `msvUSD:ethereum.json` | Ethereum collector state override |
| `msvUSD:arbitrum.json` | Arbitrum collector state override |
| `msvUSD:base.json` | Base collector state override |
| `msvUSD:mezo.json` | Mezo collector state override |

## Usage

### Oracle Report

Computes the msvUSD price report and current APY:

```bash
python3 msvUSD.py
```

With a fixed timestamp:
```bash
python3 msvUSD.py --fixed-timestamp 1700000000
```

With extra off-chain rewards included in TVL:
```bash
python3 msvUSD.py --reward-asset usdc --reward-amount 5000
# reward-asset: usdc | usdt | musd
```

With a custom config file (e.g. `msvUSD-staging.json`):
```bash
python3 msvUSD.py --config msvUSD-staging
```

### Distribution

Collects per-subvault balances and writes them to `./distributions/msvUSD_{timestamp}.json`:

```bash
python3 msvUSD.py --distribution true
```

### Yarn Scripts

```bash
yarn msvusd:oracle-report       # run oracle report
yarn msvusd:distribution        # run distribution snapshot
yarn install:python             # install Python dependencies
yarn prettier                   # format Python files with black
```

## Anvil

Mezo does not support RPC-level state overrides, so a local [Anvil](https://book.getfoundry.sh/anvil/) fork is used automatically when processing Mezo chain data. Anvil is started, used, and stopped per call — no manual setup is needed.

`install.sh` handles Foundry installation. Verify after setup:
```bash
anvil --version
```
