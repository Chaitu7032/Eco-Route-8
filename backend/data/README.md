# EcoRoute Real-World Datasets & Empirical Evaluation Guide

This directory documents the provenance, licensing, schemas, preprocessing pipelines, and empirical benchmark results for the real-world datasets integrated into EcoRoute.

---

## 1. Dataset Directory Architecture

```
backend/data/
├── hardware_power_profiles.json      # SPECpower_ssj2008 verified FDR power curves & latency
├── raw/                              # (Git-ignored) Raw archives and direct source files
│   ├── HPC2N-2002-2.2-cln.swf        # Decompressed Standard Workload Format (19.2 MB)
│   ├── HPC2N-2002-2.2-cln.swf.gz     # Downloaded gzip archive (3.0 MB)
│   ├── gcp_region_carbon_2023.csv    # Google Cloud 2023 grid carbon report (1.4 KB)
│   └── uk_eso_carbon_intensity_7d.json # UK ESO 7-day half-hourly grid observations (64.9 KB)
└── processed/                        # (Git-ignored) Cleaned, standardized JSON artifacts
    ├── hpc2n_workloads_1000.json     # 1,000 valid completed jobs adhering to DomainJob
    ├── regional_carbon_series.json   # 337 half-hourly carbon points across all 5 regions
    └── benchmark_empirical_summary.json # 5-strategy empirical benchmark metrics
```

---

## 2. Source Provenance & Licensing

### A. HPC2N-2002 Workload Trace
* **Source**: Parallel Workloads Archive (Hebrew University of Jerusalem)
* **Citation**: D. G. Feitelson et al., "Parallel Workloads Archive: HPC2N Seth Linux Cluster"
* **Download URL**: `https://www.cs.huji.ac.il/labs/parallel/workload/l_hpc2n/HPC2N-2002-2.2-cln.swf.gz`
* **Format**: Standard Workload Format (SWF), 18 whitespace-separated fields.
* **Licensing**: Academic Public Domain / Free for research evaluation.
* **Verified Size**: **2.99 MB compressed** (`.gz`), **19.24 MB decompressed** (202,871 records).

### B. Google Cloud Regional Carbon Report (2023)
* **Source**: Google Cloud Region Carbon Information Official GitHub Repository
* **Citation**: Google LLC, `GoogleCloudPlatform/region-carbon-info/data/yearly/2023.csv`
* **Download URL**: `https://raw.githubusercontent.com/GoogleCloudPlatform/region-carbon-info/main/data/yearly/2023.csv`
* **Format**: CSV (`Google Cloud Region`, `Location`, `Google CFE`, `Grid carbon intensity (gCO2eq / kWh)`).
* **Licensing**: Apache 2.0.
* **Verified Size**: **1.37 KB**.

### C. UK National Grid ESO Carbon Intensity Series
* **Source**: National Energy System Operator (NESO) Carbon Intensity API
* **Citation**: NESO / UK Carbon Intensity API
* **Download URL**: `https://api.carbonintensity.org.uk/intensity/2023-05-01T00:00Z/2023-05-08T00:00Z`
* **Format**: JSON (337 half-hourly settlement periods).
* **Licensing**: Open Government Licence v3.0.
* **Verified Size**: **64.9 KB**.

### D. Hardware Power Profiles (SPECpower_ssj2008)
* **Source**: Standard Performance Evaluation Corporation (SPEC)
* **Citation**: SPECpower_ssj2008 Disclosure Reports (Dell PowerEdge R650, HPE ProLiant DL385, Lenovo SR650 V2)
* **Format**: JSON (`backend/data/hardware_power_profiles.json`).
* **Licensing**: SPEC Fair Use Policy.
* **Verified Size**: **2.5 KB**.

---

## 3. Storage Footprint & Hard Budget Accounting

```
+--------------------------------------------------------------------------------------+
| Asset                                         | Compressed Download | Extracted Size |
+-----------------------------------------------+---------------------+----------------+
| HPC2N-2002-2.2-cln.swf.gz                     | 2.997 MB            | 19.242 MB      |
| gcp_region_carbon_2023.csv                    | 0.001 MB            | 0.001 MB       |
| uk_eso_carbon_intensity_7d.json               | 0.065 MB            | 0.065 MB       |
| hardware_power_profiles.json                  | 0.003 MB            | 0.003 MB       |
+-----------------------------------------------+---------------------+----------------+
| Total Combined Download                       | 3.066 MB            | 19.311 MB      |
| Hard Constraint Budget Limit                  | 1,024.000 MB (1 GB) | N/A            |
| Remaining Safety Headroom                     | 1,020.934 MB (99.7%)| N/A            |
+-----------------------------------------------+---------------------+----------------+
```

---

## 4. Preprocessing & Reproduction Commands

To reproduce the data extraction, preprocessing, and benchmark execution from scratch:

```bash
# 1. Activate the environment
cd backend

# 2. Preprocess the raw HPC2N SWF trace into 1,000 valid DomainJob records
uv run python scripts/preprocess_hpc2n.py

# 3. Preprocess and synchronize empirical multi-region carbon time series
uv run python scripts/preprocess_carbon.py

# 4. Run the dataset integration unit tests
uv run pytest tests/test_dataset_integration.py -v

# 5. Run the empirical 5-strategy benchmark suite (100 workloads)
uv run pytest tests/test_empirical_benchmark.py -s -v
```

---

## 5. Schema Field Mapping

| EcoRoute Domain Attribute | Source Dataset Field | Transformation / Mapping Logic |
| :--- | :--- | :--- |
| `Job.id` | SWF Field 1 (`Job Number`) | Deterministic UUID5: `uuid.uuid5(NAMESPACE_DNS, f"hpc2n-job-{job_num}")` |
| `Job.workload_type` | SWF Field 4 (`Run Time`) | Duration $<60\text{s} \rightarrow \text{INFERENCE}$; $60-1800\text{s} \rightarrow \text{BATCH}$; $>1800\text{s} \rightarrow \text{TRAINING}$ |
| `WorkloadDemand.cpu_demand` | SWF Field 5 (`Allocated Processors`) | Clamped: $\min(64.0, \max(1.0, \text{Field 5}))$ cores |
| `WorkloadDemand.memory_demand` | SWF Field 7 (`Used Memory KB`) | If $>0$, $\text{KB} / 1024^2 \times \text{cores}$; Else documented heuristic: $2.0\text{ GB} \times \text{cores}$ |
| `WorkloadDemand.base_duration` | SWF Field 4 (`Run Time`) | Wall-clock seconds: $\text{Decimal}(\text{Field 4})$ |
| `Job.priority` | Heuristic from duration archetype | High Priority ($2$), Medium Priority ($5$), Low Priority ($8$) |
| `Job.deadline` | Trace Submit Time + Duration | $\text{Arrival} + T_{\text{base}} \times \text{SlackMultiplier}$ (where multiplier $\in [1.3, 3.0]$) |
| `Region.idle_power_watts` | SPECpower_ssj2008 FDR | Dell R650: $128.0\text{W}$; Lenovo SR650: $98.0\text{W}$ |
| `Region.peak_power_watts` | SPECpower_ssj2008 FDR | Dell R650: $542.0\text{W}$; Lenovo SR650: $412.0\text{W}$ |
| `CarbonIntensity.value` | GCP 2023 + UK ESO Diurnal Series | Scaled $\text{gCO}_2\text{eq/kWh}$; strict `None` if missing (Zero Fabrication) |
