#!/usr/bin/env python3
"""
Fetch real-time prices from Yahoo Finance using yfinance
"""

import yfinance as yf
import json
import sys


def get_current_prices():
    symbols = {
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

    prices = {}

    for display_symbol, yahoo_symbol in symbols.items():
        try:
            ticker = yf.Ticker(yahoo_symbol)
            info = (
                ticker.info.get("currentPrice")
                or ticker.info.get("regularMarketPreviousClose")
                or ticker.info.get("open")
            )
            if info:
                prices[display_symbol] = round(info, 4)
                print(f"{display_symbol}: {info:.4f}")
            else:
                print(f"{display_symbol}: No price data")
        except Exception as e:
            print(f"{display_symbol}: Error - {e}")

    return prices


if __name__ == "__main__":
    prices = get_current_prices()
    print("\n--- JSON Output ---")
    print(json.dumps(prices, indent=2))
