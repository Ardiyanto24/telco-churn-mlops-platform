# M10 Continuous Integration

`.github/workflows/ci.yml` runs on pull requests to `main`, pushes to `main`,
and manual dispatch. Required jobs are `fast`, `model`, `container-smoke`, and
`security`; branch protection should require the aggregate `required-checks` job
plus one approving review.

The workflow uses only `contents: read`, never downloads remote model/data, and
never pushes an image. It builds `telco-churn-api:<commit-sha>`, generates a
synthetic verified bundle, and proves Compose readiness plus an invalid-bundle
failure. Logs/coverage and security evidence are retained for 14 days.

If branch-protection administration is unavailable, apply the policy manually:
require `required-checks`, one approval, and dismissal of stale approvals.
