# Carrier Voice Agent

> Status: MVP in progress. See [Where it breaks](#where-it-breaks) for honest limits.

## The argument

Every agentic voice demo in telecom care apologizes for an outage it cannot see. A care agent that answers "I understand you're frustrated, let me help you troubleshoot your device" while the caller's tower is in maintenance is not being helpful — it is being wrong at scale. The network is the product. A care response that ignores the state of the network is the wrong response.

This repo is an argument in code: the reasoning loop must consult live network health before it speaks. Cell site status is a first-class input to the model's tool set, not an afterthought handed off to a separate ticket queue. Everything else here — telephony, transcription, TTS, translation — is plumbing around that one commitment.

## What it does

```
  PSTN call
     │
     ▼
┌────────────┐    audio    ┌──────────────┐   text   ┌──────────────┐
│  Amazon    │────────────▶│  Transcribe  │─────────▶│   Bedrock    │
│  Connect   │             │  (streaming) │          │ (tool-using) │
└────────────┘             └──────────────┘          └──────┬───────┘
     ▲                                                      │
     │  audio                                               │ tool calls
     │                                                      ▼
┌────────────┐   text      ┌──────────────┐        ┌─────────────────┐
│   Polly    │◀────────────│  Validator   │◀──────▶│   Tool layer    │
│  (speech)  │             │  (Python,    │        │ site health,    │
└────────────┘             │  deterministic)       │ account, outage,│
                           └──────────────┘        │ appointment,    │
                                                   │ escalate        │
                                                   └─────────────────┘
```

Cascaded path shown. Speech-to-speech path replaces Transcribe + Bedrock + Polly with a single audio-in / audio-out model. Both share the same tool layer and validator.

## The two paths

**Path A — Cascaded.** Connect → Transcribe streaming → Bedrock with tool use → Polly. Real-time translation in the pipeline for non-English callers.

**Path B — Speech-to-speech.** Connect → speech-to-speech model → Polly (or model-native audio out). No text intermediate.

Both measured on the same test set:

| Metric              | Path A (cascaded) | Path B (S2S) |
|---------------------|-------------------|--------------|
| p50 turn latency    | TBD               | TBD          |
| p95 turn latency    | TBD               | TBD          |
| Cost per 3-min call | TBD               | TBD          |
| WER on accented EN  | TBD               | TBD          |
| Tool-call accuracy  | TBD               | TBD          |

Numbers land in this table when the MVP is running. The comparison is the point of the repo. A Principal builds one and knows why, not both and shrugs.

## Tools the agent can call

- `get_site_health(cell_site_id)` — `degraded | healthy | maintenance`
- `get_account_status(account_id)` — plan, balance
- `lookup_outage(zip_code)` — active incidents
- `book_appointment(account_id, slot)` — write path, gated by validator
- `escalate_to_human(reason)` — routes out on low confidence

Tool schema is fixed. Temperature 0 for tool-calling. Network data is a synthetic simulator (twenty sites, deterministic seed) — the point is the pattern, not the data.

## The validator

Plain Python. Deterministic. Checks every proposed write against policy before commit. Not a model grading another model. Rejections are demonstrable in the UI — a reviewer can watch a write proposal get blocked and see why.

## Where it breaks

- **Latency budget.** Cascaded path adds Transcribe + Bedrock + Polly hops. Sub-second turn latency is not realistic on the cascaded path with tool calls; expect 1.5–3s. S2S should be faster but tool round-trips still cost.
- **Accented speech.** Streaming Transcribe WER climbs on accented English. Cascaded path degrades gracefully (garbled text still triggers escalation); S2S failure modes are less legible.
- **Validator rejections.** When a write is blocked, the agent says so out loud rather than silently swallowing the intent. This is a feature. It also means the caller hears "I can't book that for you" more often than a demo would like.
- **Simulator, not a network.** Site health is synthetic. Real integration is a different project.

## Setup

> This section is intentionally last.

Requires: AWS account with Connect, Bedrock, Transcribe, Polly, Translate enabled. A phone number provisioned in Connect. Node 20 for the frontend, Python 3.11 for the validator and simulator.

```bash
cp .env.example .env  # fill in AWS region, Connect instance, Bedrock model ids
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && npm run dev
```

Set an AWS budget alert at $20 before provisioning Connect. Release the phone number when the demo is done.

## License

MIT. See [LICENSE](LICENSE).
