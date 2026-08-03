# M16 Engineering Log — Delayed-label performance monitoring

## Context and assumptions

- M16 will establish the delayed-label monitoring framework before the user
  supplies the external delayed-label data package.
- No available artifact proves the pending source's churn definition, join
  identifier, arrival pattern, or label-maturity interval.
- Synthetic or replayed evidence must never be represented as production
  performance.

## Plan and actions

- Read the M16 plan and target architecture sections.
- Record the durable M16 policy and its rejected alternatives in ADR-0012.
- Defer implementation values that require source-data validation while keeping
  them versioned and configurable.

## Evidence and findings

- The M16 plan requires matured labels, idempotent prediction-label joins,
  coverage reporting, rolling evaluation, data-origin labels, and explicit
  `not_available`/`insufficient_data` behavior.
- M12 already defines pseudonymous `entity_key` and immutable release lineage,
  which are the approved starting point for the protected join contract.

## Errors and handling

- No delayed-label data is available yet, so real join compatibility,
  production coverage, and maturity horizon cannot be verified. This is
  recorded as a scope constraint rather than inferred from existing datasets.

## Decisions and deviations

- ADR-0012 adopts twenty production-candidate decisions. Its 90-day maturity
  horizon and 80% coverage threshold are explicitly candidate configuration,
  pending validation against the incoming data package.

## Risks, limitations, and follow-up

- Do not label any M16 result `production` until the authoritative source,
  identifier mapping, and churn definition have been reviewed.
- When the package arrives, inspect its schema and update/supersede the ADR if
  the source requires different join or maturity semantics.

## Trace references

- ADR: `docs/decisions/0012-m16-delayed-label-performance-monitoring-policy.md`
- Upstream contracts: ADR-0008 and ADR-0011.
- Plan: `MLOPS_IMPLEMENTATION_PLAN.md`, M16.
