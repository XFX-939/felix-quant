from __future__ import annotations

import pandas as pd


def enrich_prices(prices: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(prices)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    numeric_columns = ["open", "high", "low", "close", "volume", "amount", "pct_change"]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)
    df["ma5"] = df["close"].rolling(5).mean()
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()
    df["high20"] = df["high"].rolling(20).max()
    df["low20"] = df["low"].rolling(20).min()
    df["high60"] = df["high"].rolling(60).max()
    df["high120"] = df["high"].rolling(120).max()
    df["volume_ma5"] = df["volume"].rolling(5).mean()
    df["volume_ma20"] = df["volume"].rolling(20).mean()
    df["amount_ma5"] = df["amount"].rolling(5).mean()
    df["amount_ma20"] = df["amount"].rolling(20).mean()
    df["ret3"] = df["close"] / df["close"].shift(3) - 1
    df["ret5"] = df["close"] / df["close"].shift(5) - 1
    df["ret10"] = df["close"] / df["close"].shift(10) - 1
    df["ret20"] = df["close"] / df["close"].shift(20) - 1
    df["ret60"] = df["close"] / df["close"].shift(60) - 1
    df["ret120"] = df["close"] / df["close"].shift(120) - 1
    df["volatility_20"] = (df["pct_change"] / 100).rolling(20).std() * (252 ** 0.5)
    df["volatility_60"] = (df["pct_change"] / 100).rolling(60).std() * (252 ** 0.5)
    df["volatility_120"] = (df["pct_change"] / 100).rolling(120).std() * (252 ** 0.5)
    rolling_max = df["close"].rolling(60, min_periods=20).max()
    df["drawdown_60"] = df["close"] / rolling_max - 1
    df["max_drawdown_60"] = df["drawdown_60"].rolling(60, min_periods=20).min().abs()
    rolling_max_120 = df["close"].rolling(120, min_periods=30).max()
    df["drawdown_120"] = df["close"] / rolling_max_120 - 1
    df["max_drawdown_120"] = df["drawdown_120"].rolling(120, min_periods=30).min().abs()
    df["trend_slope"] = (df["ma20"] / df["ma60"] - 1).fillna(0)
    df["ma20_slope"] = (df["ma20"] / df["ma20"].shift(5) - 1).fillna(0)
    df["ma60_slope"] = (df["ma60"] / df["ma60"].shift(5) - 1).fillna(0)
    return df


def normalize(value: float, low: float, high: float, inverse: bool = False) -> float:
    if high == low:
        return 50
    score = (value - low) / (high - low) * 100
    score = max(0, min(100, score))
    return 100 - score if inverse else score


def safe_float(value: object, default: float = 0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def component_scores(row: pd.Series) -> dict[str, float]:
    momentum = normalize(safe_float(row.get("ret60")), -0.12, 0.28)
    volatility = normalize(safe_float(row.get("volatility_60")), 0.012, 0.06, inverse=True)
    volume = normalize(safe_float(row.get("volume")) / max(safe_float(row.get("volume_ma20"), 1), 1), 0.75, 1.65)
    drawdown = normalize(safe_float(row.get("max_drawdown_60")), 0.03, 0.24, inverse=True)
    trend = normalize(safe_float(row.get("trend_slope")), -0.04, 0.1)
    return {
        "momentum": round(momentum, 2),
        "volatility": round(volatility, 2),
        "volume": round(volume, 2),
        "drawdown": round(drawdown, 2),
        "trend": round(trend, 2),
    }


def equity_drawdown(equity_values: list[float]) -> list[float]:
    peak = 0.0
    drawdowns: list[float] = []
    for value in equity_values:
        peak = max(peak, value)
        drawdowns.append(0 if peak == 0 else value / peak - 1)
    return drawdowns
