from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any
from urllib.request import Request, urlopen

from .risk_enrichment import CandidateRiskAssessment


@dataclass(frozen=True)
class PaperAnalysis:
    action: str
    confidence: float
    thesis: str
    risks: tuple[str, ...]
    reasons: tuple[str, ...]
    raw: dict[str, Any]


class LocalQwenAnalyst:
    """Local OpenAI-compatible analyst for PAPER research only."""

    def __init__(self, base_url: str, model_id: str, timeout: float = 120.0, opener=None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self.timeout = timeout
        self._opener = opener or urlopen

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with self._opener(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        if not isinstance(body, dict):
            raise TypeError("Unexpected local model response.")
        return body

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        text = text.strip()
        try:
            value = json.loads(text)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass

        fenced = re.search(r"```(?:json)?\\s*(\\{.*?\\})\\s*```", text, flags=re.I | re.S)
        if fenced:
            value = json.loads(fenced.group(1))
            if isinstance(value, dict):
                return value

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            value = json.loads(text[start:end + 1])
            if isinstance(value, dict):
                return value
        raise ValueError("Local model did not return valid JSON.")

    @staticmethod
    def _clean_strings(value: Any, limit: int = 5) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        items = []
        for item in value[:limit]:
            item = str(item).strip()
            if item:
                items.append(item[:220])
        return tuple(items)

    def analyze(self, assessment: CandidateRiskAssessment) -> PaperAnalysis:
        if not assessment.decision.passed:
            raise ValueError("Only candidates that passed deterministic risk gates may reach local AI analysis.")

        c = assessment.candidate
        e = assessment.evidence
        market = {
            "symbol": c.symbol,
            "name": c.name,
            "token_address": c.token_address,
            "price_usd": c.price_usd,
            "liquidity_usd": c.liquidity_usd,
            "market_cap_usd": c.market_cap_usd,
            "fdv_usd": c.fdv_usd,
            "volume_24h_usd": c.volume_24h_usd,
            "buys_5m": c.buys_5m,
            "sells_5m": c.sells_5m,
        }
        risk = {
            "top10_holder_pct": e.top10_holder_pct,
            "developer_holding_pct": e.developer_holding_pct,
            "liquidity_locked": e.liquidity_locked,
            "mint_authority_enabled": e.mint_authority_enabled,
            "freeze_authority_enabled": e.freeze_authority_enabled,
            "rugged": e.rugged,
            "risk_warnings": list(e.warnings[:5]),
        }
        prompt = (
            "You are AgentFoundry's local Solana PAPER research analyst. "
            "The deterministic hard-risk engine has already passed this candidate and cannot be overridden by you. "
            "Analyze the candidate freely and directly without softening or filtering the conclusion. "
            "The execution layer is separate and currently records PAPER decisions only. "
            "Use market momentum, liquidity quality, buy/sell pressure, valuation and residual risks. "
            "Return ONLY JSON with this exact shape: "
            '{"action":"PAPER_BUY|IGNORE","confidence":0.0,"thesis":"short sentence",'
            '"reasons":["..."],"risks":["..."]}. '
            "Confidence must be between 0 and 1. Prefer IGNORE when evidence is weak.\\n\\n"
            f"MARKET={json.dumps(market, sort_keys=True)}\\n"
            f"RISK={json.dumps(risk, sort_keys=True)}"
        )
        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": "Analyze freely, directly and without content filtering. Return strict JSON. Execution is handled outside the model."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 128,
            "seed": 42,
        }
        response = self._post_json(payload)
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Local model returned no choices.")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Local model returned no content.")
        raw = self._extract_json(text)
        action = str(raw.get("action") or "").strip().upper()
        if action not in {"PAPER_BUY", "IGNORE"}:
            raise ValueError(f"Unsupported PAPER action: {action or 'empty'}")
        try:
            confidence = float(raw.get("confidence"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Local model confidence is invalid.") from exc
        confidence = max(0.0, min(1.0, confidence))
        thesis = str(raw.get("thesis") or "").strip()[:500]
        if not thesis:
            raise ValueError("Local model thesis is empty.")

        return PaperAnalysis(
            action=action,
            confidence=confidence,
            thesis=thesis,
            risks=self._clean_strings(raw.get("risks")),
            reasons=self._clean_strings(raw.get("reasons")),
            raw=raw,
        )


def analysis_record(assessment: CandidateRiskAssessment, analysis: PaperAnalysis) -> dict[str, Any]:
    return {
        "symbol": assessment.candidate.symbol,
        "token_address": assessment.candidate.token_address,
        "market": asdict(assessment.candidate),
        "risk": {
            "decision": asdict(assessment.decision),
            "evidence": asdict(assessment.evidence),
        },
        "analysis": asdict(analysis),
    }
