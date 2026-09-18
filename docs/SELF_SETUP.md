# Self Setup

AgentFoundry's product goal is to turn local AI setup into a guided, measurable workflow rather than a collection of command-line recipes.

## Pipeline

1. Detect OS, CPU, RAM, GPU and VRAM locally.
2. Recommend a model size/quantization class.
3. Inspect an existing GGUF if the user already has one.
4. Recommend conservative llama.cpp context, GPU offload and KV-cache settings.
5. Start a temporary benchmark runtime.
6. Measure inference performance.
7. Measure concurrency candidates (normally 1, 2 and 4).
8. Select the throughput sweet spot subject to a latency ceiling.
9. Save the resulting runtime profile.
10. Enable compatible capability packs.

Self Setup does not silently enable wallet signing or live trading. Trading packs remain paper-only unless a future product milestone introduces a separate, explicit execution design.

## Concurrency selection

The selector does not simply choose the highest raw throughput. It rejects candidates whose average latency exceeds 1.5x the single-request baseline, then chooses the best throughput among the remaining candidates. This captures the behavior observed on the current Qwen test machine: two concurrent requests materially improved throughput, while four added almost no throughput and roughly doubled latency.

## Model selection

v0.1 recommends a model *class* rather than automatically downloading an arbitrary model. This keeps provenance and licensing review separate from hardware tuning. Initial classes are conservative Q4-class 3B, 8B and 14B profiles based on available system memory/VRAM. A later signed catalog can map those classes to reviewed model artifacts.
