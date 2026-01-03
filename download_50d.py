#!/usr/bin/env python3
"""
Download 50 days of real historical OHLCV data from Yahoo Finance and store in Redis
"""

import yfinance as yf
import json
import redis
import pandas as pd
from datetime import datetime, timedelta

# Yahoo Finance symbols mapping
YAHOO_SYMBOLS = {
    "MNQ": "^IXIC",
    "NVDA": "NVDA",
    "AMD": "AMD",
    "GS": "GS",
    "SLV": "SLV",
    "NET": "NET",
    "WDC": "WDC",
    "EWJ": "EWJ",
    "STLD": "STLD",
    "TTWO": "TTWO",
    "UBS": "UBS",
    "CRCL": "CRCL",
    "EURUSD": "EURUSD=X",
    "INRJPY": "INRJPY=X",
    "BRLGBP": "BRLGBP=X",
    "ETHUSD": "ETH-USD",
}


def get_historical_data():
    """Download 50 days of historical data from Yahoo Finance"""

    end_date = datetime.now()
    start_date = end_date - timedelta(
        days=80
    )  # Get extra days to ensure 50 trading days

    all_data = {}

    for display_symbol, yahoo_symbol in YAHOO_SYMBOLS.items():
        print(f"Downloading {display_symbol} ({yahoo_symbol})...")
        try:
            ticker = yf.Ticker(yahoo_symbol)
            df = ticker.history(start=start_date, end=end_date, interval="1d")

            if df.empty:
                print(f"  No data for {display_symbol}")
                continue

            # Take only last 50 records
            df = df.tail(50)

            # Remove timezone info if present
            if hasattr(df.index, "tz") and df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            # Convert to list of dicts
            records = []
            for idx, row in df.iterrows():
                record = {
                    "symbol": display_symbol,
                    "timestamp": int(idx.timestamp() * 1000),
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": round(float(row["Open"]), 4),
                    "high": round(float(row["High"]), 4),
                    "low": round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4),
                    "volume": int(row["Volume"]),
                }
                records.append(record)

            all_data[display_symbol] = records
            print(f"  Downloaded {len(records)} days of data")

        except Exception as e:
            print(f"  Error downloading {display_symbol}: {e}")

    return all_data


def store_in_redis(data, redis_host="localhost", redis_port=6379):
    """Store historical data in Redis with 50-day TTL"""

    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

    # Clear old data
    print("\nClearing old data from Redis...")
    for key in r.keys("equity:*"):
        r.delete(key)

    total_records = 0
    ttl_seconds = 50 * 24 * 60 * 60  # 50 days TTL

    for symbol, records in data.items():
        for record in records:
            key = f"equity:{symbol}:{record['timestamp']}"
            value = json.dumps(record)
            r.setex(key, ttl_seconds, value)

            # Add to sorted set for easy retrieval by timestamp
            r.zadd(f"symbol:{symbol}", {key: record["timestamp"]})
            r.expire(f"symbol:{symbol}", ttl_seconds)

        # Store metadata
        r.setex(f"meta:{symbol}:count", ttl_seconds, len(records))
        r.setex(f"meta:{symbol}:start", ttl_seconds, records[0]["date"])
        r.setex(f"meta:{symbol}:end", ttl_seconds, records[-1]["date"])

        total_records += len(records)
        print(f"  Stored {len(records)} records for {symbol}")

    print(f"\nTotal records stored: {total_records}")
    return total_records


def calculate_50d_changes(data):
    """Calculate 50-day changes for each symbol"""

    changes = {}

    for symbol, records in data.items():
        if len(records) >= 2:
            start_price = records[0]["close"]
            end_price = records[-1]["close"]
            change = ((end_price - start_price) / start_price) * 100
            changes[symbol] = round(change, 2)
        else:
            changes[symbol] = 0.0

    return changes


def get_current_prices(data):
    """Get current (most recent) prices from historical data"""

    current_prices = {}
    for symbol, records in data.items():
        if records:
            current_prices[symbol] = round(records[-1]["close"], 4)
    return current_prices


def calculate_volumes(data):
    """Calculate average volumes"""

    volumes = {}
    for symbol, records in data.items():
        if records:
            avg_vol = sum(r["volume"] for r in records) / len(records)
            volumes[symbol] = int(avg_vol)
    return volumes


if __name__ == "__main__":
    print("=" * 60)
    print("Downloading 50 days of historical data from Yahoo Finance")
    print("=" * 60 + "\n")

    # Download data
    data = get_historical_data()

    if not data:
        print("No data downloaded!")
        exit(1)

    # Store in Redis
    print("\n" + "=" * 60)
    print("Storing data in Redis (50-day TTL)...")
    print("=" * 60 + "\n")
    store_in_redis(data)

    # Calculate metrics
    print("\n" + "=" * 60)
    print("Calculating metrics...")
    print("=" * 60)

    changes = calculate_50d_changes(data)
    current_prices = get_current_prices(data)
    volumes = calculate_volumes(data)

    print("\nCurrent Prices:")
    for symbol, price in sorted(current_prices.items()):
        print(f"  {symbol}: {price}")

    print("\n50-Day Changes:")
    for symbol, change in sorted(changes.items(), key=lambda x: -x[1]):
        sign = "+" if change > 0 else ""
        print(f"  {symbol}: {sign}{change}%")

    print("\nAverage Volumes (Top 10):")
    for symbol, vol in sorted(volumes.items(), key=lambda x: -x[1])[:10]:
        print(f"  {symbol}: {vol:,}")

    # Save summary to JSON
    summary = {
        "current_prices": current_prices,
        "changes_50d": changes,
        "avg_volumes": volumes,
        "symbols": list(current_prices.keys()),
        "total_records": sum(len(records) for records in data.values()),
    }

    with open("/home/printer/Desktop/bot/sugi1/historical_50d_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 60)
    print("Summary saved to historical_50d_summary.json")
    print("=" * 60)
