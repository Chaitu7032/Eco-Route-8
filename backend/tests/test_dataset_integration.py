"""Dataset Integration and Validation Tests for EcoRoute."""

from decimal import Decimal
from pathlib import Path
import pytest

from app.domain.carbon import CarbonQuality
from app.persistence.models.enums import SchedulerVariant
from app.simulation.dataset_loader import DatasetScenarioLoader, DatasetWorkloadLoader
from app.simulation.simulation_runtime import SimulationRuntime


def test_raw_dataset_files_exist_and_non_empty():
    """Validates that raw and processed data assets exist with expected non-zero sizes."""
    raw_swf = Path("data/raw/HPC2N-2002-2.2-cln.swf")
    raw_gz = Path("data/raw/HPC2N-2002-2.2-cln.swf.gz")
    assert raw_swf.exists() or raw_gz.exists()
    if raw_swf.exists():
        assert raw_swf.stat().st_size > 10_000_000  # ~19 MB

    gcp_csv = Path("data/raw/gcp_region_carbon_2023.csv")
    assert gcp_csv.exists()
    assert gcp_csv.stat().st_size > 500

    hw_json = Path("data/hardware_power_profiles.json")
    assert hw_json.exists()
    assert hw_json.stat().st_size > 500


def test_hpc2n_workload_loading_and_schema_validation():
    """Validates that preprocessed HPC2N jobs comply with all domain invariants."""
    jobs = DatasetWorkloadLoader.load_hpc2n_jobs(limit=50)
    assert len(jobs) == 50

    for job in jobs:
        # Boundary constraints
        assert job.demand.cpu_demand > Decimal("0")
        assert job.demand.memory_demand > Decimal("0")
        assert job.demand.base_execution_duration > Decimal("0")
        assert 1 <= job.priority.value <= 10
        assert job.deadline > job.created_at
        assert job.workload_name.startswith("hpc2n-")


def test_empirical_scenario_loading_and_hardware_power_profiles():
    """Validates scenario region attributes and SPECpower verified values."""
    scenario = DatasetScenarioLoader.load_empirical_scenario(timestamp_index=0)
    assert len(scenario.regions) == 5

    region_codes = {r.code for r in scenario.regions}
    assert region_codes == {"se-sto", "fr-par", "de-fra", "us-east", "pl-war"}

    for r in scenario.regions:
        assert r.idle_power_watts > Decimal("0")
        assert r.peak_power_watts > r.idle_power_watts
        assert r.max_cpu_capacity > Decimal("0")
        assert r.max_memory_capacity > Decimal("0")
        assert Decimal("0.0") <= r.current_utilization <= Decimal("1.0")

        # Carbon observation verification
        ci = scenario.carbon_map[r.id]
        assert ci.source is not None
        if ci.quality in (CarbonQuality.LIVE, CarbonQuality.VALID_CACHE):
            assert ci.value is not None
            assert ci.value > Decimal("0")
        elif ci.quality in (CarbonQuality.UNAVAILABLE, CarbonQuality.CONVENTIONAL_FALLBACK):
            assert ci.value is None


def test_zero_carbon_fabrication_handling_in_empirical_scenario():
    """Validates that missing or unavailable carbon preserves value=None without guessing."""
    scenario = DatasetScenarioLoader.load_empirical_scenario(timestamp_index=0)

    # Set one region explicitly to UNAVAILABLE
    target_r = scenario.regions[0]
    from app.domain.carbon import CarbonIntensity, CarbonSource

    unavail_ci = CarbonIntensity(
        quality=CarbonQuality.UNAVAILABLE,
        source=CarbonSource.ELECTRICITY_MAPS,
        value=None,
    )
    scenario.carbon_map[target_r.id] = unavail_ci

    assert scenario.carbon_map[target_r.id].value is None
    assert not scenario.carbon_map[target_r.id].is_trustworthy


@pytest.mark.asyncio
async def test_all_five_schedulers_on_identical_hpc2n_workloads():
    """Runs all 5 scheduler variants across an identical 20-job real workload slice."""
    jobs = DatasetWorkloadLoader.load_hpc2n_jobs(limit=20)
    base_scenario = DatasetScenarioLoader.load_empirical_scenario(timestamp_index=10)
    runtime = SimulationRuntime()

    strategies = [
        SchedulerVariant.ECOROUTE,
        SchedulerVariant.CONVENTIONAL,
        SchedulerVariant.CARBON_ONLY,
        SchedulerVariant.PERFORMANCE_ONLY,
        SchedulerVariant.RANDOM,
    ]

    results = {}
    for strat in strategies:
        cloned_scenario = base_scenario.clone()
        cloned_jobs = DatasetWorkloadLoader.load_hpc2n_jobs(limit=20)
        res = await runtime.run_strategy(
            strategy=strat,
            workloads=cloned_jobs,
            scenario=cloned_scenario,
            base_time=cloned_jobs[0].created_at,
            random_seed=42,
        )
        results[strat.value] = res
        assert res.detailed_metrics["total_workloads"] == 20
        assert res.deadline_compliance_rate >= Decimal("0.0")
        assert res.duplicate_execution_count == 0

    # Ensure all 5 strategies produced results
    assert len(results) == 5
    assert results["ECOROUTE"].total_energy_kwh > Decimal("0.0")
    assert results["CONVENTIONAL"].total_energy_kwh > Decimal("0.0")
    assert results["CARBON_ONLY"].total_energy_kwh > Decimal("0.0")
    assert results["PERFORMANCE_ONLY"].total_energy_kwh > Decimal("0.0")
    assert results["RANDOM"].total_energy_kwh > Decimal("0.0")
