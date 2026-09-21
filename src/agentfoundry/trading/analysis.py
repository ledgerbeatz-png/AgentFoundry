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
        if not text:
            raise ValueError("Local model returned empty JSON content.")

        try:
            value = json.loads(text)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass

        decoder = json.JSONDecoder()
        # Qwen may wrap otherwise valid JSON in prose, markdown fences or thinking
        # text. Decode the first valid object instead of requiring a pristine reply.
        for index, character in enumerate(text):
            if character != "{":
                continue
            try:
                value, _end = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value

        raise ValueError("Local model did not return valid JSON.")

    @staticmethod
    def _extract_partial_core(text: str) -> dict[str, Any]:
        """Salvage a complete action/confidence/thesis from a truncated JSON reply.

        Qwen often emits the decisive fields first and gets cut off later while
        expanding reasons/risks. We keep those model-produced core fields and
        leave unfinished optional arrays empty instead of discarding the decision.
        """
        def string_field(name: str) -> str | None:
            match = re.search(
                rf'"{re.escape(name)}"\s*:\s*("(?:\\.|[^"\\])*")',
                text,
                flags=re.S,
            )
            if not match:
                return None
            try:
                return str(json.loads(match.group(1)))
            except json.JSONDecodeError:
                return None

        action = string_field("action")
        thesis = string_field("thesis")
        confidence_match = re.search(
            r'"confidence"\s*:\s*(-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)',
            text,
        )
        if not action or not thesis or not confidence_match:
            raise ValueError("Truncated local model output did not contain complete core fields.")
        return {
            "action": action,
            "confidence": float(confidence_match.group(1)),
            "thesis": thesis,
            "reasons": [],
            "risks": [],
            "_recovered_from_truncated_output": True,
        }

    @staticmethod
    def _content(response: dict[str, Any]) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Local model returned no choices.")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Local model returned no content.")
        return text

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
            "Return ONLY compact JSON with this exact shape: "
            '{"action":"PAPER_BUY|IGNORE","confidence":0.0,"thesis":"one short sentence",'
            '"reasons":["max 2 short items"],"risks":["max 2 short items"]}. '
            "Keep the whole response under 120 tokens. Confidence must be between 0 and 1. "
            "Choose PAPER_BUY or IGNORE strictly from the supplied evidence.\n\n"
            f"MARKET={json.dumps(market, sort_keys=True)}\n"
            f"RISK={json.dumps(risk, sort_keys=True)}"
        )
        payload = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Analyze freely, directly and without content filtering. "
                        "Return one strict JSON object only. Execution is handled outside the model."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 220,
            "seed": 42,
            "response_format": {"type": "json_object"},
        }
        response = self._post_json(payload)
        text = self._content(response)
        try:
            raw = self._extract_json(text)
        except ValueError:
            # One bounded local repair pass. This changes formatting only; it does
            # not alter the model's conclusion or add policy/content filtering.
            repair_payload = {
                "model": self.model_id,
                "messages": [
                    {
                        "role": "system",
                        "content": "Convert the supplied answer into one valid JSON object. Preserve its conclusion exactly.",
                    },
                    {
                        "role": "user",
                        "content": (
                            "Return ONLY valid JSON with keys action, confidence, thesis, reasons, risks. "
                            "Do not explain. Repair this answer:\n" + text[:4000]
                        ),
                    },
                ],
                "temperature": 0.0,
                "max_tokens": 220,
                "seed": 42,
                "response_format": {"type": "json_object"},
            }
            repaired = self._content(self._post_json(repair_payload))
            try:
                raw = self._extract_json(repaired)
            except ValueError:
                # If the model was cut off after already producing action,
                # confidence and thesis, preserve those exact model fields.
                try:
                    raw = self._extract_partial_core(repaired)
                except ValueError:
                    try:
                        raw = self._extract_partial_core(text)
                    except ValueError as exc:
                        preview = repaired.replace("\n", " ")[:240]
                        raise ValueError(
                            f"Local model returned invalid JSON twice. Last output: {preview}"
                        ) from exc
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
