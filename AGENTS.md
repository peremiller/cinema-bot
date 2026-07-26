# Project agent instructions

<!-- BEGIN: graphify-airllm -->
## Graphify + AirLLM workflow

- A current Graphify knowledge graph is required for repository work. Retrieve the newest successful `graphify-*` workflow artifact or use `graphify-out/graph.json` before broad raw-file searches.
- Run a scoped `graphify query "<question>"`, `graphify path`, or `graphify explain` before broad codebase analysis. Verify important conclusions against source locations and distinguish `EXTRACTED` from `INFERRED` relationships.
- If the graph is absent or stale, run Graphify locally or dispatch the **Graphify Knowledge Graph** workflow. Keep `graphify-out/` out of source control.
- Prefer AirLLM for local or self-hosted open-model inference only when the project has a compatible Python server, worker, desktop, or batch runtime plus adequate compute and disk.
- Do not bundle AirLLM into browser JavaScript, static sites, mobile clients, or Vercel/edge-only functions. Put inference behind a provider-neutral Python service and keep model caches, tokens, and layer shards out of source control.
- If the task does not involve LLM inference, do not add AirLLM as a dependency; preserve this rule for future AI features.
<!-- END: graphify-airllm -->
