from __future__ import annotations

import importlib
import json
import math
from typing import Any

import pandas as pd


class AkshareUnavailableError(RuntimeError):
    pass


def normalize_stock_code(raw: object) -> str:
    code = str(raw or "").strip().upper()
    if "." in code:
        code = code.split(".", 1)[0]
    for prefix in ("SZ", "SH", "BJ"):
        if code.startswith(prefix):
            code = code[len(prefix):]
    digits = "".join(ch for ch in code if ch.isdigit())
    return digits.zfill(6)[-6:] if digits else ""


def infer_market(code: str) -> str:
    if code.startswith("6"):
        return "SH"
    if code.startswith(("8", "4")):
        return "BJ"
    return "SZ"


class AkshareDataProvider:
    def __init__(self, ak_module: Any | None = None, include_industry: bool = False):
        self.ak = ak_module if ak_module is not None else _load_akshare()
        self.include_industry = include_industry

    def fetch_stock_universe(self, limit: int | None = None) -> list[dict]:
        try:
            frame = self._market_spot_frame()
        except AkshareUnavailableError:
            return self._basic_stock_universe(limit=limit)
        if frame is None or frame.empty:
            return self._basic_stock_universe(limit=limit)
        industry_map = self._industry_map() if self.include_industry else {}
        rows: list[dict] = []
        for _, row in frame.iterrows():
            code = normalize_stock_code(_pick(row, "代码", "code", "股票代码"))
            if not code:
                continue
            name = str(_pick(row, "名称", "name", default="")).strip()
            if not name:
                continue
            rows.append(
                {
                    "code": code,
                    "name": name,
                    "industry": industry_map.get(code, "未分类"),
                    "market": infer_market(code),
                    "is_st": "ST" in name.upper(),
                    "is_suspended": _is_suspended(row),
                    "float_market_cap": _to_float(_pick(row, "流通市值", "float_market_cap"), 8000000000),
                }
            )
            if limit and len(rows) >= limit:
                break
        return rows

    def fetch_market_snapshot(self, limit: int | None = None) -> list[dict]:
        try:
            frame = self._market_spot_frame()
        except AkshareUnavailableError as exc:
            raise AkshareUnavailableError(f"AKShare 全市场实时行情获取失败：{exc}") from exc
        if frame is None or frame.empty:
            raise AkshareUnavailableError("AKShare 未返回全市场实时行情。")
        industry_map = self._industry_map() if self.include_industry else {}
        rows: list[dict] = []
        for _, row in frame.iterrows():
            code = normalize_stock_code(_pick(row, "代码", "code", "股票代码"))
            if not code:
                continue
            name = str(_pick(row, "名称", "name", default="")).strip()
            if not name or "退" in name:
                continue
            close = _to_float(_pick(row, "最新价", "close", "当前价"))
            pre_close = _to_float(_pick(row, "昨收", "pre_close", "昨收价"))
            pct_change = _to_float(_pick(row, "涨跌幅", "pct_change", "pctChg"))
            limit_rate = _limit_rate(code, name)
            limit_up_price = round(pre_close * (1 + limit_rate), 2) if pre_close > 0 else 0.0
            limit_down_price = round(pre_close * (1 - limit_rate), 2) if pre_close > 0 else 0.0
            rows.append(
                {
                    "stock_code": code,
                    "stock_name": name,
                    "market": infer_market(code),
                    "industry": industry_map.get(code, "未分类"),
                    "open": _to_float(_pick(row, "今开", "open", "开盘")),
                    "high": _to_float(_pick(row, "最高", "high")),
                    "low": _to_float(_pick(row, "最低", "low")),
                    "close": close,
                    "pre_close": pre_close,
                    "change_pct": pct_change,
                    "volume": _to_float(_pick(row, "成交量", "volume", "vol")),
                    "amount": _to_float(_pick(row, "成交额", "amount")),
                    "turnover_rate": _to_float(_pick(row, "换手率", "turnover_rate")),
                    "market_value": _to_float(_pick(row, "总市值", "market_value")),
                    "float_market_value": _to_float(_pick(row, "流通市值", "float_market_value", "流通市值")),
                    "limit_up_price": limit_up_price,
                    "limit_down_price": limit_down_price,
                    "is_limit_up": close > 0 and (close >= limit_up_price * 0.995 or pct_change >= limit_rate * 100 - 0.15),
                    "is_limit_down": close > 0 and (close <= limit_down_price * 1.005 or pct_change <= -limit_rate * 100 + 0.15),
                    "is_suspended": _is_suspended(row),
                    "is_st": "ST" in name.upper(),
                    "raw_json": json.dumps({str(key): _json_safe(value) for key, value in row.to_dict().items()}, ensure_ascii=False),
                }
            )
            if limit and len(rows) >= limit:
                break
        return rows

    def fetch_limit_up_pool(self, trade_date: str) -> list[dict]:
        function = getattr(self.ak, "stock_zt_pool_em", None)
        if not callable(function):
            raise AkshareUnavailableError("当前 AKShare 版本不支持 stock_zt_pool_em 涨停池接口。")
        try:
            frame = function(date=trade_date.replace("-", ""))
        except Exception as exc:  # noqa: BLE001 - external data source boundary
            raise AkshareUnavailableError(f"AKShare 涨停池获取失败：{exc}") from exc
        if frame is None or frame.empty:
            return []
        rows: list[dict] = []
        for _, row in frame.iterrows():
            code = normalize_stock_code(_pick(row, "代码", "股票代码", "code"))
            if not code:
                continue
            name = str(_pick(row, "名称", "股票简称", "name", default="")).strip()
            board_count = max(1, _to_int_like(_pick(row, "连板数", "连板高度", "board_count"), default=1))
            open_board_count = max(0, _to_int_like(_pick(row, "炸板次数", "开板次数", "open_board_count"), default=0))
            first_limit_time = _format_limit_time(_pick(row, "首次封板时间", "first_limit_time"))
            last_limit_time = _format_limit_time(_pick(row, "最后封板时间", "last_limit_time"))
            seal_amount = _to_float(_pick(row, "封板资金", "封单金额", "seal_amount"))
            float_market_value = _to_float(_pick(row, "流通市值", "float_market_value"))
            rows.append(
                {
                    "stock_code": code,
                    "stock_name": name or code,
                    "industry": str(_pick(row, "所属行业", "行业", "industry", default="")).strip() or "未分类",
                    "close": _to_float(_pick(row, "最新价", "收盘价", "close")),
                    "change_pct": _to_float(_pick(row, "涨跌幅", "pct_change", "pctChg")),
                    "amount": _to_float(_pick(row, "成交额", "amount")),
                    "turnover_rate": _to_float(_pick(row, "换手率", "turnover_rate")),
                    "market_value": _to_float(_pick(row, "总市值", "market_value")),
                    "float_market_value": float_market_value,
                    "is_limit_up": True,
                    "is_broken_board": False,
                    "first_limit_time": first_limit_time,
                    "last_limit_time": last_limit_time,
                    "open_board_count": open_board_count,
                    "seal_amount": seal_amount,
                    "seal_amount_ratio": seal_amount / float_market_value if float_market_value > 0 and seal_amount > 0 else 0,
                    "limit_up_type": str(_pick(row, "涨停类型", "板型", "limit_up_type", default="")).strip() or "未知",
                    "board_count": board_count,
                    "raw_json": json.dumps({str(key): _json_safe(value) for key, value in row.to_dict().items()}, ensure_ascii=False),
                }
            )
        return rows

    def _market_spot_frame(self) -> Any:
        errors: list[str] = []
        for function_name in ("stock_zh_a_spot_em", "stock_zh_a_spot"):
            function = getattr(self.ak, function_name, None)
            if not callable(function):
                errors.append(f"{function_name}: 当前 AKShare 版本不支持")
                continue
            try:
                frame = function()
            except Exception as exc:  # noqa: BLE001 - external data source boundary
                errors.append(f"{function_name}: {exc}")
                continue
            if frame is not None and not frame.empty:
                return frame
            errors.append(f"{function_name}: 空数据")
        raise AkshareUnavailableError("；".join(errors) or "无可用实时行情接口")

    def fetch_daily_prices(self, code: str, start_date: str, end_date: str, adjust: str = "qfq") -> list[dict]:
        symbol = normalize_stock_code(code)
        try:
            frame = self.ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
        except Exception:
            frame = self._sina_daily_frame(symbol, start_date, end_date, adjust)
        if frame is None or frame.empty:
            frame = self._sina_daily_frame(symbol, start_date, end_date, adjust)
        return _daily_prices_from_frame(frame, symbol)

    def _sina_daily_frame(self, symbol: str, start_date: str, end_date: str, adjust: str) -> Any:
        market_symbol = f"{infer_market(symbol).lower()}{symbol}"
        return self.ak.stock_zh_a_daily(
            symbol=market_symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust if adjust in {"qfq", "hfq"} else "",
        )

    def _industry_map(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        try:
            boards = self.ak.stock_board_industry_name_em()
        except Exception:
            return mapping
        if boards is None or boards.empty:
            return mapping
        for _, board in boards.iterrows():
            industry = str(_pick(board, "板块名称", "name", default="")).strip()
            if not industry:
                continue
            try:
                constituents = self.ak.stock_board_industry_cons_em(symbol=industry)
            except Exception:
                continue
            if constituents is None or constituents.empty:
                continue
            for _, item in constituents.iterrows():
                code = normalize_stock_code(_pick(item, "代码", "code", "股票代码"))
                if code and code not in mapping:
                    mapping[code] = industry
        return mapping

    def _basic_stock_universe(self, limit: int | None = None) -> list[dict]:
        frame = self.ak.stock_info_a_code_name()
        if frame is None or frame.empty:
            return []
        rows: list[dict] = []
        for _, row in frame.iterrows():
            code = normalize_stock_code(_pick(row, "代码", "code", "股票代码", "证券代码"))
            if not code:
                continue
            name = str(_pick(row, "名称", "name", "股票简称", "证券简称", default="")).strip()
            if not name:
                continue
            rows.append(
                {
                    "code": code,
                    "name": name,
                    "industry": "未分类",
                    "market": infer_market(code),
                    "is_st": "ST" in name.upper(),
                    "is_suspended": False,
                    "float_market_cap": 8000000000,
                }
            )
            if limit and len(rows) >= limit:
                break
        return rows


def _daily_prices_from_frame(frame: Any, symbol: str) -> list[dict]:
    if frame is None or frame.empty:
        return []
    prices: list[dict] = []
    previous_close = 0.0
    for _, row in frame.iterrows():
        date_value = _pick(row, "日期", "date")
        trade_date = _format_date(date_value)
        if not trade_date:
            continue
        open_price = _to_float(_pick(row, "开盘", "open"))
        close = _to_float(_pick(row, "收盘", "close"))
        high = _to_float(_pick(row, "最高", "high"))
        low = _to_float(_pick(row, "最低", "low"))
        volume_raw = _to_float(_pick(row, "成交量", "volume", "vol"))
        volume = volume_raw * 100 if _has_field(row, "成交量") else volume_raw
        amount = _to_float(_pick(row, "成交额", "amount"))
        if amount <= 0 and close > 0:
            amount = volume * close
        pct_change = _to_float(_pick(row, "涨跌幅", "pct_change", "pctChg"), default=float("nan"))
        if math.isnan(pct_change):
            pct_change = ((close - previous_close) / previous_close * 100) if previous_close else 0
        prices.append(
            {
                "stock_code": symbol,
                "date": trade_date,
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": round(volume, 0),
                "amount": round(amount, 2),
                "pct_change": round(pct_change, 2),
            }
        )
        previous_close = close
    return sorted(prices, key=lambda item: item["date"])


def _load_akshare() -> Any:
    try:
        return importlib.import_module("akshare")
    except ImportError as exc:
        raise AkshareUnavailableError("未安装 AKShare，请先在 backend 环境执行 pip install -r requirements.txt") from exc


def _pick(row: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        try:
            value = row[name]
        except Exception:
            continue
        if value is not None and not _is_nan(value):
            return value
    return default


def _has_field(row: Any, name: str) -> bool:
    try:
        return name in row.index
    except Exception:
        try:
            row[name]
            return True
        except Exception:
            return False


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(number) else number


def _to_int_like(value: Any, default: int = 0) -> int:
    if value is None or _is_nan(value):
        return default
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return default if math.isnan(float(value)) else int(float(value))
    text = str(value).strip()
    if not text:
        return default
    digits = []
    for char in text:
        if char.isdigit():
            digits.append(char)
        elif digits:
            break
    return int("".join(digits)) if digits else default


def _is_nan(value: Any) -> bool:
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def _format_date(value: Any) -> str:
    if value is None or _is_nan(value):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text:
        return ""
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10]


def _format_limit_time(value: Any) -> str:
    if value is None or _is_nan(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 5:
        digits = digits.zfill(6)
    if len(digits) >= 6:
        digits = digits[-6:]
        return f"{digits[:2]}:{digits[2:4]}:{digits[4:6]}"
    if len(digits) == 4:
        return f"{digits[:2]}:{digits[2:4]}:00"
    return text


def _is_suspended(row: Any) -> bool:
    status = str(_pick(row, "交易状态", "tradestatus", "状态", default="")).strip()
    if status in {"停牌", "0"}:
        return True
    price = _to_float(_pick(row, "最新价", "close", "当前价"))
    amount = _to_float(_pick(row, "成交额", "amount"))
    return price <= 0 or amount <= 0


def _limit_rate(code: str, name: str = "") -> float:
    upper_name = name.upper()
    if "ST" in upper_name:
        return 0.05
    if code.startswith(("300", "301", "688", "689")):
        return 0.20
    if code.startswith(("8", "4")):
        return 0.30
    return 0.10


def _json_safe(value: Any) -> Any:
    if _is_nan(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
