import json

from agentfoundry.trading.analysis import LocalQwenAnalyst
from agentfoundry.trading.market_data import MarketCandidate
from agentfoundry.trading.risk import RiskDecision
from agentfoundry.trading.risk_enrichment import CandidateRiskAssessment, RiskEvidence


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def passed_assessment():
    candidate = MarketCandidate(
        token_address="A" * 32,
        symbol="CAT",
        name="Labor Cat",
        pair_address="PAIR",
        dex_id="raydium",
        price_usd=0.01,
        liquidity_usd=50000,
        market_cap_usd=150000,
        fdv_usd=150000,
        volume_24h_usd=90000,
        buys_5m=25,
        sells_5m=8,
        pair_created_at=1,
        url="",
    )
    evidence = RiskEvidence(
        top10_holder_pct=30,
        developer_holding_pct=2,
        liquidity_locked=True,
        mint_authority_enabled=False,
        freeze_authority_enabled=False,
        rugged=False,
        score=100,
        missing=(),
        warnings=(),
    )
    return CandidateRiskAssessment(candidate, "PASS", RiskDecision(True, ()), evidence)


def test_local_qwen_analyst_parses_strict_json():
    body = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "action": "PAPER_BUY",
                    "confidence": 0.72,
                    "thesis": "Strong paper setup with contained residual risk.",
                    "reasons": ["buy pressure"],
                    "risks": ["small cap"],
                })
            }
        }]
    }
    analyst = LocalQwenAnalyst(
        "http://127.0.0.1:8080/v1",
        "qwen",
        opener=lambda *_args, **_kwargs: FakeResponse(body),
    )

    result = analyst.analyze(passed_assessment())

    assert result.action == "PAPER_BUY"
    assert result.confidence == 0.72


def test_blocked_candidate_never_reaches_qwen():
    assessment = passed_assessment()
    blocked = CandidateRiskAssessment(
        assessment.candidate,
        "BLOCK",
        RiskDecision(False, ("mint_authority_enabled",)),
        assessment.evidence,
    )
    analyst = LocalQwenAnalyst("http://127.0.0.1:8080/v1", "qwen")

    try:
        analyst.analyze(blocked)
    except ValueError as exc:
        assert "passed deterministic risk gates" in str(exc)
    else:
        raise AssertionError("blocked candidate should not reach local AI")


def test_extract_json_accepts_wrapped_object():
    text = 'analysis follows:\n\n```json\n{"action":"IGNORE","confidence":0.4,"thesis":"weak","reasons":[],"risks":[]}\n```\nfinished'

    value = LocalQwenAnalyst._extract_json(text)

    assert value["action"] == "IGNORE"


def test_local_qwen_repairs_invalid_json_once():
    payloads = [
        {
            "choices": [{
                "message": {
                    "content": "action=PAPER_BUY confidence=.7 thesis=momentum"
                }
            }]
        },
        {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "action": "PAPER_BUY",
                        "confidence": 0.7,
                        "thesis": "Momentum remains favorable.",
                        "reasons": ["buy pressure"],
                        "risks": ["small cap"],
                    })
                }
            }]
        },
    ]
    calls = []

    def opener(request, **_kwargs):
        calls.append(json.loads(request.data.decode("utf-8")))
        return FakeResponse(payloads[len(calls) - 1])

    analyst = LocalQwenAnalyst("http://127.0.0.1:8080/v1", "qwen", opener=opener)

    result = analyst.analyze(passed_assessment())

    assert result.action == "PAPER_BUY"
    assert len(calls) == 2
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert "Preserve its conclusion exactly" in calls[1]["messages"][0]["content"]


def test_partial_core_salvages_truncated_json():
    text = (
        '{"action":"PAPER_BUY","confidence":0.75,'
        '"thesis":"SOURCE shows positive market momentum.",'
        '"reasons":["buy pressure", "liquidity is'
    )

    value = LocalQwenAnalyst._extract_partial_core(text)

    assert value["action"] == "PAPER_BUY"
    assert value["confidence"] == 0.75
    assert value["thesis"] == "SOURCE shows positive market momentum."
    assert value["reasons"] == []
    assert value["_recovered_from_truncated_output"] is True
