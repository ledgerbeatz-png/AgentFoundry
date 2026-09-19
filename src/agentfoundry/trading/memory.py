from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2


@dataclass(frozen=True)
class TradeRecord:
    trade_id: str
    symbol: str
    strategy_version: str
    opened_at: float
    entry_price: float
    quantity: float
    status: str = "open"


class TradeMemory:
    """SQLite evidence store for paper-trading learning and reproducibility."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS trades (
            trade_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, strategy_version TEXT NOT NULL,
            opened_at REAL NOT NULL, entry_price REAL NOT NULL, quantity REAL NOT NULL,
            status TEXT NOT NULL, closed_at REAL, exit_price REAL, realized_pnl_pct REAL,
            mfe_pct REAL, mae_pct REAL
        );
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, trade_id TEXT NOT NULL, observed_at REAL NOT NULL,
            action TEXT NOT NULL, reasons_json TEXT NOT NULL, market_json TEXT NOT NULL,
            FOREIGN KEY(trade_id) REFERENCES trades(trade_id)
        );
        CREATE TABLE IF NOT EXISTS outcomes (
            trade_id TEXT NOT NULL, horizon TEXT NOT NULL, observed_at REAL NOT NULL,
            price REAL NOT NULL, return_from_entry_pct REAL NOT NULL,
            PRIMARY KEY(trade_id, horizon), FOREIGN KEY(trade_id) REFERENCES trades(trade_id)
        );
        CREATE TABLE IF NOT EXISTS research_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            observed_at REAL NOT NULL,
            action TEXT NOT NULL,
            confidence REAL NOT NULL,
            thesis TEXT NOT NULL,
            market_json TEXT NOT NULL,
            risk_json TEXT NOT NULL,
            analysis_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_research_decisions_candidate_time
            ON research_decisions(candidate_id, observed_at);
        """)
        self.db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
        self.db.commit()

    def open_trade(self, record: TradeRecord) -> None:
        self.db.execute(
            "INSERT INTO trades(trade_id,symbol,strategy_version,opened_at,entry_price,quantity,status) VALUES(?,?,?,?,?,?,?)",
            (record.trade_id, record.symbol, record.strategy_version, record.opened_at, record.entry_price, record.quantity, record.status),
        )
        self.db.commit()

    def add_decision(self, trade_id: str, observed_at: float, action: str, reasons: tuple[str, ...], market: dict[str, Any]) -> None:
        self.db.execute(
            "INSERT INTO decisions(trade_id,observed_at,action,reasons_json,market_json) VALUES(?,?,?,?,?)",
            (trade_id, observed_at, action, json.dumps(reasons), json.dumps(market, sort_keys=True)),
        )
        self.db.commit()

    def add_research_decision(
        self,
        candidate_id: str,
        symbol: str,
        observed_at: float,
        action: str,
        confidence: float,
        thesis: str,
        market: dict[str, Any],
        risk: dict[str, Any],
        analysis: dict[str, Any],
    ) -> None:
        self.db.execute(
            "INSERT INTO research_decisions(candidate_id,symbol,observed_at,action,confidence,thesis,market_json,risk_json,analysis_json) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (
                candidate_id,
                symbol,
                observed_at,
                action,
                float(confidence),
                thesis,
                json.dumps(market, sort_keys=True),
                json.dumps(risk, sort_keys=True),
                json.dumps(analysis, sort_keys=True),
            ),
        )
        self.db.commit()

    def research_decisions(self, limit: int = 100) -> list[sqlite3.Row]:
        return list(
            self.db.execute(
                "SELECT * FROM research_decisions ORDER BY observed_at DESC LIMIT ?",
                (max(1, int(limit)),),
            )
        )

    def close_trade(self, trade_id: str, closed_at: float, exit_price: float, realized_pnl_pct: float, mfe_pct: float, mae_pct: float) -> None:
        self.db.execute(
            "UPDATE trades SET status='closed',closed_at=?,exit_price=?,realized_pnl_pct=?,mfe_pct=?,mae_pct=? WHERE trade_id=?",
            (closed_at, exit_price, realized_pnl_pct, mfe_pct, mae_pct, trade_id),
        )
        self.db.commit()

    def add_outcome(self, trade_id: str, horizon: str, observed_at: float, price: float) -> None:
        row = self.db.execute("SELECT entry_price FROM trades WHERE trade_id=?", (trade_id,)).fetchone()
        if row is None:
            raise KeyError(trade_id)
        ret = (price / row["entry_price"] - 1.0) * 100.0
        self.db.execute(
            "INSERT OR REPLACE INTO outcomes(trade_id,horizon,observed_at,price,return_from_entry_pct) VALUES(?,?,?,?,?)",
            (trade_id, horizon, observed_at, price, ret),
        )
        self.db.commit()

    def closed_trades(self, strategy_version: str | None = None) -> list[sqlite3.Row]:
        if strategy_version:
            return list(self.db.execute("SELECT * FROM trades WHERE status='closed' AND strategy_version=? ORDER BY opened_at", (strategy_version,)))
        return list(self.db.execute("SELECT * FROM trades WHERE status='closed' ORDER BY opened_at"))

    def close(self) -> None:
        self.db.close()
