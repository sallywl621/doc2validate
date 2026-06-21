# Slide 10 Executable Validation Package

This package contains generated validation scripts for the Slide 10 experiment.

It does not include raw dataset artifacts.

## Contents

- runtime/validation_runtime.py
  Shared loader and profiling runtime.

- specs/
  One JSON validation specification per validation-ready logical file.

- generated_validators/
  One executable Python validator per validation-ready logical file.

- results/
  Execution manifests and profile signatures produced during the experiment.

- run_all_validators.py
  Convenience runner for re-executing all validators.

## Re-run

From this directory:

python run_all_validators.py --benchmark-root /path/to/scidata_selected_50_v1 --out-dir rerun_outputs

Each validator expects the original artifact tree to exist under benchmark root.

## What is validated

Each validator:

1. loads the resolved physical file
2. checks automatically matched columns
3. infers column data types
4. computes numeric summaries or string hash signatures

These scripts validate artifact integrity, schema consistency, and documented column availability.
They do not validate scientific correctness.
