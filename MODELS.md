# Model Map — SDD & Review Agents

Which AI model answers each agent role. Source of truth: `agent.*.model` in
`~/.config/opencode/opencode.json` (global opencode config). This file is the
human-readable mirror; if they drift, the config wins.

## Agent → Model

| Agent | Model | Role |
|---|---|---|
| `gentle-orchestrator` | `opencode/muse-spark-1.2-contributor-free` | Orchestrator — coordinates sub-agents, never executes |
| `sdd-explore` | `opencode/hy3-free` | Codebase investigation & requirement exploration |
| `sdd-propose` | `opencode/big-pickle` | Change proposals (intent, scope, approach) |
| `sdd-spec` | `opencode/big-pickle` | Delta specifications from proposals |
| `sdd-design` | `nvidia/nemotron-3-super-120b-a12b` | Technical design & architecture |
| `sdd-tasks` | `nvidia/nemotron-3-nano-30b-a3b` | Task breakdown from specs + design |
| `sdd-apply` | `opencode/ling-3.0-flash-fin-free` | Implementation of tasks |
| `sdd-verify` | `nvidia/nemotron-3-super-120b-a12b` | Independent verification against specs |
| `sdd-archive` | `opencode/mimo-v2.5-free` | Archive & final-state report |
| `sdd-onboard` | `opencode/big-pickle` | Guided SDD onboarding walkthrough |
| `general` | `opencode/ling-3.0-flash-fin-free` | General implementation & command execution |
| `explore` | *(session default)* | Freeform exploration fallback |
| `jd-fix-agent` | `opencode/ling-3.0-flash-fin-free` | Surgical fix agent (judgment-day protocol) |
| `jd-judge-a` | `nvidia/nemotron-3-super-120b-a12b` | Blind adversarial judge A |
| `jd-judge-b` | `nvidia/nemotron-3-super-120b-a12b` | Blind adversarial judge B |
| `review-risk` (R1) | `nvidia/nemotron-3-super-120b-a12b` | Security, privilege, data exposure |
| `review-readability` (R2) | `nvidia/nemotron-3-super-120b-a12b` | Naming, complexity, maintainability |
| `review-reliability` (R3) | `nvidia/nemotron-3-super-120b-a12b` | Tests, behavior, contracts, regressions |
| `review-resilience` (R4) | `nvidia/nemotron-3-super-120b-a12b` | Fallbacks, retry, observability, SLO |
| `review-refuter` | `nvidia/nemotron-3-nano-30b-a3b` | Batched refutation of BLOCKER/CRITICAL findings |
| `review-validator` | `nvidia/nemotron-3-nano-30b-a3b` | Read-only fix validator (Git against frozen trees) |

## Cost & availability notes

- **`opencode/*-free` models are promotional** (Zen): free for a limited time,
  then the ID stops responding (no silent billing). The contributor/free tiers
  may retain data to improve the product — do not route confidential business
  data through them.
- **`opencode/ling-3.0-flash-fin-free`** is the *finance* variant of Ling 3.0
  Flash, free promo runs until **2026-09-25**. It has solid tool-calling; after
  that date, swap `sdd-apply` / `general` / `jd-fix-agent` to a permanent model
  (e.g. `opencode/big-pickle` or a paid code model like `opencode/kimi-k2.7-code`).
- **`nvidia/nemotron-*`** run through the NVIDIA-backed provider already
  configured in this setup. `nemotron-3-super-120b-a12b` is the reasoning
  workhorse (design, verify, judges, R-lenses); `nemotron-3-nano-30b-a3b` is
  the cheap refutation/validation tier.

> Restart opencode after changing `opencode.json` — config is loaded once at
> startup and is not hot-reloaded.