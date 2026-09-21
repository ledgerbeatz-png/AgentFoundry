from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
import time
from typing import Any
from urllib.parse import quote
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .market_data import MarketCandidate
from .risk import RiskDecision, RiskPolicy, TokenSnapshot, evaluate_snapshot


RUGCHECK_BASE = "https://api.rugcheck.xyz"


def redact_rpc_url(url: str) -> str:
    """Keep provider identity visible without leaking API keys or query secrets."""
    if not url:
        return ""
    try:
        from urllib.parse import urlsplit
        parts = urlsplit(url)
        if not parts.scheme or not parts.netloc:
            return "[configured RPC]"
        return f"{parts.scheme}://{parts.netloc}{parts.path}"
    except Exception:
        return "[configured RPC]"


@dataclass(frozen=True)
class RiskEvidence:
    top10_holder_pct: float | None
    developer_holding_pct: float | None
    liquidity_locked: bool | None
    mint_authority_enabled: bool | None
    freeze_authority_enabled: bool | None
    rugged: bool | None
    score: float | None
    missing: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CandidateRiskAssessment:
    candidate: MarketCandidate
    status: str
    decision: RiskDecision
    evidence: RiskEvidence


class SolanaRpcRiskClient:
    """Read-only Solana RPC fallback for incomplete third-party risk reports."""

    def __init__(
        self,
        rpc_url: str | None = None,
        timeout: float = 12.0,
        opener=None,
        min_interval: float = 0.9,
    ) -> None:
        configured = rpc_url or os.environ.get("SOLANA_RPC_URL")
        defaults = [
            "https://api.mainnet.solana.com",
            "https://api.mainnet-beta.solana.com",
            "https://solana-rpc.publicnode.com",
        ]
        self.rpc_urls = []
        source_urls = [configured] if configured else defaults
        for url in source_urls:
            if url and url not in self.rpc_urls:
                self.rpc_urls.append(url)
        self.timeout = timeout
        self._opener = opener or urlopen
        self._request_id = 0
        self.last_rpc_url = ""
        self.min_interval = max(0.0, min_interval)
        self._last_request_at = 0.0

    def _pace(self) -> None:
        remaining = self.min_interval - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)

    def _rpc(self, method: str, params: list[Any]) -> Any:
        errors: list[str] = []
        for rpc_url in self.rpc_urls:
            for attempt in range(2):
                self._pace()
                self._request_id += 1
                payload = json.dumps({
                    "jsonrpc": "2.0",
                    "id": self._request_id,
                    "method": method,
                    "params": params,
                }).encode("utf-8")
                request = Request(
                    rpc_url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "User-Agent": "AgentFoundry/0.1 SolanaResearchPaper",
                    },
                    method="POST",
                )
                try:
                    self._last_request_at = time.monotonic()
                    with self._opener(request, timeout=self.timeout) as response:
                        body = json.loads(response.read().decode("utf-8"))
                    if not isinstance(body, dict) or body.get("error"):
                        raise RuntimeError(
                            str(body.get("error") if isinstance(body, dict) else "invalid response")
                        )
                    self.last_rpc_url = rpc_url
                    return body.get("result")
                except HTTPError as exc:
                    errors.append(f"{rpc_url}: HTTP {exc.code}")
                    if exc.code in {429, 503} and attempt == 0:
                        retry_after = exc.headers.get("Retry-After") if exc.headers else None
                        try:
                            wait = float(retry_after) if retry_after else 2.0
                        except (TypeError, ValueError):
                            wait = 2.0
                        time.sleep(max(1.0, min(wait, 5.0)))
                        continue
                    break
                except Exception as exc:
                    errors.append(f"{rpc_url}: {type(exc).__name__}: {exc}")
                    break
        raise RuntimeError(f"Solana RPC {method} failed on all endpoints: {' | '.join(errors)}")

    @staticmethod
    def _raw_amount(value: Any) -> int:
        try:
            return int(str(value or "0"))
        except (TypeError, ValueError):
            return 0

    def enrich(
        self,
        mint: str,
        creator: str = "",
        supply: int | None = None,
        need_authorities: bool = False,
    ) -> dict[str, Any]:
        supply = self._raw_amount(supply)
        if supply <= 0:
            supply_result = self._rpc("getTokenSupply", [mint, {"commitment": "confirmed"}]) or {}
            supply_value = supply_result.get("value") if isinstance(supply_result, dict) else {}
            supply = self._raw_amount((supply_value or {}).get("amount"))
        if supply <= 0:
            raise RuntimeError("Solana RPC returned an invalid token supply.")

        largest_result = self._rpc("getTokenLargestAccounts", [mint, {"commitment": "confirmed"}]) or {}
        largest = largest_result.get("value") if isinstance(largest_result, dict) else []
        largest = largest if isinstance(largest, list) else []
        top10_amount = sum(
            self._raw_amount(item.get("amount"))
            for item in largest[:10]
            if isinstance(item, dict)
        )
        top10_pct = (top10_amount / supply) * 100.0 if largest else None

        mint_enabled = None
        freeze_enabled = None
        if need_authorities:
            account_result = self._rpc(
                "getAccountInfo",
                [mint, {"encoding": "jsonParsed", "commitment": "confirmed"}],
            ) or {}
            account = account_result.get("value") if isinstance(account_result, dict) else None
            info = {}
            if isinstance(account, dict):
                data = account.get("data")
                parsed = data.get("parsed") if isinstance(data, dict) else None
                info = parsed.get("info") if isinstance(parsed, dict) and isinstance(parsed.get("info"), dict) else {}
            if "mintAuthority" in info:
                mint_enabled = info.get("mintAuthority") is not None
            if "freezeAuthority" in info:
                freeze_enabled = info.get("freezeAuthority") is not None

        developer_pct = None
        if creator:
            owned_result = self._rpc(
                "getTokenAccountsByOwner",
                [creator, {"mint": mint}, {"encoding": "jsonParsed", "commitment": "confirmed"}],
            ) or {}
            accounts = owned_result.get("value") if isinstance(owned_result, dict) else []
            accounts = accounts if isinstance(accounts, list) else []
            developer_amount = 0
            for row in accounts:
                if not isinstance(row, dict):
                    continue
                account_data = row.get("account")
                data = account_data.get("data") if isinstance(account_data, dict) else None
                parsed = data.get("parsed") if isinstance(data, dict) else None
                token_info = parsed.get("info") if isinstance(parsed, dict) else None
                token_amount = token_info.get("tokenAmount") if isinstance(token_info, dict) else None
                if isinstance(token_amount, dict):
                    developer_amount += self._raw_amount(token_amount.get("amount"))
            developer_pct = (developer_amount / supply) * 100.0

        return {
            "top10_holder_pct": top10_pct,
            "developer_holding_pct": developer_pct,
            "mint_authority_enabled": mint_enabled,
            "freeze_authority_enabled": freeze_enabled,
        }


class RugCheckClient:
    """Read-only RugCheck adapter with defensive parsing.

    Missing or ambiguous evidence never becomes a pass. The deterministic gate
    only evaluates a token after every required safety field is available.
    """

    def __init__(
        self,
        timeout: float = 15.0,
        opener=None,
        delay_seconds: float = 0.35,
        rpc_client: SolanaRpcRiskClient | None = None,
    ) -> None:
        self.timeout = timeout
        self._opener = opener or urlopen
        self.delay_seconds = max(0.0, delay_seconds)
        self.rpc_client = rpc_client or SolanaRpcRiskClient(timeout=timeout)

    def report(self, mint: str) -> dict[str, Any]:
        mint = mint.strip()
        if len(mint) < 32:
            raise ValueError("A valid-looking Solana mint address is required.")
        request = Request(
            f"{RUGCHECK_BASE}/v1/tokens/{quote(mint, safe='')}/report",
            headers={
                "Accept": "application/json",
                "User-Agent": "AgentFoundry/0.1 SolanaResearchPaper",
            },
        )
        with self._opener(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("Unexpected RugCheck response format.")
        return payload

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _holder_pct(cls, holder: dict[str, Any]) -> float | None:
        for key in ("pct", "percentage", "percent"):
            number = cls._number(holder.get(key))
            if number is not None:
                return number
        return None

    @staticmethod
    def _authority(report: dict[str, Any], key: str) -> tuple[bool | None, bool]:
        token = report.get("token") if isinstance(report.get("token"), dict) else {}
        if key in report:
            return report.get(key) is not None, True
        if key in token:
            return token.get(key) is not None, True
        return None, False

    @classmethod
    def parse(cls, report: dict[str, Any]) -> RiskEvidence:
        missing: list[str] = []
        warnings: list[str] = []

        holders = report.get("topHolders")
        if not isinstance(holders, list):
            holders = []
        holder_pcts = [
            pct for holder in holders[:10]
            if isinstance(holder, dict) and (pct := cls._holder_pct(holder)) is not None
        ]
        top10 = sum(holder_pcts) if holder_pcts else None
        if top10 is None:
            missing.append("top10_holder_pct")

        creator = str(report.get("creator") or "").strip()
        developer = None
        if creator and holders:
            creator_pcts = []
            for holder in holders:
                if not isinstance(holder, dict):
                    continue
                owner = str(holder.get("owner") or holder.get("address") or "").strip()
                pct = cls._holder_pct(holder)
                if owner == creator and pct is not None:
                    creator_pcts.append(pct)
            if creator_pcts:
                developer = sum(creator_pcts)
            else:
                # Creator is known and absent from reported top holders. Treat this
                # as zero only if RugCheck supplied a holder set; otherwise unknown.
                developer = 0.0
        if developer is None:
            missing.append("developer_holding_pct")

        mint_enabled, mint_known = cls._authority(report, "mintAuthority")
        freeze_enabled, freeze_known = cls._authority(report, "freezeAuthority")
        if not mint_known:
            missing.append("mint_authority")
        if not freeze_known:
            missing.append("freeze_authority")

        lock_values: list[float] = []
        markets = report.get("markets")
        if isinstance(markets, list):
            for market in markets:
                if not isinstance(market, dict):
                    continue
                lp = market.get("lp") if isinstance(market.get("lp"), dict) else {}
                for key in ("lpLockedPct", "lpBurnedPct", "lockedPct", "burnedPct"):
                    value = cls._number(lp.get(key))
                    if value is not None:
                        lock_values.append(value)
        liquidity_locked = max(lock_values) >= 95.0 if lock_values else None
        if liquidity_locked is None:
            missing.append("liquidity_lock")

        risks = report.get("risks")
        if isinstance(risks, list):
            for risk in risks:
                if isinstance(risk, dict):
                    name = str(risk.get("name") or risk.get("description") or "").strip()
                    if name:
                        warnings.append(name)

        rugged = report.get("rugged") if isinstance(report.get("rugged"), bool) else None
        score = cls._number(report.get("score"))

        return RiskEvidence(
            top10_holder_pct=top10,
            developer_holding_pct=developer,
            liquidity_locked=liquidity_locked,
            mint_authority_enabled=mint_enabled,
            freeze_authority_enabled=freeze_enabled,
            rugged=rugged,
            score=score,
            missing=tuple(missing),
            warnings=tuple(warnings[:8]),
        )

    def assess(
        self,
        candidate: MarketCandidate,
        policy: RiskPolicy | None = None,
    ) -> CandidateRiskAssessment:
        report = self.report(candidate.token_address)
        evidence = self.parse(report)

        # Fresh launches can have an incomplete RugCheck holder set for a short
        # period. Fill only missing on-chain fields from read-only Solana RPC.
        if any(name in evidence.missing for name in (
            "top10_holder_pct",
            "developer_holding_pct",
            "mint_authority",
            "freeze_authority",
        )):
            creator = str(report.get("creator") or "").strip()
            try:
                token = report.get("token") if isinstance(report.get("token"), dict) else {}
                report_supply = self.rpc_client._raw_amount(token.get("supply"))
                fallback = self.rpc_client.enrich(
                    candidate.token_address,
                    creator=creator,
                    supply=report_supply or None,
                    need_authorities=(
                        evidence.mint_authority_enabled is None
                        or evidence.freeze_authority_enabled is None
                    ),
                )
            except Exception as exc:
                fallback = {}
                rpc_warning = f"solana_rpc_fallback_failed:{type(exc).__name__}:{str(exc)[:160]}"
            else:
                rpc_warning = "solana_rpc_fallback_used:" + redact_rpc_url(self.rpc_client.last_rpc_url or "custom")

            top10 = evidence.top10_holder_pct
            developer = evidence.developer_holding_pct
            mint_enabled = evidence.mint_authority_enabled
            freeze_enabled = evidence.freeze_authority_enabled
            if top10 is None:
                top10 = fallback.get("top10_holder_pct")
            if developer is None:
                developer = fallback.get("developer_holding_pct")
            if mint_enabled is None:
                mint_enabled = fallback.get("mint_authority_enabled")
            if freeze_enabled is None:
                freeze_enabled = fallback.get("freeze_authority_enabled")

            missing = []
            if top10 is None:
                missing.append("top10_holder_pct")
            if developer is None:
                missing.append("developer_holding_pct")
            if evidence.liquidity_locked is None:
                missing.append("liquidity_lock")
            if mint_enabled is None:
                missing.append("mint_authority")
            if freeze_enabled is None:
                missing.append("freeze_authority")

            evidence = replace(
                evidence,
                top10_holder_pct=top10,
                developer_holding_pct=developer,
                mint_authority_enabled=mint_enabled,
                freeze_authority_enabled=freeze_enabled,
                missing=tuple(missing),
                warnings=evidence.warnings + (rpc_warning,),
            )

        reasons: list[str] = []
        if evidence.rugged is True:
            reasons.append("rugcheck_rugged")
        reasons.extend(f"missing_{name}" for name in evidence.missing)

        if reasons:
            decision = RiskDecision(False, tuple(reasons))
            status = "BLOCK"
        else:
            snapshot = TokenSnapshot(
                symbol=candidate.symbol,
                market_cap_usd=candidate.market_cap_usd or 0.0,
                liquidity_usd=candidate.liquidity_usd,
                top10_holder_pct=float(evidence.top10_holder_pct),
                developer_holding_pct=float(evidence.developer_holding_pct),
                liquidity_locked=bool(evidence.liquidity_locked),
                mint_authority_enabled=bool(evidence.mint_authority_enabled),
                freeze_authority_enabled=bool(evidence.freeze_authority_enabled),
            )
            decision = evaluate_snapshot(snapshot, policy)
            status = "PASS" if decision.passed else "BLOCK"

        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        return CandidateRiskAssessment(candidate, status, decision, evidence)
