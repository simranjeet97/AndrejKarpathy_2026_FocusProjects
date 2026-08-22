# Limitations & Research Integrity

## 1. Limitations
* **Pilot Scale**: 48 local tasks provide a controlled pilot evaluation, not a statistically definitive general benchmark.
* **External Memory vs Parameter Learning**: This prototype tests external state persistence (memory/workflow schema), not parameter/weight update fine-tuning.
* **Subprocess Isolation**: Executed in local temporary directories with subprocess isolation and timeouts. Full containerized sandboxing is recommended for untrusted web environments.

## 2. Research Integrity Commitment
> **No experimental result is reported unless it was produced by actually running the code.**
