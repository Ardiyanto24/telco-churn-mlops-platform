# Test Commands and Rules

All test names start with `test_` and must be deterministic, isolated, and free of secrets. Shared temporary files use `tests.support.temporary_workspace`; production database, artifact storage, and customer payloads are prohibited.

| Category | Command | Purpose |
|---|---|---|
| Fast/unit | `py scripts/run_tests.py fast --coverage-dir coverage/fast` | Dependency-free settings and lock checks. |
| API | `docker run ... scripts/run_tests.py api` | Contract/API checks in the locked runtime. |
| Model | `docker run ... scripts/run_tests.py model` | Preprocessing, artifact, and M5 data-contract checks. |
| Integration | `py scripts/run_tests.py integration` | Docker baseline and API boundary checks. |
| All | `py scripts/run_tests.py all` | Full suite; run in CI after M10 is added. |

The `coverage/` directory is a generated artifact and is not committed. Intentional failure is verified with `py -m unittest tests.does_not_exist`, which must return non-zero.

M6 training and candidate-artifact checks are included in the model suite. The
complete candidate can be generated non-interactively in the locked runtime:

```powershell
docker run --rm --mount "type=bind,source=$((Get-Location).Path),target=/workspace" `
  --workdir /workspace -e PYTHONPATH=/workspace/src `
  telco-churn-m6-runtime:local python scripts/train_model.py
```

M7 registry checks are also included in the model suite and require the M7 image:

```powershell
docker run --rm --mount "type=bind,source=$((Get-Location).Path),target=/workspace,readonly" `
  --workdir /workspace -e PYTHONPATH=/workspace/src `
  --entrypoint python telco-churn-m7-runtime:local scripts/run_tests.py model
```
