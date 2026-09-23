# Kalshi Trading Engine

Typed, extensible Kalshi API v2 engine for `KXBTC15M` markets. The default
execution mode is dry-run and does not submit orders.

## Setup

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

Set `KALSHI_KEY_ID` and `KALSHI_PRIVATE_KEY_PATH` in `.env`. Use the demo
environment while developing. Private key files are ignored by Git.

## Run

```bash
python main.py
```

The polling loop discovers the nearest open `KXBTC15M` market every 10
seconds, evaluates the sample spread strategy, and logs simulated orders.
`ExecutionEngine` must be explicitly constructed with `dry_run=False` before
any live order can be submitted.

## Test

```bash
python -m unittest discover -s tests -v
```

The tests are offline and do not require a private key or live API access.