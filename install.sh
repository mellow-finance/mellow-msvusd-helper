#!/bin/bash
set -e

if ! command -v yarn &> /dev/null; then
    npm install -g yarn
fi

yarn install
pip install -r requirements.txt

if ! command -v anvil &> /dev/null; then
    curl -L https://foundry.paradigm.xyz | bash
    foundryup
fi
