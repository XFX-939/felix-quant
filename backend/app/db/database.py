import json
import math
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import numpy as np

from app.core.config import DB_PATH, MARKET_DATA_SOURCE

SAMPLE_LATEST_PRICE_ANCHORS = {
    "000001": 12.48,
    "600519": 1468.0,
    "300750": 218.0,
    "600036": 42.6,
    "000858": 128.0,
    "600276": 45.2,
    "002415": 34.8,
    "601318": 48.5,
    "600030": 22.4,
    "002594": 286.0,
    "600887": 27.8,
    "300059": 18.9,
}


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def dict_from_row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def dicts_from_rows(rows: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict_from_row(row) for row in rows if row is not None]


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def initialize_database() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    _try_enable_wal_mode()
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                industry TEXT NOT NULL,
                market TEXT NOT NULL,
                list_date TEXT,
                is_st INTEGER NOT NULL DEFAULT 0,
                is_suspended INTEGER NOT NULL DEFAULT 0,
                float_market_cap REAL NOT NULL DEFAULT 8000000000,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                amount REAL NOT NULL,
                pct_change REAL NOT NULL,
                UNIQUE(stock_code, date),
                FOREIGN KEY(stock_code) REFERENCES stocks(code) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS market_snapshots_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                market TEXT NOT NULL DEFAULT '',
                industry TEXT NOT NULL DEFAULT '未分类',
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                pre_close REAL,
                change_pct REAL,
                volume REAL,
                amount REAL,
                turnover_rate REAL,
                market_value REAL,
                float_market_value REAL,
                limit_up_price REAL,
                limit_down_price REAL,
                is_limit_up INTEGER NOT NULL DEFAULT 0,
                is_limit_down INTEGER NOT NULL DEFAULT 0,
                is_suspended INTEGER NOT NULL DEFAULT 0,
                is_st INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(trade_date, stock_code)
            );

            CREATE INDEX IF NOT EXISTS idx_market_snapshots_date
                ON market_snapshots_daily(trade_date);

            CREATE INDEX IF NOT EXISTS idx_market_snapshots_limit
                ON market_snapshots_daily(trade_date, is_limit_up, stock_code);

            CREATE TABLE IF NOT EXISTS market_data_sync_status (
                trade_date TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                progress REAL NOT NULL DEFAULT 0,
                total_count INTEGER NOT NULL DEFAULT 0,
                success_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                task_id INTEGER,
                started_at TEXT,
                finished_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS stock_industry_map (
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                sw_l1_code TEXT NOT NULL DEFAULT '',
                sw_l1_name TEXT NOT NULL DEFAULT '综合',
                sw_l2_code TEXT NOT NULL DEFAULT '',
                sw_l2_name TEXT NOT NULL DEFAULT '综合',
                sw_l3_code TEXT NOT NULL DEFAULT '',
                sw_l3_name TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'fallback',
                effective_date TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY(stock_code, effective_date)
            );

            CREATE INDEX IF NOT EXISTS idx_stock_industry_map_code
                ON stock_industry_map(stock_code, effective_date);

            CREATE TABLE IF NOT EXISTS market_sentiment_daily (
                trade_date TEXT PRIMARY KEY,
                limit_up_count INTEGER NOT NULL DEFAULT 0,
                limit_down_count INTEGER NOT NULL DEFAULT 0,
                broken_board_count INTEGER NOT NULL DEFAULT 0,
                seal_rate REAL NOT NULL DEFAULT 0,
                max_board_height INTEGER NOT NULL DEFAULT 0,
                three_board_plus_count INTEGER NOT NULL DEFAULT 0,
                yesterday_limit_up_premium REAL NOT NULL DEFAULT 0,
                index_trend_score REAL NOT NULL DEFAULT 50,
                market_sentiment_score REAL NOT NULL DEFAULT 0,
                market_state TEXT NOT NULL DEFAULT '退潮',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS industry_heat_daily (
                trade_date TEXT NOT NULL,
                industry_level TEXT NOT NULL,
                industry_code TEXT NOT NULL DEFAULT '',
                industry_name TEXT NOT NULL,
                limit_up_count INTEGER NOT NULL DEFAULT 0,
                chain_stock_count INTEGER NOT NULL DEFAULT 0,
                max_board_height INTEGER NOT NULL DEFAULT 0,
                avg_change_pct REAL NOT NULL DEFAULT 0,
                total_amount REAL NOT NULL DEFAULT 0,
                amount_ratio REAL NOT NULL DEFAULT 1,
                seal_rate REAL NOT NULL DEFAULT 0,
                broken_board_count INTEGER NOT NULL DEFAULT 0,
                industry_heat_score REAL NOT NULL DEFAULT 0,
                industry_heat_rank INTEGER NOT NULL DEFAULT 999,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(trade_date, industry_level, industry_name)
            );

            CREATE TABLE IF NOT EXISTS limit_up_strategy_signals (
                trade_date TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                board_count INTEGER NOT NULL DEFAULT 1,
                sw_l1_name TEXT NOT NULL DEFAULT '综合',
                sw_l2_name TEXT NOT NULL DEFAULT '综合',
                market_sentiment_score REAL NOT NULL DEFAULT 0,
                industry_heat_score REAL NOT NULL DEFAULT 0,
                board_height_score REAL NOT NULL DEFAULT 0,
                seal_quality_score REAL NOT NULL DEFAULT 0,
                liquidity_score REAL NOT NULL DEFAULT 0,
                risk_penalty_score REAL NOT NULL DEFAULT 0,
                total_score REAL NOT NULL DEFAULT 0,
                action_level TEXT NOT NULL DEFAULT 'D',
                action_label TEXT NOT NULL DEFAULT '禁止参与',
                trigger_condition TEXT NOT NULL DEFAULT '',
                position_advice TEXT NOT NULL DEFAULT '',
                stop_loss_rule TEXT NOT NULL DEFAULT '',
                take_profit_rule TEXT NOT NULL DEFAULT '',
                risk_reasons TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(trade_date, stock_code)
            );

            CREATE TABLE IF NOT EXISTS strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                type TEXT NOT NULL,
                parameters TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                strategy_id INTEGER NOT NULL,
                signal_type TEXT NOT NULL,
                score REAL NOT NULL,
                reason TEXT NOT NULL,
                risk_reason TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(stock_code) REFERENCES stocks(code) ON DELETE CASCADE,
                FOREIGN KEY(strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_signals_date ON signals(date);
            CREATE INDEX IF NOT EXISTS idx_signals_stock ON signals(stock_code);

            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                total_return REAL NOT NULL,
                annual_return REAL NOT NULL,
                max_drawdown REAL NOT NULL,
                sharpe REAL NOT NULL,
                win_rate REAL NOT NULL,
                trade_count INTEGER NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                signal_id INTEGER,
                action_taken INTEGER NOT NULL DEFAULT 0,
                reason TEXT NOT NULL,
                result TEXT NOT NULL,
                summary TEXT NOT NULL,
                tags TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(stock_code) REFERENCES stocks(code) ON DELETE CASCADE,
                FOREIGN KEY(signal_id) REFERENCES signals(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS risk_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                threshold REAL NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS task_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                trade_date TEXT,
                status TEXT NOT NULL,
                current_stage TEXT NOT NULL DEFAULT '',
                total_count INTEGER NOT NULL DEFAULT 0,
                processed_count INTEGER NOT NULL DEFAULT 0,
                success_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                retry_count INTEGER NOT NULL DEFAULT 0,
                progress_percent REAL NOT NULL DEFAULT 0,
                started_at TEXT,
                finished_at TEXT,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                summary_json TEXT NOT NULL DEFAULT '{}',
                created_by TEXT NOT NULL DEFAULT 'system',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_task_runs_type_date_status
                ON task_runs(task_type, trade_date, status);

            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name TEXT NOT NULL UNIQUE,
                job_type TEXT NOT NULL,
                cron_expression TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS job_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name TEXT NOT NULL,
                job_type TEXT NOT NULL,
                trigger_type TEXT NOT NULL DEFAULT 'auto',
                status TEXT NOT NULL,
                scheduled_at TEXT,
                started_at TEXT,
                finished_at TEXT,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                progress REAL NOT NULL DEFAULT 0,
                current_stage TEXT NOT NULL DEFAULT '',
                success_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                retry_count INTEGER NOT NULL DEFAULT 0,
                data_date TEXT,
                snapshot_type TEXT NOT NULL DEFAULT '',
                error_message TEXT,
                result_summary TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_job_runs_name_date_status
                ON job_runs(job_name, data_date, status);

            CREATE INDEX IF NOT EXISTS idx_job_runs_created
                ON job_runs(created_at DESC);

            CREATE TABLE IF NOT EXISTS data_sync_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_type TEXT NOT NULL,
                data_date TEXT,
                last_success_at TEXT,
                last_attempt_at TEXT,
                status TEXT NOT NULL DEFAULT 'missing',
                total_count INTEGER NOT NULL DEFAULT 0,
                success_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT '',
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(data_type, data_date)
            );

            CREATE INDEX IF NOT EXISTS idx_data_sync_status_type_date
                ON data_sync_status(data_type, data_date);

            CREATE TABLE IF NOT EXISTS dashboard_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_date TEXT NOT NULL,
                snapshot_type TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                market_status TEXT NOT NULL DEFAULT '',
                market_summary_json TEXT NOT NULL DEFAULT '{}',
                candidate_summary_json TEXT NOT NULL DEFAULT '{}',
                risk_summary_json TEXT NOT NULL DEFAULT '{}',
                strategy_summary_json TEXT NOT NULL DEFAULT '{}',
                performance_summary_json TEXT NOT NULL DEFAULT '{}',
                data_quality_json TEXT NOT NULL DEFAULT '{}',
                summary_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(data_date, snapshot_type)
            );

            CREATE INDEX IF NOT EXISTS idx_dashboard_snapshots_latest
                ON dashboard_snapshots(data_date DESC, generated_at DESC);

            CREATE TABLE IF NOT EXISTS failed_sync_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                task_type TEXT NOT NULL,
                data_type TEXT NOT NULL,
                status TEXT NOT NULL,
                retry_count INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 3,
                error_message TEXT NOT NULL DEFAULT '',
                last_error_at TEXT,
                next_retry_at TEXT,
                raw_context_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(trade_date, code, task_type, data_type)
            );

            CREATE INDEX IF NOT EXISTS idx_failed_sync_status
                ON failed_sync_records(status, task_type, data_type);

            CREATE TABLE IF NOT EXISTS stock_sync_state (
                code TEXT PRIMARY KEY,
                last_daily_date TEXT,
                last_factor_date TEXT,
                last_success_at TEXT,
                failed_count INTEGER NOT NULL DEFAULT 0,
                last_error_message TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS stock_diagnosis_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                research_rating TEXT NOT NULL,
                rating_horizon TEXT NOT NULL,
                rating_summary TEXT NOT NULL,
                target_price_low REAL,
                target_price_mid REAL,
                target_price_high REAL,
                target_price_method TEXT NOT NULL DEFAULT '',
                target_price_confidence TEXT NOT NULL DEFAULT '低',
                key_bullish_reasons_json TEXT NOT NULL DEFAULT '[]',
                key_bearish_reasons_json TEXT NOT NULL DEFAULT '[]',
                upgrade_triggers_json TEXT NOT NULL DEFAULT '[]',
                downgrade_triggers_json TEXT NOT NULL DEFAULT '[]',
                rating_disclaimer TEXT NOT NULL DEFAULT '',
                rating_version TEXT NOT NULL DEFAULT 'stock-inspector-v1',
                overall_score REAL NOT NULL,
                technical_score REAL,
                fundamental_score REAL,
                sentiment_score REAL,
                capital_flow_score REAL,
                risk_control_score REAL,
                risk_level TEXT NOT NULL,
                data_confidence TEXT NOT NULL,
                summary TEXT NOT NULL,
                raw_factors_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(code, trade_date)
            );

            CREATE TABLE IF NOT EXISTS strategy_nav_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                nav REAL NOT NULL,
                daily_return REAL NOT NULL,
                cumulative_return REAL NOT NULL,
                benchmark_code TEXT NOT NULL DEFAULT 'LOCAL_EQUAL_WEIGHT',
                benchmark_nav REAL,
                benchmark_return REAL,
                drawdown REAL NOT NULL,
                market_regime TEXT,
                data_version TEXT NOT NULL DEFAULT 'local-sqlite-v1',
                parameter_hash TEXT NOT NULL DEFAULT 'default',
                source_task_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(trade_date, strategy_name)
            );

            CREATE INDEX IF NOT EXISTS idx_strategy_nav_daily_strategy_date
                ON strategy_nav_daily(strategy_name, trade_date);

            CREATE TABLE IF NOT EXISTS strategy_trade_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                entry_date TEXT NOT NULL,
                exit_date TEXT,
                entry_price REAL,
                exit_price REAL,
                holding_days INTEGER NOT NULL DEFAULT 0,
                return_rate REAL NOT NULL DEFAULT 0,
                max_drawdown_during_holding REAL,
                action TEXT NOT NULL DEFAULT '',
                weight REAL,
                exit_reason TEXT NOT NULL DEFAULT '',
                source_task_id INTEGER,
                created_at TEXT NOT NULL,
                UNIQUE(strategy_name, code, entry_date, exit_date)
            );

            CREATE INDEX IF NOT EXISTS idx_strategy_trade_records_strategy_date
                ON strategy_trade_records(strategy_name, entry_date);

            CREATE TABLE IF NOT EXISTS strategy_performance_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                period TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                return_rate REAL,
                annualized_return REAL,
                max_drawdown REAL,
                volatility REAL,
                sharpe_ratio REAL,
                win_rate REAL,
                trade_count INTEGER NOT NULL DEFAULT 0,
                avg_holding_days REAL,
                benchmark_return REAL,
                excess_return REAL,
                data_coverage_ratio REAL NOT NULL DEFAULT 0,
                validity_level TEXT NOT NULL,
                warnings_json TEXT NOT NULL DEFAULT '[]',
                parameter_hash TEXT NOT NULL DEFAULT 'default',
                data_version TEXT NOT NULL DEFAULT 'local-sqlite-v1',
                updated_at TEXT NOT NULL,
                UNIQUE(strategy_name, period, end_date)
            );

            CREATE INDEX IF NOT EXISTS idx_strategy_performance_summary_name_period
                ON strategy_performance_summary(strategy_name, period, end_date);

            CREATE TABLE IF NOT EXISTS strategy_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_title TEXT,
                source_author TEXT,
                source_url TEXT,
                publish_date TEXT,
                source_summary TEXT NOT NULL,
                original_idea TEXT NOT NULL,
                local_adaptation TEXT NOT NULL,
                implementation_notes TEXT NOT NULL,
                limitations_json TEXT NOT NULL DEFAULT '[]',
                required_data_json TEXT NOT NULL DEFAULT '[]',
                missing_data_json TEXT NOT NULL DEFAULT '[]',
                confidence_level TEXT NOT NULL DEFAULT '低',
                evidence_level TEXT NOT NULL DEFAULT '仅假设',
                is_verified_by_backtest INTEGER NOT NULL DEFAULT 0,
                backtest_validity TEXT NOT NULL DEFAULT '未验证',
                tags_json TEXT NOT NULL DEFAULT '[]',
                version TEXT NOT NULL DEFAULT 'v1',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(strategy_name, version)
            );

            CREATE INDEX IF NOT EXISTS idx_strategy_sources_name
                ON strategy_sources(strategy_name, version);
            """
        )
        _ensure_column(conn, "stocks", "list_date", "TEXT")
        _ensure_column(conn, "stocks", "is_st", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "stocks", "is_suspended", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "stocks", "float_market_cap", "REAL NOT NULL DEFAULT 8000000000")
        _ensure_column(conn, "market_snapshots_daily", "market", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "market_snapshots_daily", "industry", "TEXT NOT NULL DEFAULT '未分类'")
        _ensure_column(conn, "market_snapshots_daily", "float_market_value", "REAL")
        _ensure_column(conn, "market_snapshots_daily", "raw_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "market_snapshots_daily", "is_broken_board", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "market_snapshots_daily", "first_limit_time", "TEXT")
        _ensure_column(conn, "market_snapshots_daily", "last_limit_time", "TEXT")
        _ensure_column(conn, "market_snapshots_daily", "open_board_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "market_snapshots_daily", "seal_amount", "REAL")
        _ensure_column(conn, "market_snapshots_daily", "seal_amount_ratio", "REAL")
        _ensure_column(conn, "market_snapshots_daily", "limit_up_type", "TEXT NOT NULL DEFAULT '未知'")
        _ensure_column(conn, "market_snapshots_daily", "board_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "market_snapshots_daily", "is_new_high", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "market_data_sync_status", "task_id", "INTEGER")
        _ensure_column(conn, "signals", "metadata", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "stock_diagnosis_reports", "research_rating", "TEXT NOT NULL DEFAULT '无法评级'")
        _ensure_column(conn, "stock_diagnosis_reports", "rating_horizon", "TEXT NOT NULL DEFAULT '中期：1-3个月'")
        _ensure_column(conn, "stock_diagnosis_reports", "rating_summary", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "stock_diagnosis_reports", "target_price_low", "REAL")
        _ensure_column(conn, "stock_diagnosis_reports", "target_price_mid", "REAL")
        _ensure_column(conn, "stock_diagnosis_reports", "target_price_high", "REAL")
        _ensure_column(conn, "stock_diagnosis_reports", "target_price_method", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "stock_diagnosis_reports", "target_price_confidence", "TEXT NOT NULL DEFAULT '低'")
        _ensure_column(conn, "stock_diagnosis_reports", "key_bullish_reasons_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "stock_diagnosis_reports", "key_bearish_reasons_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "stock_diagnosis_reports", "upgrade_triggers_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "stock_diagnosis_reports", "downgrade_triggers_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "stock_diagnosis_reports", "rating_disclaimer", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "stock_diagnosis_reports", "rating_version", "TEXT NOT NULL DEFAULT 'stock-inspector-v1'")
        _ensure_column(conn, "strategy_nav_daily", "benchmark_code", "TEXT NOT NULL DEFAULT 'LOCAL_EQUAL_WEIGHT'")
        _ensure_column(conn, "strategy_nav_daily", "data_version", "TEXT NOT NULL DEFAULT 'local-sqlite-v1'")
        _ensure_column(conn, "strategy_nav_daily", "parameter_hash", "TEXT NOT NULL DEFAULT 'default'")
        _ensure_column(conn, "strategy_nav_daily", "source_task_id", "INTEGER")
        _ensure_column(conn, "strategy_trade_records", "action", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "strategy_trade_records", "weight", "REAL")
        _ensure_column(conn, "strategy_trade_records", "source_task_id", "INTEGER")
        _ensure_column(conn, "strategy_performance_summary", "parameter_hash", "TEXT NOT NULL DEFAULT 'default'")
        _ensure_column(conn, "strategy_performance_summary", "data_version", "TEXT NOT NULL DEFAULT 'local-sqlite-v1'")
        _ensure_column(conn, "task_runs", "parent_task_id", "INTEGER")
        _ensure_column(conn, "task_runs", "child_task_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "task_runs", "completed_child_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "task_runs", "failed_child_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "task_runs", "batch_mode", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "task_runs", "strategy_name", "TEXT")
        _ensure_column(conn, "task_runs", "task_group_name", "TEXT")
        _ensure_column(conn, "job_runs", "snapshot_type", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "job_runs", "result_summary", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "dashboard_snapshots", "summary_json", "TEXT NOT NULL DEFAULT '{}'")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_task_runs_parent
                ON task_runs(parent_task_id, id)
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_nav_daily_identity
                ON strategy_nav_daily(trade_date, strategy_name, parameter_hash, data_version)
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_performance_summary_identity
                ON strategy_performance_summary(strategy_name, period, end_date, parameter_hash, data_version)
            """
        )
        _ensure_column(conn, "strategy_sources", "source_title", "TEXT")
        _ensure_column(conn, "strategy_sources", "source_author", "TEXT")
        _ensure_column(conn, "strategy_sources", "source_url", "TEXT")
        _ensure_column(conn, "strategy_sources", "publish_date", "TEXT")
    seed_database()


def seed_database() -> None:
    with get_connection() as conn:
        stock_count = conn.execute("SELECT COUNT(*) AS c FROM stocks").fetchone()["c"]
        strategy_count = conn.execute("SELECT COUNT(*) AS c FROM strategies").fetchone()["c"]
        risk_count = conn.execute("SELECT COUNT(*) AS c FROM risk_rules").fetchone()["c"]

    seeded_stocks = stock_count == 0
    if stock_count == 0:
        _seed_stocks_and_prices()
    if strategy_count == 0:
        _seed_strategies()
    _ensure_dragon_strategy()
    _ensure_classic_quant_strategies()
    if risk_count == 0:
        _seed_risk_rules()
    _ensure_stock_metadata()
    from app.services.strategy_source_service import ensure_strategy_sources

    ensure_strategy_sources()
    if seeded_stocks or MARKET_DATA_SOURCE.lower() == "sample":
        refresh_sample_market_shape()


def _try_enable_wal_mode() -> None:
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.close()
    except sqlite3.OperationalError:
        pass


def _seed_stocks_and_prices() -> None:
    created = now_iso()
    stocks = [
        ("000001", "平安银行", "银行", "SZ"),
        ("600519", "贵州茅台", "食品饮料", "SH"),
        ("300750", "宁德时代", "电力设备", "SZ"),
        ("600036", "招商银行", "银行", "SH"),
        ("000858", "五粮液", "食品饮料", "SZ"),
        ("600276", "恒瑞医药", "医药生物", "SH"),
        ("002415", "海康威视", "计算机", "SZ"),
        ("601318", "中国平安", "非银金融", "SH"),
        ("600030", "中信证券", "非银金融", "SH"),
        ("002594", "比亚迪", "汽车", "SZ"),
        ("600887", "伊利股份", "食品饮料", "SH"),
        ("300059", "东方财富", "非银金融", "SZ"),
    ]

    end = date.today()
    days = _business_days(end - timedelta(days=260), end)
    rng = np.random.default_rng(42)

    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO stocks (code, name, industry, market, list_date, is_st, is_suspended, float_market_cap, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, ?)
            """,
            [
                (
                    code,
                    name,
                    industry,
                    market,
                    (end - timedelta(days=520 + index * 8)).isoformat(),
                    _sample_float_cap(index),
                    created,
                    created,
                )
                for index, (code, name, industry, market) in enumerate(stocks)
            ],
        )

        for index, (code, _name, _industry, _market) in enumerate(stocks):
            base_price = 12 + index * 8 + rng.uniform(0, 10)
            drift = 0.0004 + (index % 4) * 0.00018
            volatility = 0.014 + (index % 5) * 0.003
            price = base_price
            previous_close = price
            price_rows = []
            for offset, day in enumerate(days):
                cycle = math.sin(offset / 18 + index) * 0.006
                shock = rng.normal(drift + cycle, volatility)
                open_price = max(1.0, previous_close * (1 + rng.normal(0, volatility / 3)))
                close = max(1.0, open_price * (1 + shock))
                high = max(open_price, close) * (1 + abs(rng.normal(0.008, 0.004)))
                low = min(open_price, close) * (1 - abs(rng.normal(0.008, 0.004)))
                volume = max(100000, rng.normal(900000 + index * 120000, 180000))
                if offset > len(days) - 24 and index in {0, 2, 6, 9, 11}:
                    close *= 1.005 + (index % 3) * 0.002
                    volume *= 1.18
                pct_change = (close - previous_close) / previous_close * 100 if previous_close else 0
                amount = volume * close
                price_rows.append(
                    (
                        code,
                        day.isoformat(),
                        round(open_price, 2),
                        round(high, 2),
                        round(low, 2),
                        round(close, 2),
                        round(volume, 0),
                        round(amount, 2),
                        round(pct_change, 2),
                    )
                )
                previous_close = close
            conn.executemany(
                """
                INSERT INTO daily_prices
                    (stock_code, date, open, high, low, close, volume, amount, pct_change)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                price_rows,
            )


def _seed_strategies() -> None:
    created = now_iso()
    strategies = [
        (
            "均线趋势策略",
            "MA20 > MA60，价格站上 MA20，近 20 日收益为正且成交量放大。",
            "趋势",
            {
                "ma_short": 20,
                "ma_long": 60,
                "min_score": 60,
                "volume_window": 20,
            },
        ),
        (
            "低回撤趋势策略",
            "近 60 日收益为正，最大回撤低于阈值，波动率低于市场均值且中期趋势向上。",
            "趋势",
            {
                "lookback": 60,
                "max_drawdown_threshold": 0.16,
                "volatility_threshold": 0.035,
                "min_score": 60,
            },
        ),
        (
            "多因子评分策略",
            "综合动量、波动率、成交量、回撤和趋势因子，输出 0-100 综合评分。",
            "多因子",
            {
                "min_score": 60,
                "weights": {
                    "momentum": 0.25,
                    "volatility": 0.2,
                    "volume": 0.15,
                    "drawdown": 0.2,
                    "trend": 0.2,
                },
            },
        ),
    ]
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO strategies (name, description, type, parameters, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            [(name, description, strategy_type, json.dumps(params, ensure_ascii=False), created, created) for name, description, strategy_type, params in strategies],
        )


def _ensure_dragon_strategy() -> None:
    created = now_iso()
    params = {
        "strategy_class": "DragonLeaderStrategy",
        "display_name": "短线龙头候选策略",
        "dragon_config": {
            "minListDays": 60,
            "minClosePrice": 3,
            "maxClosePrice": 80,
            "minAmount": 200000000,
            "minFloatMarketCap": 2000000000,
            "maxFloatMarketCap": 30000000000,
            "minScore": 60,
        },
        "backtest": {
            "max_holding_days": 5,
            "stop_loss": 0.06,
            "take_profit": 0.12,
            "position_cap": 0.1,
            "max_positions": 3,
        },
    }
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT id FROM strategies WHERE name = ? OR parameters LIKE ?",
            ("短线龙头候选策略", "%DragonLeaderStrategy%"),
        ).fetchone()
        if exists:
            return
        conn.execute(
            """
            INSERT INTO strategies (name, description, type, parameters, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (
                "短线龙头候选策略",
                "DragonLeaderStrategy：筛选短期强势题材中的龙头候选，仅用于观察清单、风险提示、回测依据和人工确认。",
                "短线龙头",
                json.dumps(params, ensure_ascii=False),
                created,
                created,
            ),
        )


def _ensure_classic_quant_strategies() -> None:
    created = now_iso()
    strategies = [
        (
            "市场热点候选策略",
            "MarketHotspotStrategy：基于行业热度、短线强度、资金活跃度和龙头辨识度生成热点观察清单，不输出投资建议。",
            "短线热点",
            {
                "strategy_class": "MarketHotspotStrategy",
                "classic_config": {
                    "min_list_days": 60,
                    "min_amount": 200000000,
                    "min_close_price": 3,
                    "min_float_market_cap": 2000000000,
                    "max_float_market_cap": 50000000000,
                    "min_score": 60,
                    "max_position": 0.1,
                },
            },
        ),
        (
            "价值动量策略",
            "ValueMomentumStrategy：结合低估值、分红/现金流代理因子与中期动量，仅用于观察清单、风险提示、回测依据和人工确认。",
            "经典多因子",
            {
                "strategy_class": "ValueMomentumStrategy",
                "classic_config": {"min_list_days": 120, "min_amount": 100000000, "min_float_market_cap": 2000000000, "min_score": 30, "max_position": 0.1},
            },
        ),
        (
            "质量动量策略",
            "QualityMomentumStrategy：结合盈利质量代理因子、中期趋势和安全边际，仅用于个人量化研究和复盘。",
            "经典多因子",
            {
                "strategy_class": "QualityMomentumStrategy",
                "classic_config": {"min_list_days": 120, "min_amount": 100000000, "min_float_market_cap": 2000000000, "min_score": 30, "max_position": 0.1},
            },
        ),
        (
            "低波防御策略",
            "LowBetaDefensiveStrategy：在 RiskOff 或 Choppy 阶段输出低 Beta / 低波观察清单，不输出投资建议。",
            "防御",
            {
                "strategy_class": "LowBetaDefensiveStrategy",
                "classic_config": {"min_list_days": 120, "min_amount": 100000000, "min_float_market_cap": 2000000000, "min_score": 30, "max_position": 0.1},
            },
        ),
        (
            "趋势跟踪策略",
            "TrendFollowingStrategy：中期趋势跟踪观察模型，随市场状态进行启用或降权。",
            "趋势",
            {
                "strategy_class": "TrendFollowingStrategy",
                "classic_config": {"min_list_days": 120, "min_amount": 100000000, "min_float_market_cap": 2000000000, "min_score": 30, "max_position": 0.1},
            },
        ),
    ]
    with get_connection() as conn:
        for name, description, strategy_type, params in strategies:
            exists = conn.execute(
                "SELECT id FROM strategies WHERE name = ? OR parameters LIKE ?",
                (name, f"%{params['strategy_class']}%"),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """
                INSERT INTO strategies (name, description, type, parameters, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (name, description, strategy_type, json.dumps(params, ensure_ascii=False), created, created),
            )


def _ensure_stock_metadata() -> None:
    with get_connection() as conn:
        rows = conn.execute("SELECT id, code, name FROM stocks ORDER BY code").fetchall()
        for index, row in enumerate(rows):
            first_price = conn.execute(
                "SELECT MIN(date) AS first_date FROM daily_prices WHERE stock_code = ?",
                (row["code"],),
            ).fetchone()["first_date"]
            list_date = first_price or (date.today() - timedelta(days=520 + index * 8)).isoformat()
            conn.execute(
                """
                UPDATE stocks
                SET list_date = COALESCE(list_date, ?),
                    is_st = CASE WHEN UPPER(name) LIKE '%ST%' THEN 1 ELSE COALESCE(is_st, 0) END,
                    is_suspended = COALESCE(is_suspended, 0),
                    float_market_cap = CASE
                        WHEN float_market_cap IS NULL OR float_market_cap <= 0 THEN ?
                        ELSE float_market_cap
                    END
                WHERE id = ?
                """,
                (list_date, _sample_float_cap(index), row["id"]),
            )


def _ensure_dragon_sample_prices() -> None:
    targets = {
        "000001": {"pct": 9.92, "boards": 2, "amount": 650000000},
        "600036": {"pct": 9.86, "boards": 1, "amount": 520000000},
        "002415": {"pct": 7.2, "boards": 0, "amount": 420000000},
    }
    with get_connection() as conn:
        for code, config in targets.items():
            rows = conn.execute(
                "SELECT * FROM daily_prices WHERE stock_code = ? ORDER BY date DESC LIMIT 24",
                (code,),
            ).fetchall()
            if len(rows) < 10:
                continue
            ordered = list(reversed(rows))
            if config["boards"]:
                _shape_limit_boards(conn, code, ordered, int(config["boards"]), float(config["pct"]), float(config["amount"]))
            else:
                _shape_strong_breakout(conn, code, ordered, float(config["pct"]), float(config["amount"]))


def refresh_sample_market_shape() -> None:
    _ensure_dragon_sample_prices()
    _normalize_sample_price_scale()
    _ensure_dragon_sample_prices()


def _normalize_sample_price_scale() -> None:
    with get_connection() as conn:
        for code, target_close in SAMPLE_LATEST_PRICE_ANCHORS.items():
            latest = conn.execute(
                "SELECT close FROM daily_prices WHERE stock_code = ? ORDER BY date DESC LIMIT 1",
                (code,),
            ).fetchone()
            if not latest:
                continue
            current_close = float(latest["close"] or 0)
            if current_close <= 0:
                continue
            ratio = target_close / current_close
            conn.execute(
                """
                UPDATE daily_prices
                SET open = ROUND(open * ?, 2),
                    high = ROUND(high * ?, 2),
                    low = ROUND(low * ?, 2),
                    close = ROUND(close * ?, 2),
                    amount = ROUND(volume * ROUND(close * ?, 2), 2)
                WHERE stock_code = ?
                """,
                (ratio, ratio, ratio, ratio, ratio, code),
            )


def _shape_limit_boards(conn: sqlite3.Connection, code: str, rows: list[sqlite3.Row], boards: int, pct: float, amount: float) -> None:
    start_index = max(1, len(rows) - boards)
    previous_close = float(rows[start_index - 1]["close"])
    for idx in range(start_index, len(rows)):
        row = rows[idx]
        close = round(previous_close * (1 + pct / 100), 2)
        open_price = round(close * 0.985, 2)
        high = close
        low = round(open_price * 0.992, 2)
        volume = round(amount / close, 0)
        conn.execute(
            """
            UPDATE daily_prices
            SET open = ?, high = ?, low = ?, close = ?, volume = ?, amount = ?, pct_change = ?
            WHERE id = ?
            """,
            (open_price, high, low, close, volume, round(volume * close, 2), pct, row["id"]),
        )
        previous_close = close


def _shape_strong_breakout(conn: sqlite3.Connection, code: str, rows: list[sqlite3.Row], pct: float, amount: float) -> None:
    latest = rows[-1]
    previous = rows[-2]
    high20 = max(float(row["high"]) for row in rows[-21:-1])
    close = round(max(float(previous["close"]) * (1 + pct / 100), high20 * 1.01), 2)
    open_price = round(float(previous["close"]) * 1.025, 2)
    low = round(min(open_price, close) * 0.985, 2)
    high = round(close * 1.015, 2)
    volume = round(amount / close, 0)
    pct_change = round((close - float(previous["close"])) / float(previous["close"]) * 100, 2)
    conn.execute(
        """
        UPDATE daily_prices
        SET open = ?, high = ?, low = ?, close = ?, volume = ?, amount = ?, pct_change = ?
        WHERE id = ?
        """,
        (open_price, high, low, close, volume, round(volume * close, 2), pct_change, latest["id"]),
    )


def _sample_float_cap(index: int) -> float:
    return float(4500000000 + (index % 7) * 3200000000)


def _seed_risk_rules() -> None:
    rules = [
        ("最低候选评分", "单只股票评分低于阈值时不进入候选池。", 60),
        ("单票最大仓位", "单只股票建议仓位上限。", 0.2),
        ("策略最大回撤预警", "策略回撤超过阈值时进入降权观察。", 0.18),
        ("连续亏损预警", "连续亏损次数超过阈值时标记策略失效观察。", 3),
        ("高风险波动率", "近 60 日年化波动率超过阈值时标记高风险。", 0.35),
    ]
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO risk_rules (name, description, threshold, enabled) VALUES (?, ?, ?, 1)",
            rules,
        )


def _business_days(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
