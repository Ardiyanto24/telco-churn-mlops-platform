# M15 Engineering Log — Statistical monitoring calibration

## Context and assumptions

- M14 results/configuration are experimental. M15 owns the first candidate
  configuration and baseline approval gate.
- The existing M13 artifact remains provisional because it was generated from
  complete validated data despite ADR-0009's training-split policy.

## Plan and actions

- Create deterministic configuration/scenario contracts before selecting a
  production configuration.
- Reconstruct the exact M6 fit split from its versioned seed/fractions and
  require a separate approval record before writing an approved baseline.

## Evidence and findings

- `test_monitoring_baseline.py`, `test_monitoring_engine.py`, and
  `test_monitoring_calibration.py` passed together: 13 tests.
- Candidate config `5c80214e4a245a480e27ad5896ec53169ed53c3cef51d9f088a10b7d740705fa`
  is deterministic and stored under `configs/monitoring/`.

## Decisions and deviations

- ADR-0011 governs calibration. No current baseline is promoted solely from
  synthetic testing or an unreviewed provenance claim.

## Risks, limitations, and follow-up

- The candidate config is not production-approved until backtests and an
  approved training-split baseline are generated.
- Full baseline generation/scoring on the 415,935-row fit split needs a
  long-running batch environment rather than the interactive runtime budget.
