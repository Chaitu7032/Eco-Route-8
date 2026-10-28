"""Comprehensive empirical benchmark comparing all five scheduler variants on HPC2N workloads."""

from decimal import Decimal
import json
import logging
from pathlib import Path
import pytest

from app.domain.carbon import CarbonQuality
from app.persistence.models.enums import SchedulerVariant
from app.simulation.dataset_loader import DatasetScenarioLoader, DatasetWorkloadLoader
from app.simulation.simulation_runtime import SimulationRuntime

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_full_benchmark_comparison_100_jobs():
    """Runs a 100-job empirical comparison across all 5 strategies on verified HPC2N data."""
    workload_count = 100
    base_scenario = DatasetScenarioLoader.load_empirical_scenario(timestamp_index=12)
    runtime = SimulationRuntime()

    strategies = [
        SchedulerVariant.ECOROUTE,
        SchedulerVariant.CONVENTIONAL,
        SchedulerVariant.CARBON_ONLY,
        SchedulerVariant.PERFORMANCE_ONLY,
        SchedulerVariant.RANDOM,
    ]

    benchmark_summary = {}

    for strat in strategies:
        cloned_scenario = base_scenario.clone()
        cloned_workloads = DatasetWorkloadLoader.load_hpc2n_jobs(limit=workload_count)

        res = await runtime.run_strategy(
            strategy=strat,
            workloads=cloned_workloads,
            scenario=cloned_scenario,
            base_time=cloned_workloads[0].created_at,
            random_seed=42,
        )

        completed = res.detailed_metrics["completed_count"]
        failed = res.detailed_metrics["failed_count"]
        deferred = res.detailed_metrics["deferred_count"]

        benchmark_summary[strat.value] = {
            "total_energy_kwh": float(res.total_energy_kwh),
            "total_co2eq_grams": float(res.total_co2eq_grams),
            "avg_execution_time_seconds": float(res.avg_execution_time_seconds),
            "avg_latency_ms": float(res.avg_latency_ms),
            "deadline_compliance_rate": float(res.deadline_compliance_rate),
            "failure_rate": float(res.failure_rate),
            "deferral_rate": float(res.deferral_rate),
            "duplicate_execution_count": res.duplicate_execution_count,
            "completed_count": completed,
            "failed_count": failed,
            "deferred_count": deferred,
        }

    # Verify all completed without duplicates
    for s_name, s_data in benchmark_summary.items():
        assert s_data["duplicate_execution_count"] == 0
        assert s_data["completed_count"] + s_data["failed_count"] + s_data["deferred_count"] == workload_count

    # Carbon reduction vs Conventional
    conv_co2 = benchmark_summary["CONVENTIONAL"]["total_co2eq_grams"]
    eco_co2 = benchmark_summary["ECOROUTE"]["total_co2eq_grams"]
    carbon_only_co2 = benchmark_summary["CARBON_ONLY"]["total_co2eq_grams"]

    if conv_co2 > 0:
        carbon_savings_pct = ((conv_co2 - eco_co2) / conv_co2) * 100.0
        benchmark_summary["ECOROUTE"]["carbon_savings_pct_vs_conventional"] = round(carbon_savings_pct, 2)

    # Save artifact
    out_path = Path("data/processed/benchmark_empirical_summary.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_summary, f, indent=2)

    print("\nEmpirical 100-Job Benchmark Completed:")
    for strat, data in benchmark_summary.items():
        print(f"[{strat}] Energy: {data['total_energy_kwh']} kWh | CO2: {data['total_co2eq_grams']} g | SLA: {data['deadline_compliance_rate']*100:.1f}%")
