# Training Data Contract v1

`telco-churn-training/v1` is the canonical raw-training schema for M5. It uses
the original Telco column names so the M6 pipeline can reuse the stable
preprocessor without an implicit field-name translation.

## Contract

- All 20 input fields plus `Churn` are required; unknown columns are rejected.
- `id` is unique; `SeniorCitizen` is `0` or `1`; `tenure` is 0--72;
  charges are non-negative.
- Categorical fields are limited to the Telco domains encoded in
  `telco_churn.data_contract`.
- `PhoneService=No` requires `MultipleLines=No phone service`.
- `InternetService=No` requires each internet add-on field to be
  `No internet service`.
- A blank `TotalCharges` is accepted only for a zero-tenure record, matching
  the known source-dataset convention.

The validator uses Pandera `DataFrameSchema` with strict columns, coercion, and
per-column checks. Pandera documents this schema pattern and its required,
nullable, and coercion behavior at
https://pandera.readthedocs.io/en/stable/dataframe_schemas.html.

## Data lineage and DVC

Raw and validated datasets are ignored by Git. Store raw data at
`data/raw/telco_churn.csv`, configure a DVC remote outside of this repository,
then use `dvc repro validate_data`. The stage in `dvc.yaml` records source,
validator, and output dependencies. DVC documents this workflow as `dvc add`
for data tracking and `dvc.yaml` for reproducible pipeline stages:
https://dvc.org/doc/command-reference/.

The output manifest records schema version, source name, SHA-256, dimensions,
and Git revision. M6 must load data only through `load_verified_dataset`, which
checks the manifest checksum and reruns the contract validation.

## Compatibility

Breaking field/domain changes require `telco-churn-training/v2` (or later), a
migration note, and a new validation schema. Additive fields are also rejected
by v1 to prevent accidental leakage; introduce them only in a new version.
