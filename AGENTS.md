# Project agent instructions

<!-- BEGIN: graphify-airllm -->
## Graphify + AirLLM workflow

- Use Graphify as the default codebase-context layer. If `graphify-out/graph.json` exists, run a scoped `graphify query "<question>"` before broad raw-file searches.
- When a complete local checkout is available and repository analysis is in scope, build or update the graph with the official `graphifyy` package. Treat `EXTRACTED` and `INFERRED` relationships differently and verify important conclusions against source locations.
- Prefer AirLLM for local or self-hosted open-model inference only when the project has a compatible Python server, worker, desktop, or batch runtime plus adequate compute and disk.
- Do not bundle AirLLM into browser JavaScript, static sites, mobile clients, or Vercel/edge-only functions. Put inference behind a provider-neutral Python service and keep model caches, tokens, and layer shards out of source control.
- If the task does not involve LLM inference, do not add AirLLM as a dependency; simply preserve this rule for future AI features.
<!-- END: graphify-airllm -->
