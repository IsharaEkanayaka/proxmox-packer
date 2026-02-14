"""Orchestrator — runs the Packer → Terraform → Ansible pipeline."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from .models import ClusterSpec


class Stage(Enum):
    PACKER = "packer"
    TERRAFORM = "terraform"
    ANSIBLE = "ansible"
    ADDONS = "addons"


@dataclass
class StageResult:
    stage: Stage
    success: bool
    duration_s: float
    message: str


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _run(cmd: list[str], cwd: Path, stage_name: str, dry_run: bool = False) -> StageResult:
    """Run a shell command and return a StageResult."""
    start = time.time()
    cmd_str = " ".join(cmd)

    if dry_run:
        return StageResult(
            stage=Stage(stage_name),
            success=True,
            duration_s=0.0,
            message=f"[DRY RUN] Would execute: {cmd_str} (in {cwd})",
        )

    print(f"\n{'='*60}")
    print(f"  Stage: {stage_name.upper()}")
    print(f"  Command: {cmd_str}")
    print(f"  Working dir: {cwd}")
    print(f"{'='*60}\n")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=False,  # Stream output to terminal
            text=True,
        )
        elapsed = time.time() - start
        if result.returncode == 0:
            return StageResult(Stage(stage_name), True, elapsed, f"Completed in {elapsed:.1f}s")
        else:
            return StageResult(Stage(stage_name), False, elapsed, f"Failed (exit code {result.returncode})")
    except FileNotFoundError:
        elapsed = time.time() - start
        return StageResult(Stage(stage_name), False, elapsed, f"Command not found: {cmd[0]}")
    except Exception as e:
        elapsed = time.time() - start
        return StageResult(Stage(stage_name), False, elapsed, str(e))


def run_packer(dry_run: bool = False) -> StageResult:
    """Build the VM template with Packer."""
    packer_dir = _project_root() / "packer"
    return _run(["packer", "build", "-force", "."], packer_dir, "packer", dry_run)


def run_terraform(dry_run: bool = False, auto_approve: bool = False) -> StageResult:
    """Provision VMs with Terraform."""
    tf_dir = _project_root() / "terraform"

    # Init first
    init_result = _run(["terraform", "init"], tf_dir, "terraform", dry_run)
    if not init_result.success and not dry_run:
        return init_result

    # Plan
    plan_result = _run(["terraform", "plan", "-out=tfplan"], tf_dir, "terraform", dry_run)
    if not plan_result.success and not dry_run:
        return plan_result

    # Apply
    apply_cmd = ["terraform", "apply"]
    if auto_approve:
        apply_cmd.append("-auto-approve")
    apply_cmd.append("tfplan")

    return _run(apply_cmd, tf_dir, "terraform", dry_run)


def run_ansible(spec: ClusterSpec, dry_run: bool = False) -> StageResult:
    """Configure Kubernetes with Ansible."""
    ansible_dir = _project_root() / "ansible"
    return _run(
        ["ansible-playbook", "-i", "inventory.ini", "site.yml"],
        ansible_dir,
        "ansible",
        dry_run,
    )


def run_addons(spec: ClusterSpec, dry_run: bool = False) -> StageResult:
    """Install add-ons with Ansible."""
    ansible_dir = _project_root() / "ansible"
    addons_file = ansible_dir / "addons.yml"

    if not addons_file.exists():
        return StageResult(Stage.ADDONS, True, 0.0, "No add-ons playbook found, skipping.")

    return _run(
        ["ansible-playbook", "-i", "inventory.ini", "addons.yml"],
        ansible_dir,
        "addons",
        dry_run,
    )


def run_pipeline(
    spec: ClusterSpec,
    skip_packer: bool = True,
    auto_approve: bool = False,
    dry_run: bool = False,
) -> list[StageResult]:
    """
    Run the full provisioning pipeline.
    
    Args:
        spec: The cluster specification.
        skip_packer: Skip Packer if template already exists (default: True).
        auto_approve: Auto-approve Terraform apply.
        dry_run: Just print what would happen.
    
    Returns:
        List of StageResults for each pipeline stage.
    """
    results: list[StageResult] = []

    # Packer
    if not skip_packer:
        result = run_packer(dry_run)
        results.append(result)
        if not result.success and not dry_run:
            return results

    # Terraform
    result = run_terraform(dry_run, auto_approve)
    results.append(result)
    if not result.success and not dry_run:
        return results

    # Wait for VMs to boot
    if not dry_run:
        print("\nWaiting 60s for VMs to finish booting...")
        time.sleep(60)
    else:
        results.append(StageResult(Stage.TERRAFORM, True, 0.0, "[DRY RUN] Would wait 60s for VMs to boot"))

    # Ansible
    result = run_ansible(spec, dry_run)
    results.append(result)
    if not result.success and not dry_run:
        return results

    # Add-ons
    if spec.addons:
        result = run_addons(spec, dry_run)
        results.append(result)

    return results


def print_results(results: list[StageResult]):
    """Print a summary of pipeline results."""
    print(f"\n{'='*60}")
    print("  Pipeline Summary")
    print(f"{'='*60}")
    total_time = 0.0
    all_ok = True
    for r in results:
        status = "OK" if r.success else "FAIL"
        icon = "+" if r.success else "x"
        print(f"  [{icon}] {r.stage.value:<12} {status:<6} {r.message}")
        total_time += r.duration_s
        if not r.success:
            all_ok = False
    print(f"{'='*60}")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Result: {'SUCCESS' if all_ok else 'FAILED'}")
    print(f"{'='*60}")
