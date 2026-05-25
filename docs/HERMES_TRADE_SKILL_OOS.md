# Hermes Trade Skill — Out-of-Sample Validation

## Why 100% Historical Winrate Can Be Overfit

A 100% winrate on historical paper data is a red flag, not a green light. It can arise from:

- **Selection bias** — the skill was trained on the same data it was evaluated on.
- **Channel over-concentration** — nearly all winning trades come from one source.
- **Duplicate-token inflation** — the same token is counted multiple times.
- **Single-day data** — all signals came from one session, so edge may not generalize.
- **Look-ahead leakage** — training rows were built from future-known channel performance.
- **Deterministic cherry-picking** — grid search over thousands of rule combinations guarantees a "perfect" subset on small data.

OOS validation exists to catch these traps before any capital is risked.

---

## OOS Tests

### 1. Time-Split Validation
Chronologically sort accepted setups and hold out the last 30% as a pseudo-future test set. If the skill is overfit to a lucky recent window, the test winrate will drop sharply.

**Threshold:** test winrate ≥ 0.80

### 2. Channel Holdout Validation
Measure what fraction of accepted setups come from the single largest channel. If one channel dominates, the skill is a channel bet, not a robust rule.

**Threshold:** no single channel > 95% of accepted setups

### 3. Shuffled-Order Replay Validation
Deterministically shuffle accepted setups and re-apply the skill rules. Because cooldown and duplicate windows are set to 0 in the current rule set, the accepted count and winrate must remain identical. A mismatch reveals hidden order-dependent state.

**Threshold:** replay accepted count equals original count

### 4. Duplicate-Token Collapse Validation
Group accepted setups by token symbol (or mint address) and keep only the first occurrence. If the winrate collapses when duplicates are removed, the edge was artificially inflated by repeatedly counting the same token.

**Threshold:** collapsed winrate ≥ 0.80

### 5. Minimum Unique Token Count
A skill evaluated on fewer than 50 unique tokens has insufficient sample diversity to claim generalization.

**Threshold:** unique tokens ≥ 50

### 6. Minimum Day Coverage
All signals from a single calendar day may reflect a transient market regime. The full normalized source should span multiple days.

**Threshold:** day coverage ≥ 7

---

## Gate to Micro Live Trading

Before micro live testing (e.g., $5–$10 positions) ALL of the following must pass:

| Check | Threshold |
|-------|-----------|
| Accepted setups | ≥ 100 |
| Unique tokens | ≥ 50 |
| Day coverage | ≥ 7 |
| Time-split winrate | ≥ 0.80 |
| Largest channel share | ≤ 0.95 |
| Duplicate-collapse winrate | ≥ 0.80 |
| Shuffled-replay consistency | exact match |

If any check fails, the skill stays in paper-only mode. Do not increase position size until OOS passes on a refreshed, larger dataset.

---

## Artifacts

- **Input:** `artifacts/hermes_trade_skill/skill_rules.json`
- **Input:** `artifacts/hermes_trade_skill/accepted_setups.jsonl`
- **Input:** `artifacts/normalized_calls.jsonl`
- **Output:** `artifacts/hermes_trade_skill/oos_validation.json`

Run the validator:

```bash
bash scripts/validate_hermes_trade_skill_oos.sh
```
