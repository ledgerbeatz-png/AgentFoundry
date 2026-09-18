# AgentFoundry Trading Packs

AgentFoundry treats trading as an installable capability, not as the identity of the core product.

## Product boundary

The core application owns local-model setup, llama.cpp runtime management, hardware-aware tuning, benchmarks, Hermes orchestration, pack discovery and pack lifecycle. Trading packs own market-specific ingestion, deterministic risk rules, AI prompts, paper execution and outcome tracking.

## First pack: Solana Research

The first built-in manifest is `trading.solana-research`. Version 0.1 is deliberately paper-only.

Data flow:

```text
Solana/Pump.fun feed
        |
        v
Deterministic fast filter
        |
        +---- rejected -> audit log
        |
        v
Local Qwen analysis
   +----+----+
   |         |
 RISK       ALPHA
   +----+----+
        |
        v
Python validator
        |
        v
Paper broker -> outcomes -> evaluation
```

Hard risk gates are code, not prompts. An LLM may explain a rejection but cannot override a deterministic rejection. The default policy rejects unlocked liquidity, active mint authority, active freeze authority, liquidity below $10,000, top-10 concentration above 60%, or developer holdings above 12%. These are initial research thresholds and must be evaluated empirically before they are treated as useful strategy parameters.

## Reuse plan

- `hermes-solana-autonomous-trader`: candidate discovery and Solana research components.
- `solana-sniper-dashboard`: control-plane and latency-observability ideas.
- `polymarket-btc5m-lab`: reproducible event capture, replay and paper-broker methodology.
- `Hermes-trading-bot` / Clodds: optional adapters and market/risk tooling rather than the core runtime.
- ASTRAFLY: later offline strategy evolution using recorded outcomes; never the live safety authority.

## Pack contract roadmap

v0.1 establishes manifests, registry and deterministic risk primitives. Next milestones add lifecycle hooks, local OpenAI-compatible inference adapters, two-agent parallel analysis, paper broker storage, outcome snapshots, UI pack management and benchmark-driven concurrency selection.
