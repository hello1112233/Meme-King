# Meme King Execution Plan

This is a design document for a future isolated execution subsystem. It does not implement live trading, transaction signing, wallet loading, swaps, or RPC submission.

## Execution Boundary

Meme King should never let ingestion or replay cognition directly execute. The only acceptable future design is a separate executor process with a narrow message contract.

```text
Replay cognition -> candidate_intents table -> approval gate -> execution_outbox
                                                              |
                                                              v
                                                   isolated Rust executor
```

## Non-Breaking Trade Execution

Non-breaking execution means the executor can fail without breaking:

- source ingestion
- replay artifact generation
- dashboard rendering
- data-source health monitoring
- historical scorecards

Executor failures are normal outbox state transitions, not process-wide exceptions.

Outbox states:

- `created`
- `approved`
- `leased`
- `preflight_failed`
- `submitted`
- `confirmed`
- `expired`
- `cancelled`
- `failed_retryable`
- `failed_terminal`

## Rust Executor Sidecar

Recommended future executor language: Rust.

Reasons:

- lower steady-state memory than a full Python trading stack
- explicit state machines and typed request/response contracts
- easy static binary distribution for macOS arm64
- separate crash domain from Python ingestion/cognition
- strong fit for low-latency network fanout and timeout control

Executor runtime:

- `tokio` async runtime
- SQLite outbox lease reader or Unix-domain socket API
- bounded internal queues
- per-token idempotency keys
- RPC client pool with health scoring
- confirmation watchdog
- deterministic executor journal

## Minimal Message Contract

The future executor should accept only fully validated, immutable intents:

```json
{
  "intent_id": "sha256:...",
  "created_at": "2026-05-25T00:00:00Z",
  "mode": "paper|dry_run|live",
  "token_mint": "...",
  "side": "buy|sell",
  "max_spend_lamports": 0,
  "slippage_bps": 0,
  "ttl_ms": 0,
  "safety_hash": "sha256:...",
  "source_event_ids": ["sha256:..."]
}
```

Until a future live phase is explicitly approved, `mode` must be `paper` or `dry_run`.

## Safety Gates Before Executor Lease

- global `EXECUTION_ENABLED=0` by default
- manual approval marker required
- source provenance present
- candidate was produced by replay-safe cognition from persisted events
- token mint validated
- duplicate token cooldown checked
- max outstanding intents checked
- daily loss/spend limits checked
- source health acceptable
- RPC health acceptable
- dry-run simulation artifact present
- idempotency key not previously confirmed

## Async Retry Queues

Use two queues:

1. `enrichment_queue`: DexScreener/GMGN/Helius/RPC reads, retryable without execution risk.
2. `execution_queue`: future executor-only queue, disabled by default.

Queue policy:

- bounded queue length
- per-source concurrency caps
- exponential backoff with jitter
- TTL expiration
- idempotent retries
- poison-message quarantine after terminal failures
- deterministic attempt records in SQLite

## RPC Failover Design

Future executor should not rely on one RPC path. It should maintain endpoint health:

- primary Solana RPC
- Helius Sender or staked RPC path
- Jito block engine path
- backup standard RPC

Health dimensions:

- latest slot lag
- recent send latency
- recent confirmation latency
- HTTP error rate
- blockhash freshness
- simulation reliability
- rate-limit response rate

The executor should fetch blockhashes and confirm transactions using consistent commitment settings and reject stale blockhashes. Solana's official confirmation guidance emphasizes healthy RPC nodes, avoiding stale blockhash reuse, and using appropriate commitment/preflight settings.

## Transaction Confirmation Reliability

Future confirmation state machine:

1. fetch latest blockhash and `lastValidBlockHeight`
2. build transaction
3. simulate/preflight unless using a consciously documented low-latency skip path
4. submit through selected endpoint set
5. poll signature status until confirmed, failed, or blockheight expired
6. if expired and no landed signature exists, mark retryable only if intent TTL remains
7. never double-submit a new transaction without idempotency and position-state reconciliation

Jito bundles can provide all-or-nothing semantics for bundled transactions, but receiving a bundle ID does not guarantee landing. Any future Jito path must track bundle status separately.

## Graduation Token Timing

Architecture-only timing model:

- Pre-graduation tokens: PumpPortal/PumpDev events and bonding-curve state are primary signals; DEX liquidity may be absent.
- Graduation boundary: liquidity migration and route availability are unstable; executor must treat this as a separate state, not a normal buy path.
- Post-graduation tokens: DEX route, pool liquidity, slippage, price impact, and confirmation reliability become primary.

No live sniper logic is implemented here. A future implementation must benchmark observed historical latency from source event to route availability before choosing execution timing.

## Pre-Graduation Sniper Logic Boundary

Future pre-graduation logic should be modeled as:

```text
source event -> curve state -> quality gates -> dry-run quote/simulation -> outbox intent
```

It must not bypass:

- source provenance
- deterministic event persistence
- duplicate/cooldown gates
- max exposure limits
- simulation or documented preflight alternative
- executor isolation

## Post-Graduation Liquidity Handling

Future post-graduation logic should be modeled as:

```text
graduation detected -> liquidity event persisted -> DEX route check -> slippage/impact budget -> outbox intent
```

Handling requirements:

- separate route availability from liquidity quality
- detect thin/unstable pools
- require bounded slippage and max price impact
- record route source and quote age
- re-check route immediately before signing

## Benchmarking Plan

Before live execution:

- Measure source-to-event-log latency.
- Measure enrichment queue latency under burst.
- Replay old graduation candidates and estimate missed timing windows.
- Benchmark Rust sidecar cold start and steady-state memory.
- Benchmark RPC endpoint latency and confirmation reliability.
- Benchmark queue retry behavior under simulated endpoint failures.
- Verify executor crash does not corrupt ingestion/cognition state.

## Hard Requirements For Future Implementation

- Separate repository module or binary for executor.
- No private keys in Python ingestion/cognition.
- No execution API reachable from replay tests.
- Dry-run default.
- Manual enablement and manual approval.
- Structured execution journal.
- Kill switch that immediately stops leasing new intents.
- Integration tests using fake RPC only before any real RPC path is enabled.

