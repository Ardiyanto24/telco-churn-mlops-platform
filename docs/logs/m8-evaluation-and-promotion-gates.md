# M8 Evaluation and Promotion Gates Log

## Context dan assumptions

- Scope M8 adalah evaluasi offline terhadap bundle M3/M6 dan registry M7; tidak
  ada deployment atau klaim performa production.
- Kandidat dievaluasi pada test split M6 yang direkonstruksi dari `training_run.json`.
- Tidak adanya champion kompatibel menghasilkan `not_comparable`, bukan lolos
  otomatis; approval awal tetap eksplisit.

## Plan dan actions

- Menambahkan policy versioned `configs/evaluation/m8-gates-v1.json` dan ADR-0004.
- Menambahkan gate metric/probability, pipeline evaluasi, report JSON, model card,
  dan approval artifact pada `src/telco_churn/evaluation/`.
- Menambahkan CLI `scripts/evaluate_candidate.py` dan `scripts/approve_candidate.py`.
- Menambahkan runtime verifikasi `docker/m8-runtime.Dockerfile` dan test M8 ke
  kategori `model`.

## Evidence dan findings

- Unit dan integration-fixture M8 memverifikasi absolute gate, probability NaN,
  regression terhadap champion, rekonstruksi split, output immutable, dan
  approval digest sebelum alias champion dapat ditetapkan.
- Image `telco-churn-m8-runtime:local` berhasil dibangun dari runtime M7 yang
  sudah locked.

## Errors dan handling

- Percobaan awal suite langsung dengan `python -m unittest` gagal mengimpor
  package karena environment container tidak menyetel `PYTHONPATH=/workspace/src`.
  Pengulangan dengan environment standar runner lulus; ini bukan kegagalan gate.

## Decisions dan deviations

- Konfigurasi M8 menerapkan keputusan ADR-0004: AP sebagai metric utama,
  ECE equal-frequency, batas latency p95, dan alias `champion` hanya setelah
  artifact approval.
- Bootstrap CI dicatat sebagai evidence analitis berikutnya, bukan syarat hard
  blocker v1, agar gate deterministik tetap dapat direproduksi offline.

## Risks, limitations, follow-up

- Angka gate v1 berlaku untuk data telco versioned saat ini dan perlu dikalibrasi
  ulang jika definisi churn, populasi, atau objective berubah.
- M8 tidak mengukur performa production atau melakukan deployment; M9-M12
  menangani runtime, CI, dan telemetry.

## Trace references

- ADR: `docs/decisions/0004-m8-evaluation-and-promotion-gate-policy.md`
- Gate config: `evaluation-gates/v1`
- Data origin report: `offline_test`
