# Doc2Validate

Documentation-driven executable dataset validation with schema-centered LLM extraction and Structured Curatability Score (SCS).

This repository contains the code, corpus construction pipeline, schema extraction workflow, execution-based validation tools, and analysis scripts for the paper:

> From Documentation to Executable Dataset Validation: A Schema-Centered LLM Framework for Dataset Curatability and Repository Stewardship

## Overview

Doc2Validate transforms dataset documentation into machine-actionable validation signals.

Given dataset papers, repository landing pages, and related documentation, the framework:

1. builds task-relevant context under token constraints;
2. extracts a structured dataset schema using LLMs;
3. computes schema-derived curatability features and SCS;
4. generates executable validation workflows;
5. executes generated code in controlled environments;
6. stores logs, execution outcomes, and analysis results.

The framework is designed for scalable, AI-assisted repository stewardship.

## Repository Structure

```text
doc2validate/
├── README.md
├── LICENSE
├── requirements.txt
├── pyproject.toml
├── .gitignore
│
├── configs/
│   ├── model_config.yaml
│   ├── corpus_config.yaml
│   ├── context_config.yaml
│   └── execution_config.yaml
│
├── data/
│   ├── raw_pdfs/
│   ├── raw_landing_pages/
│   ├── structured_docs/
│   ├── extracted_schemas/
│   └── benchmark_metadata/
│
├── src/
│   ├── preprocessing/
│   │   ├── paper_type_filter.py
│   │   ├── pdf_extractor.py
│   │   ├── url_parser.py
│   │   ├── landing_page_crawler.py
│   │   ├── document_structurer.py
│   │   └── batch_scripts/
│   │
│   ├── context/
│   │   ├── context_builder.py
│   │   ├── section_selector.py
│   │   ├── token_budget.py
│   │   └── context_trace.py
│   │
│   ├── schema_extraction/
│   │   ├── dataset_structure_extractor.py
│   │   ├── schema_definition.py
│   │   ├── prompts/
│   │   └── validators.py
│   │
│   ├── feature_computation/
│   │   ├── dataset_feature_computer.py
│   │   └── schema_features.py
│   │
│   ├── scoring/
│   │   └── scs.py
│   │
│   ├── execution/
│   │   ├── code_generator.py
│   │   ├── environment_generator.py
│   │   ├── executor.py
│   │   ├── error_analyzer.py
│   │   └── runtime_templates/
│   │
│   └── utils/
│       ├── io.py
│       ├── logging.py
│       ├── path_utils.py
│       └── llm_client.py
│
├── scripts/
│   ├── build_corpus.py
│   ├── extract_schemas.py
│   ├── compute_scs.py
│   ├── generate_workflows.py
│   ├── run_validation.py
│   └── run_full_pipeline.py
│
├── experiments/
│   ├── context_strategy_ablation/
│   ├── representation_ablation/
│   ├── scs_analysis/
│   └── failure_analysis/
│
├── results/
│   ├── runs/
│   ├── logs/
│   ├── execution_outputs/
│   ├── figures/
│   └── tables/
│
├── notebooks/
│   ├── corpus_statistics.ipynb
│   ├── scs_correlation_analysis.ipynb
│   ├── execution_result_analysis.ipynb
│   └── failure_case_study.ipynb
│
└── examples/
    ├── sample_structured_doc.json
    ├── sample_schema.json
    ├── sample_scs_features.json
    └── sample_execution_result.json
```

