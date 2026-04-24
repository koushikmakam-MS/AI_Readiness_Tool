"""Extended tests for SetupOnboardingChecker — new script/tool detection."""
from __future__ import annotations

import pytest

from ai_readiness.checkers.setup_onboarding import SetupOnboardingChecker
from ai_readiness.core.models import CheckStatus
from tests.conftest import create_file


def _run(tmp_path):
    checker = SetupOnboardingChecker(repo_path=tmp_path)
    return {c.name: c for c in checker.run_checks()}


# ── Single-command build ─────────────────────────────────────────────

def test_init_ps1_detected(tmp_path):
    create_file(tmp_path, "init.ps1", "Write-Host 'init'")
    results = _run(tmp_path)
    assert results["Single-command build"].status is CheckStatus.PASS


def test_init_cmd_detected(tmp_path):
    create_file(tmp_path, "init.cmd", "echo init")
    results = _run(tmp_path)
    assert results["Single-command build"].status is CheckStatus.PASS


def test_build_sh_detected(tmp_path):
    create_file(tmp_path, "build.sh", "#!/bin/bash\nmake")
    results = _run(tmp_path)
    assert results["Single-command build"].status is CheckStatus.PASS


def test_setup_py_detected(tmp_path):
    create_file(tmp_path, "setup.py", "# setup")
    results = _run(tmp_path)
    assert results["Single-command build"].status is CheckStatus.PASS


def test_makefile_detected(tmp_path):
    create_file(tmp_path, "Makefile", "all:\n\techo build")
    results = _run(tmp_path)
    assert results["Single-command build"].status is CheckStatus.PASS


def test_justfile_detected(tmp_path):
    create_file(tmp_path, "justfile", "build:\n  echo build")
    results = _run(tmp_path)
    assert results["Single-command build"].status is CheckStatus.PASS


def test_taskfile_detected(tmp_path):
    create_file(tmp_path, "Taskfile.yml", "version: '3'")
    results = _run(tmp_path)
    assert results["Single-command build"].status is CheckStatus.PASS


# ── Helper scripts ───────────────────────────────────────────────────

def test_config_scripts_dir_detected(tmp_path):
    create_file(tmp_path, ".config/.scripts/setup.sh", "#!/bin/bash")
    results = _run(tmp_path)
    assert results["Helper scripts"].status is CheckStatus.PASS


def test_tools_dir_detected(tmp_path):
    create_file(tmp_path, "tools/lint.sh", "#!/bin/bash")
    results = _run(tmp_path)
    assert results["Helper scripts"].status is CheckStatus.PASS


def test_root_ps1_detected_as_helper(tmp_path):
    create_file(tmp_path, "deploy.ps1", "Write-Host 'deploy'")
    results = _run(tmp_path)
    assert results["Helper scripts"].status is CheckStatus.PASS


def test_root_cmd_detected_as_helper(tmp_path):
    create_file(tmp_path, "deploy.cmd", "echo deploy")
    results = _run(tmp_path)
    assert results["Helper scripts"].status is CheckStatus.PASS


def test_root_sh_detected_as_helper(tmp_path):
    create_file(tmp_path, "deploy.sh", "#!/bin/bash")
    results = _run(tmp_path)
    assert results["Helper scripts"].status is CheckStatus.PASS


# ── Empty repo ───────────────────────────────────────────────────────

def test_empty_repo_all_fail(tmp_path):
    results = _run(tmp_path)
    assert results["Single-command build"].status is CheckStatus.FAIL
    assert results["Container support"].status is CheckStatus.FAIL
    assert results["Helper scripts"].status is CheckStatus.FAIL
    assert results["Environment template"].status is CheckStatus.FAIL
