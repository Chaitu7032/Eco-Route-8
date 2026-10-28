"""HPC2N SWF Workload Trace Parser and Preprocessor for EcoRoute.

Parses Standard Workload Format (SWF) records, cleans and validates entries,
and transforms raw cluster traces into EcoRoute DomainJob and WorkloadDemand objects.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import gzip
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
import uuid

logger = logging.getLogger(__name__)

# Heuristic constants for memory imputation when SWF reports -1
DEFAULT_MEMORY_PER_CORE_GB = Decimal("2.0")
MIN_CPU_CORES = Decimal("1.0")
MAX_CPU_CORES = Decimal("64.0")
MIN_MEMORY_GB = Decimal("1.0")
MAX_MEMORY_GB = Decimal("256.0")
MIN_DURATION_SECONDS = Decimal("5.0")


@dataclass(frozen=True)
class RawSWFRecord:
    """Raw parsed line from a Standard Workload Format (SWF) file.
    
    Fields defined by Hebrew University Parallel Workloads Archive:
    1. Job Number (counter >= 1)
    2. Submit Time (seconds from trace start)
    3. Wait Time (seconds)
    4. Run Time (seconds, wall clock)
    5. Number of Allocated Processors
    6. Average CPU Time Used (seconds)
    7. Used Memory (KB per processor, or -1)
    8. Requested Processors (-1 if unavailable)
    9. Requested Time (seconds, or -1)
    10. Requested Memory (KB per processor, or -1)
    11. Status (1 = Completed, 0 = Failed, 5 = Canceled)
    12. User ID
    13. Group ID
    14. Executable Number
    15. Queue Number
    16. Partition Number
    17. Preceding Job Number
    18. Think Time from Preceding Job
    """
    job_number: int
    submit_time: int
    wait_time: int
    run_time: int
    allocated_processors: int
    avg_cpu_time: float
    used_memory_kb: int
    requested_processors: int
    requested_time: int
    requested_memory_kb: int
    status: int
    user_id: int
    group_id: int
    executable_number: int
    queue_number: int
    partition_number: int
    preceding_job_number: int
    think_time: int


class HPC2NTraceParser:
    """Parser and cleaner for HPC2N-2002 SWF workload files."""

    @staticmethod
    def parse_swf_file(filepath: Path) -> Iterator[RawSWFRecord]:
        """Reads and yields raw SWF records from a .swf or .swf.gz file."""
        if not filepath.exists():
            raise FileNotFoundError(f"SWF file not found: {filepath}")

        opener = gzip.open if str(filepath).endswith(".gz") else open
        with opener(filepath, "rt", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line_str = line.strip()
                if not line_str or line_str.startswith(";"):
                    continue

                parts = line_str.split()
                if len(parts) < 18:
                    continue

                try:
                    record = RawSWFRecord(
                        job_number=int(parts[0]),
                        submit_time=int(parts[1]),
                        wait_time=int(parts[2]),
                        run_time=int(float(parts[3])),
                        allocated_processors=int(parts[4]),
                        avg_cpu_time=float(parts[5]),
                        used_memory_kb=int(parts[6]),
                        requested_processors=int(parts[7]),
                        requested_time=int(float(parts[8])),
                        requested_memory_kb=int(parts[9]),
                        status=int(parts[10]),
                        user_id=int(parts[11]),
                        group_id=int(parts[12]),
                        executable_number=int(parts[13]),
                        queue_number=int(parts[14]),
                        partition_number=int(parts[15]),
                        preceding_job_number=int(parts[16]),
                        think_time=int(parts[17]),
                    )
                    yield record
                except (ValueError, IndexError):
                    continue

    @classmethod
    def extract_valid_jobs(
        cls,
        filepath: Path,
        max_jobs: int = 1000,
        base_time: Optional[datetime] = None,
        min_runtime_seconds: int = 5,
    ) -> List[Dict[str, Any]]:
        """Filters valid completed jobs and transforms them into EcoRoute job dicts.

        Invariants enforced:
        - status == 1 (Completed normally; eliminates aborted/cancelled jobs)
        - run_time >= min_runtime_seconds
        - allocated_processors > 0
        - memory imputed deterministically if -1
        """
        start_dt = base_time or datetime(2023, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
        valid_jobs: List[Dict[str, Any]] = []

        for record in cls.parse_swf_file(filepath):
            # Filtering rules
            if record.status != 1:  # Only successfully completed jobs
                continue
            if record.run_time < min_runtime_seconds:
                continue
            if record.allocated_processors <= 0:
                continue

            cpu_val = min(MAX_CPU_CORES, max(MIN_CPU_CORES, Decimal(str(record.allocated_processors))))
            duration_val = Decimal(str(record.run_time))

            # Memory handling: if used_memory_kb > 0, convert to GB; otherwise use documented heuristic
            if record.used_memory_kb > 0:
                total_mem_kb = record.used_memory_kb * record.allocated_processors
                raw_mem_gb = Decimal(str(total_mem_kb)) / Decimal("1048576")
                mem_val = min(MAX_MEMORY_GB, max(MIN_MEMORY_GB, raw_mem_gb.quantize(Decimal("0.01"))))
                memory_source = "OBSERVED_TRACE_MEMORY"
            else:
                mem_val = min(MAX_MEMORY_GB, max(MIN_MEMORY_GB, cpu_val * DEFAULT_MEMORY_PER_CORE_GB))
                memory_source = "IMPUTED_STANDARD_2GB_PER_CORE"

            # Derive synthetic archetype
            if duration_val < Decimal("60"):
                archetype = "INFERENCE"
                slack_multiplier = Decimal("1.3")
                priority_val = 2  # High priority
            elif duration_val <= Decimal("1800"):
                archetype = "BATCH"
                slack_multiplier = Decimal("2.0")
                priority_val = 5  # Medium priority
            else:
                archetype = "TRAINING"
                slack_multiplier = Decimal("3.0")
                priority_val = 8  # Low priority

            # Derive arrival and deadline
            arrival_time = start_dt + timedelta(seconds=record.submit_time % (7 * 86400))
            deadline_seconds = float(duration_val * slack_multiplier)
            deadline_time = arrival_time + timedelta(seconds=deadline_seconds)

            job_dict = {
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"hpc2n-job-{record.job_number}")),
                "workload_name": f"hpc2n-{archetype.lower()}-{record.job_number:06d}",
                "workload_type": archetype,
                "cpu_demand": float(cpu_val),
                "memory_demand": float(mem_val),
                "base_execution_duration": float(duration_val),
                "priority": priority_val,
                "deadline": deadline_time.isoformat(),
                "created_at": arrival_time.isoformat(),
                "provenance": {
                    "trace_source": "HPC2N-2002-2.2-cln.swf",
                    "original_job_number": record.job_number,
                    "original_submit_seconds": record.submit_time,
                    "original_runtime_seconds": record.run_time,
                    "original_allocated_processors": record.allocated_processors,
                    "original_used_memory_kb": record.used_memory_kb,
                    "memory_source": memory_source,
                    "synthetic_slack_multiplier": float(slack_multiplier),
                },
            }
            valid_jobs.append(job_dict)

            if len(valid_jobs) >= max_jobs:
                break

        return valid_jobs


def run_pipeline() -> None:
    """Preprocesses raw HPC2N trace and outputs validated JSON fixtures."""
    raw_path = Path("backend/data/raw/HPC2N-2002-2.2-cln.swf")
    if not raw_path.exists():
        raw_path = Path("backend/data/raw/HPC2N-2002-2.2-cln.swf.gz")
    if not raw_path.exists():
        raw_path = Path("data/raw/HPC2N-2002-2.2-cln.swf")
    if not raw_path.exists():
        raw_path = Path("data/raw/HPC2N-2002-2.2-cln.swf.gz")

    processed_dir = Path("backend/data/processed")
    if not processed_dir.parent.exists():
        processed_dir = Path("data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Extracting 1,000 valid jobs from {raw_path}...")
    jobs_1000 = HPC2NTraceParser.extract_valid_jobs(raw_path, max_jobs=1000)

    out_file = processed_dir / "hpc2n_workloads_1000.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(jobs_1000, f, indent=2)

    print(f"Successfully preprocessed {len(jobs_1000)} valid HPC2N jobs to {out_file}")


if __name__ == "__main__":
    run_pipeline()
