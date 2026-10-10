# Decision log

One line per decision: what, rejected alternatives, why. Newest at the bottom. Details live in `docs/superpowers/specs/2026-10-10-compass-backend-design.md`.

| # | Date (ET) | Decision | Rejected | Why |
|---|---|---|---|---|
| 1 | 10-10 19:30 | Region us-west-2 | us-east-1 | Session creds default there; every model we use is enabled there |
| 2 | 10-10 19:30 | Grok 4.7 for offline wording + KB tagging; Claude Haiku 4.5 for inline classify/moderate/barrier mapping | Grok inline; Claude for everything | Measured: Grok 4.7 7.7-12 s per sentence (always reasons), Haiku 4.5 ~1.0 s. Inline must stay under 1.5 s p95. Claude is not fully disabled: Haiku 4.5, Sonnet 4.5/4.6/5 work; 5.5 family and Opus are denied |
| 3 | 10-10 19:30 | Stage-2 crisis classifier = Haiku 4.5 ∥ gpt-oss-safeguard-20b, most severe label wins, failure → `concern` | Single model | Two independent labellers, 0.4-1.0 s in parallel; fail-safe bias |
| 4 | 10-10 19:30 | Self-harm methods enforced as a Guardrails denied topic + code lexicon | Relying on a content filter | Bedrock Guardrails has no self-harm content category |
| 5 | 10-10 19:30 | Grounding check on all generated text (no time/number/place/weekday absent from facts) | Prompt-only "don't add facts" | Sonnet invented "classes don't start until 2pm" in a probe |
| 6 | 10-10 19:30 | ECS Fargate + ALB + CloudFront (default HTTPS cert) | App Runner; Lambda + API GW; Lightsail | App Runner is denied in this account. Fargate keeps one warm task (no cold starts), supports streaming for P2 voice, redeploys with one command |
| 7 | 10-10 19:30 | RDS PostgreSQL 16 db.t4g.small in default VPC, private, SG from ECS only | Aurora Serverless v2 | Cheapest predictable option; pgvector supported |
| 8 | 10-10 19:30 | FastAPI + Pydantic v2 + psycopg 3 + plain SQL | ORM; Node | OpenAPI generated from the same models used by fixtures; bundle is Python |
| 9 | 10-10 19:30 | Memory: self-managed typed facts in Postgres, rule-written, bounded (25), `(kind,key)` upsert, every fact citable and deletable | AgentCore Memory, mem0 runtime, Letta, Honcho | We have no conversations to extract from; deletion must be provable; Honcho is AGPL. Borrowed: Hermes bounded store, OpenClaw supersede-in-place, mem0 ADD/UPDATE/DELETE/NONE semantics |
| 10 | 10-10 19:30 | No agent loop anywhere in P0/P1. Ask box and staff ask = fixed pipelines (check → retrieve/generate SQL → validate → one call) | Strands, LangGraph, Claude Agent SDK loops | Predictability, latency, debuggability at 3 a.m.; scope control. Strands is the pick if a real multi-tool loop is ever needed (Apache-2.0, Bedrock-native) |
| 11 | 10-10 19:30 | Ranking learns via Beta-Binomial posterior mean by cohort; Thompson sampling behind a flag, seeded per (student, week) | Unseeded bandit; learned-to-rank | Deterministic demo, one-sentence explanation ("rated 4+ by 71% of 41 Newark commuters") |
| 12 | 10-10 19:30 | Stage-1 lexicon alone must catch 100% of the crisis test set | Classifier-dependent pass | Test must pass with Bedrock blocked |
| 13 | 10-10 19:30 | Andre's week-2 basketball event is rung 3 (persona file said 2) | Keep rung 2 | Brief requires "next week's pick is the next rung" after a 4 rating |
| 14 | 10-10 19:30 | Wording never inline: cache hit or template now, AI generation queued | Inline generation with timeout | Guarantees latency regardless of Bedrock |
| 15 | 10-10 19:50 | Ingest Scarlet Sync public events as a snapshot source with attribution; collapse LibCal room slots to one place per library; drop away games | Live proxy; ignore it | Real recreation/intramural/club supply and real Newark (Dana) and Camden (Robeson) study spaces; snapshot avoids a demo-time dependency |
| 16 | 10-10 19:50 | Staff endpoints use a separate read-only DB role that can only read suppressed views/functions | UI-only suppression | Brief requires suppression in the database layer |
