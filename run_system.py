#!/usr/bin/env python3
"""
Financial Forecasting System - Unified Entry Point
===================================================
This script orchestrates the entire financial forecasting system:
- Manages Docker services (Redis, etc.)
- Downloads historical data
- Trains ML models (Rust)
- Generates analysis reports
- Updates Report.md

Usage:
    python3 run_system.py --window 240
    python3 run_system.py --window 100 --build
    python3 run_system.py --window 50 --clean
"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# Configuration
PROJECT_DIR = Path("/home/printer/Desktop/bot/sugi1")
RUST_DIR = PROJECT_DIR / "rust-model"
JAVA_DIR = PROJECT_DIR / "java-backend"
REPORT_PATH = PROJECT_DIR / "Report.md"
DOCKER_COMPOSE_PATH = PROJECT_DIR / "docker-compose.yml"

# Default symbols
STOCK_SYMBOLS = [
    "NVDA",
    "AMD",
    "WDC",
    "SLV",
    "GS",
    "NET",
    "STLD",
    "TTWO",
    "UBS",
    "CRCL",
]
FOREX_SYMBOLS = ["EURUSD=X", "INRJPY=X"]
INDEX_SYMBOLS = ["MNQ", "EWJ"]
CRYPTO_SYMBOLS = ["ETH-USD"]
ALL_SYMBOLS = STOCK_SYMBOLS + FOREX_SYMBOLS + INDEX_SYMBOLS + CRYPTO_SYMBOLS

WINDOWS = {
    14: {"python": "download_14d.py", "trading_days": 14, "name": "14-Day"},
    50: {"python": "download_50d.py", "trading_days": 50, "name": "50-Day"},
    100: {"python": "download_100d.py", "trading_days": 100, "name": "100-Day"},
    240: {"python": "download_240d.py", "trading_days": 240, "name": "240-Day"},
}


@dataclass
class Config:
    window: int = 240
    build_rust: bool = False
    clean: bool = False
    skip_docker: bool = False
    verbose: bool = False


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def log(msg: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    color = {
        "INFO": Colors.CYAN,
        "SUCCESS": Colors.GREEN,
        "WARN": Colors.WARNING,
        "ERROR": Colors.FAIL,
    }.get(level, Colors.BLUE)
    print(f"{color}[{timestamp}] {level}: {msg}{Colors.ENDC}")


def run_command(
    cmd: list[str], cwd: Optional[Path] = None, capture: bool = True
) -> tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, stderr."""
    log(f"Running: {' '.join(cmd)}") if len(cmd) < 20 else log(f"Running: {cmd[0]}...")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            timeout=300,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def check_docker() -> bool:
    """Check if Docker is available."""
    code, _, _ = run_command(["docker", "--version"])
    return code == 0


def check_redis() -> bool:
    """Check if Redis is running."""
    code, _, _ = run_command(["redis-cli", "ping"])
    return code == 0


def start_docker_services() -> bool:
    """Start Docker services using docker-compose."""
    if check_redis():
        log("Redis is already running", "WARN")
        return True

    if not DOCKER_COMPOSE_PATH.exists():
        log("No docker-compose.yml found, skipping Docker", "WARN")
        return True

    log("Starting Docker services...")
    code, stdout, stderr = run_command(["docker-compose", "up", "-d"], cwd=PROJECT_DIR)

    if code != 0:
        log(f"Docker compose failed: {stderr}", "ERROR")
        return False

    # Wait for Redis
    for i in range(10):
        if check_redis():
            log("Redis is ready", "SUCCESS")
            return True
        time.sleep(1)

    log("Redis failed to start", "ERROR")
    return False


def stop_docker_services():
    """Stop Docker services."""
    if DOCKER_COMPOSE_PATH.exists():
        run_command(["docker-compose", "down"], cwd=PROJECT_DIR)
        log("Docker services stopped")


def clean_redis():
    """Clean Redis data."""
    if check_redis():
        run_command(["redis-cli", "FLUSHALL"])
        log("Redis cleaned", "SUCCESS")


def download_data(window: int, verbose: bool = False) -> bool:
    """Download historical data for the specified window."""
    if window not in WINDOWS:
        log(f"Invalid window: {window}. Valid: {list(WINDOWS.keys())}", "ERROR")
        return False

    config = WINDOWS[window]
    script_name = config["python"]

    # Check if custom 100d script exists, otherwise use 50d
    if window == 100 and not (PROJECT_DIR / script_name).exists():
        script_name = "download_50d.py"  # Fallback

    script_path = PROJECT_DIR / script_name

    if not script_path.exists():
        log(f"Script not found: {script_path}", "ERROR")
        return False

    log(f"Downloading {config['name']} data ({config['trading_days']} trading days)...")

    env = os.environ.copy()
    env["TRADING_DAYS"] = str(config["trading_days"])

    code, stdout, stderr = run_command(
        [sys.executable, str(script_path)],
        cwd=PROJECT_DIR,
    )

    if verbose:
        print(stdout)

    if code != 0:
        log(f"Download failed: {stderr}", "ERROR")
        return False

    log("Data download complete", "SUCCESS")
    return True


def build_rust_model() -> bool:
    """Build the Rust ML model."""
    log("Building Rust model...")

    code, stdout, stderr = run_command(
        ["/home/printer/.cargo/bin/cargo", "build", "--release"],
        cwd=RUST_DIR,
    )

    if code != 0:
        log(f"Rust build failed: {stderr}", "ERROR")
        return False

    binary = RUST_DIR / "target/release/rust-model"
    if not binary.exists():
        log("Rust binary not found", "ERROR")
        return False

    log("Rust model built successfully", "SUCCESS")
    return True


def run_rust_model(window: int, verbose: bool = False) -> dict:
    """Run the Rust ML model and return results."""
    binary = RUST_DIR / "target/release/rust-model"

    if not binary.exists():
        log("Rust binary not found, building...", "WARN")
        if not build_rust_model():
            return {}

    log("Running Rust ML model...")

    # Run with timeout
    try:
        result = subprocess.run(
            [str(binary)],
            cwd=RUST_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        log("Rust model timed out", "ERROR")
        return {}

    if verbose:
        print(output[-2000:])  # Last 2000 chars

    # Parse results from output
    results = parse_rust_output(output)

    if results:
        log("Rust model analysis complete", "SUCCESS")
    else:
        log("Failed to parse Rust model output", "ERROR")

    return results


def parse_rust_output(output: str) -> dict:
    """Parse Rust model output for key metrics."""
    results = {}

    import re

    # Parse Strongest Movers section
    movers_section = re.search(
        r"=== Strongest Movers.*?===\n(.*?)(?:\n===|$)", output, re.DOTALL
    )
    if movers_section:
        lines = movers_section.group(1).strip().split("\n")
        for line in lines:
            # Format: "Symbol: UBS      | Alpha:   2.3787 | Probability:  22.59% | Change:   23.30%"
            match = re.search(r"Symbol:\s*(\w+).*?Change:\s*([+-]?[\d.]+)", line)
            if match:
                symbol = match.group(1)
                change = float(match.group(2))
                results[symbol] = change

    # Extract strongest movers list
    movers_match = re.search(r"Strongest Movers:([\d\s\w.,]+)", output)
    if movers_match:
        results["strongest_movers"] = movers_match.group(1).strip()

    # Extract correlation range
    corr_match = re.search(
        r"Highest Correlation:\s*([-\d.]+).*?Lowest Correlation:\s*([-\d.]+)",
        output,
        re.DOTALL,
    )
    if corr_match:
        results["corr_max"] = float(corr_match.group(1))
        results["corr_min"] = float(corr_match.group(2))

    # Extract training samples
    samples_match = re.search(r"Training Random Forest with (\d+) samples", output)
    if samples_match:
        results["training_samples"] = int(samples_match.group(1))

    # Extract alpha data
    alpha_data = []
    movers_section = re.search(
        r"=== Highest Volume ===\n(.*?)(?:\n===|$)", output, re.DOTALL
    )
    if movers_section:
        lines = movers_section.group(1).strip().split("\n")
        for line in lines:
            match = re.search(r"Symbol:\s*(\w+).*?Alpha:\s*([+-]?[\d.]+)", line)
            if match:
                symbol = match.group(1)
                alpha = float(match.group(2))
                alpha_data.append((symbol, alpha))
        results["alpha"] = alpha_data

    return results


def generate_report(window: int, rust_results: dict, verbose: bool = False) -> str:
    """Generate the analysis report markdown."""
    log("Generating analysis report...")

    # Get data from Redis
    summary = get_redis_summary()

    # Build report
    report = f"""# Financial Forecasting Analysis Report

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Analysis Window:** {WINDOWS.get(window, {}).get("name", f"{window}-Day")}  
**Data Source:** Yahoo Finance via Redis

---

## Executive Summary

This report provides comprehensive analysis of equity, forex, index, and cryptocurrency
data using machine learning models to identify alpha opportunities and correlations.

### Key Findings

"""

    if "strongest_movers" in rust_results:
        report += f"**Strongest Movers:** {rust_results['strongest_movers']}\n\n"

    report += f"**Correlation Range:** {rust_results.get('corr_min', 0):.3f} to {rust_results.get('corr_max', 0):.3f}\n\n"
    report += f"**Training Samples:** {rust_results.get('training_samples', 0):,}\n\n"

    # Performance Summary
    report += """## Performance Summary

| Symbol | Change | Status |
|--------|--------|--------|
"""

    # Sort by performance
    sorted_perf = sorted(
        rust_results.items(),
        key=lambda x: x[1] if isinstance(x[1], float) else -999,
        reverse=True,
    )

    for symbol, change in sorted_perf:
        if isinstance(change, float) and symbol in ALL_SYMBOLS:
            status = (
                "🟢 Strong"
                if change > 50
                else "🟡 Moderate"
                if change > 20
                else "🔴 Weak"
            )
            report += f"| {symbol} | {change:+.2f}% | {status} |\n"

    # Top performers
    report += """
### Top Performers

"""

    top_performers = [
        (k, v) for k, v in sorted_perf if isinstance(v, float) and k in ALL_SYMBOLS
    ][:5]
    for symbol, change in top_performers:
        report += f"1. **{symbol}**: {change:+.2f}%\n"

    # Data Summary
    report += f"""
---

## Data Summary

### Symbols Analyzed

| Category | Symbols |
|----------|---------|
| Stocks | {", ".join(STOCK_SYMBOLS)} |
| Forex | {", ".join(FOREX_SYMBOLS)} |
| Indices | {", ".join(INDEX_SYMBOLS)} |
| Crypto | {", ".join(CRYPTO_SYMBOLS)} |

### Redis Data Summary

| Metric | Value |
|--------|-------|
| Total Records | {summary.get("total_keys", "N/A"):,} |
| Symbols with Data | {summary.get("symbol_count", "N/A")} |
| Date Range | {summary.get("date_range", "N/A")} |

"""

    # Volume Summary
    if "volumes" in summary:
        report += "### Average Volumes (Top 10)\n\n"
        report += "| Symbol | Avg Volume |\n|--------|------------|\n"
        for symbol, volume in summary["volumes"][:10]:
            report += f"| {symbol} | {volume:,.0f} |\n"
        report += "\n"

    # Correlations
    report += """## Correlation Analysis

The following asset pairs show strong positive correlations (>0.5):

"""

    if "correlations" in summary and summary["correlations"]:
        for pair, corr in summary["correlations"][:10]:
            report += f"- **{pair[0]} ↔ {pair[1]}**: {corr:.2f}\n"
        report += "\n"
    else:
        report += "No strong correlations detected.\n\n"

    # ML Insights
    report += f"""## Machine Learning Insights

### Model Configuration

- **Algorithm:** Random Forest
- **Lookback Window:** 5 days
- **Minimum Records:** 25
- **Training Samples:** {rust_results.get("training_samples", 0):,}

### Feature Engineering

The model uses the following features:
- Price returns (1d, 5d, 20d)
- Volume changes
- Relative Strength Index (RSI)
- Moving Averages (SMA 20, SMA 50)
- MACD signals

---

## Methodology

1. **Data Collection:** Historical OHLCV data fetched from Yahoo Finance
2. **Storage:** Data stored in Redis with TTL matching analysis window
3. **Feature Engineering:** Technical indicators calculated per symbol
4. **Model Training:** Random Forest trained on {rust_results.get("training_samples", 0):,} samples
5. **Prediction:** Generate forecasts and identify alpha opportunities

---

## Recommendations

Based on the {WINDOWS.get(window, {}).get("name", f"{window}-Day")} analysis:

"""

    # Generate recommendations based on performance
    positive_perf = [(k, v) for k, v in sorted_perf if isinstance(v, float) and v > 0][
        :3
    ]
    if positive_perf:
        report += "### Opportunities\n\n"
        for symbol, change in positive_perf:
            report += f"- **{symbol}** shows strong momentum with {change:+.2f}% gain\n"
        report += "\n"

    # Risk warnings
    negative_perf = [(k, v) for k, v in sorted_perf if isinstance(v, float) and v < -10]
    if negative_perf:
        report += "### Risk Factors\n\n"
        for symbol, change in negative_perf:
            report += f"- **{symbol}** showing weakness with {change:+.2f}% decline\n"
        report += "\n"

    # Technical notes
    report += f"""---

## Technical Notes

- Analysis window: {WINDOWS.get(window, {}).get("name", f"{window}-Day")} ({WINDOWS.get(window, {}).get("trading_days", window)} trading days)
- Redis TTL: {WINDOWS.get(window, {}).get("trading_days", window) * 24 * 60 * 60:,} seconds
- Rust model binary: `{"✅ Built" if (RUST_DIR / "target/release/rust-model").exists() else "❌ Not Built"}`
- Java API: `{"✅ Running" if check_redis() else "❌ Not Running"}`

---

*Report generated by Financial Forecasting System*
"""

    return report


def get_redis_summary() -> dict:
    """Get summary statistics from Redis."""
    summary = {}

    # Get key count
    code, stdout, _ = run_command(["redis-cli", "KEYS", "equity:*"])
    if code == 0:
        keys = [k for k in stdout.strip().split("\n") if k]
        summary["total_keys"] = len(keys)

    # Get symbol count
    code, stdout, _ = run_command(["redis-cli", "KEYS", "symbol:*"])
    if code == 0:
        symbols = [
            k
            for k in stdout.strip().split("\n")
            if k and ":" not in k.replace("symbol:", "")
        ]
        summary["symbol_count"] = len(symbols)

    # Get volumes for each symbol
    volumes = []
    for symbol in ALL_SYMBOLS:
        code, stdout, _ = run_command(["redis-cli", "KEYS", f"equity:{symbol}:*"])
        if code == 0:
            keys = [k for k in stdout.strip().split("\n") if k]
            if keys:
                # Sample some keys to get volume
                total_vol = 0
                count = 0
                for key in keys[:10]:  # Sample up to 10
                    code2, vol_str, _ = run_command(["redis-cli", "GET", key])
                    if code2 == 0:
                        try:
                            data = json.loads(vol_str)
                            vol = data.get("volume", 0)
                            total_vol += float(vol) if vol else 0
                            count += 1
                        except:
                            pass
                if count > 0:
                    volumes.append((symbol, total_vol / count))

    volumes.sort(key=lambda x: x[1], reverse=True)
    summary["volumes"] = volumes

    # Get date range
    code, stdout, _ = run_command(["redis-cli", "KEYS", "equity:NVIDIA:*"])
    if code != 0:
        code, stdout, _ = run_command(["redis-cli", "KEYS", "equity:NVDA:*"])

    if code == 0:
        keys = [k for k in stdout.strip().split("\n") if k]
        if keys:
            timestamps = []
            for key in keys[:50]:
                ts_str = key.split(":")[-1]
                try:
                    timestamps.append(int(ts_str))
                except:
                    pass
            if timestamps:
                min_ts = min(timestamps)
                max_ts = max(timestamps)
                min_date = datetime.fromtimestamp(min_ts / 1000).strftime("%Y-%m-%d")
                max_date = datetime.fromtimestamp(max_ts / 1000).strftime("%Y-%m-%d")
                summary["date_range"] = f"{min_date} to {max_date}"

    # Calculate correlations (simplified)
    correlations = []
    for i, sym1 in enumerate(ALL_SYMBOLS[:8]):
        for sym2 in ALL_SYMBOLS[i + 1 : 8]:
            corr = calculate_correlation(sym1, sym2)
            if corr and abs(corr) > 0.3:
                correlations.append(((sym1, sym2), corr))

    correlations.sort(key=lambda x: abs(x[1]), reverse=True)
    summary["correlations"] = correlations

    return summary


def calculate_correlation(sym1: str, sym2: str) -> Optional[float]:
    """Calculate correlation between two symbols."""
    # Get price data
    data1 = get_price_data(sym1)
    data2 = get_price_data(sym2)

    if not data1 or not data2:
        return None

    # Align by timestamp
    aligned1 = {d["timestamp"]: d["close"] for d in data1}
    aligned2 = {d["timestamp"]: d["close"] for d in data2}

    common_ts = sorted(set(aligned1.keys()) & set(aligned2.keys()))[
        -50:
    ]  # Last 50 points

    if len(common_ts) < 10:
        return None

    # Calculate returns
    returns1 = []
    returns2 = []
    for i in range(1, len(common_ts)):
        ts = common_ts[i]
        prev_ts = common_ts[i - 1]
        if (
            ts in aligned1
            and prev_ts in aligned1
            and ts in aligned2
            and prev_ts in aligned2
        ):
            r1 = (
                (aligned1[ts] - aligned1[prev_ts]) / aligned1[prev_ts]
                if aligned1[prev_ts]
                else 0
            )
            r2 = (
                (aligned2[ts] - aligned2[prev_ts]) / aligned2[prev_ts]
                if aligned2[prev_ts]
                else 0
            )
            returns1.append(r1)
            returns2.append(r2)

    if len(returns1) < 10:
        return None

    # Simple correlation
    mean1 = sum(returns1) / len(returns1)
    mean2 = sum(returns2) / len(returns2)

    numerator = sum((r1 - mean1) * (r2 - mean2) for r1, r2 in zip(returns1, returns2))
    denom1 = sum((r - mean1) ** 2 for r in returns1) ** 0.5
    denom2 = sum((r - mean2) ** 2 for r in returns2) ** 0.5

    if denom1 == 0 or denom2 == 0:
        return None

    return numerator / (denom1 * denom2)


def get_price_data(symbol: str) -> list:
    """Get price data from Redis for a symbol."""
    code, stdout, _ = run_command(["redis-cli", "KEYS", f"equity:{symbol}:*"])

    if code != 0:
        return []

    keys = [k for k in stdout.strip().split("\n") if k]
    data = []

    for key in keys[:240]:
        code2, val, _ = run_command(["redis-cli", "GET", key])
        if code2 == 0:
            try:
                data.append(json.loads(val))
            except:
                pass

    # Sort by timestamp
    data.sort(key=lambda x: x.get("timestamp", 0))
    return data


def save_report(report: str, path: Path):
    """Save report to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report)
    log(f"Report saved to {path}", "SUCCESS")


def start_java_api() -> bool:
    """Start the Java API server."""
    # Check if already running
    code, _, _ = run_command(["curl", "-s", "http://localhost:8080/api/health"])
    if code == 0:
        log("Java API already running", "WARN")
        return True

    log("Starting Java API...")

    # Start in background
    nohup_cmd = f"cd {JAVA_DIR} && nohup mvn exec:java -Dexec.mainClass='com.financial.backend.Main' > /tmp/java-api.log 2>&1 &"
    run_command(["bash", "-c", nohup_cmd])

    # Wait for startup
    for i in range(30):
        time.sleep(1)
        code, _, _ = run_command(["curl", "-s", "http://localhost:8080/api/health"])
        if code == 0:
            log("Java API started", "SUCCESS")
            return True

    log("Java API failed to start", "ERROR")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Financial Forecasting System - Unified Entry Point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 run_system.py --window 240              # Run full analysis with 240-day window
    python3 run_system.py --window 100 --build      # Build Rust model and run 100-day analysis
    python3 run_system.py --window 50 --clean       # Clean Redis and run 50-day analysis
    python3 run_system.py --window 14 --skip-docker # Skip Docker, run quick 14-day analysis
        """,
    )

    parser.add_argument(
        "--window",
        "-w",
        type=int,
        default=240,
        choices=[14, 50, 100, 240],
        help="Analysis window in trading days (default: 240)",
    )

    parser.add_argument(
        "--build",
        "-b",
        action="store_true",
        help="Force rebuild Rust model",
    )

    parser.add_argument(
        "--clean",
        "-c",
        action="store_true",
        help="Clean Redis data before running",
    )

    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip Docker service management",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    print(f"""
{Colors.BOLD}╔═══════════════════════════════════════════════════════════════╗
║     Financial Forecasting System - Unified Entry Point      ║
╚═══════════════════════════════════════════════════════════════╝{Colors.ENDC}
    """)

    config = Config(
        window=args.window,
        build_rust=args.build,
        clean=args.clean,
        skip_docker=args.skip_docker,
        verbose=args.verbose,
    )

    # Step 1: Manage Docker services
    if not config.skip_docker:
        if config.clean:
            clean_redis()

        if not start_docker_services():
            log("Failed to start Docker services", "ERROR")
            sys.exit(1)
    else:
        if config.clean:
            clean_redis()

    # Step 2: Check Redis
    if not check_redis():
        log("Redis is not running. Please start Docker or Redis manually.", "ERROR")
        sys.exit(1)

    log(
        f"Redis is running (Window: {WINDOWS.get(config.window, {}).get('name', f'{config.window}-Day')})"
    )

    # Step 3: Download data
    if not download_data(config.window, config.verbose):
        log("Failed to download data", "ERROR")
        sys.exit(1)

    # Step 4: Build Rust model if needed
    binary = RUST_DIR / "target/release/rust-model"
    if config.build_rust or not binary.exists():
        if not build_rust_model():
            log("Rust model build failed", "ERROR")
            sys.exit(1)

    # Step 5: Run Rust model
    rust_results = run_rust_model(config.window, config.verbose)

    # Step 6: Generate report
    report = generate_report(config.window, rust_results, config.verbose)
    save_report(report, REPORT_PATH)

    # Step 7: Start Java API (optional, for real-time queries)
    log("Java API is available at http://localhost:8080/api/equity/symbol?symbol=NVDA")

    print(f"""
{Colors.BOLD}╔═══════════════════════════════════════════════════════════════╗
║                    Analysis Complete!                        ║
╚═══════════════════════════════════════════════════════════════╝{Colors.ENDC}

📊 Window: {WINDOWS.get(config.window, {}).get("name", f"{config.window}-Day")}
📄 Report: {REPORT_PATH}
🔧 Rust Binary: {"✅ Built" if binary.exists() else "❌ Not Built"}

Run: cat {REPORT_PATH} to view the full report.
    """)


if __name__ == "__main__":
    main()
