from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from app.db.schema import Database
from app.experiments.cli import build_parser
from app.experiments.runner import ExperimentRunner, ExperimentState


def test_create_scaffolds_directories(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.db")
    database.initialize()
    runner = ExperimentRunner(experiments_dir=tmp_path / "experiments", database=database)
    experiment_dir = runner.create("test-experiment")
    assert experiment_dir.exists()
    assert (experiment_dir / "data").exists()
    assert (experiment_dir / "scripts").exists()
    assert (experiment_dir / "spec.md").exists()
    assert (experiment_dir / "results.md").exists()


def test_create_generates_numbered_experiment_id(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.db")
    database.initialize()
    runner = ExperimentRunner(experiments_dir=tmp_path / "experiments", database=database)
    d1 = runner.create("first")
    d2 = runner.create("second")
    assert d1.name == "001-first"
    assert d2.name == "002-second"


def test_validate_accepts_valid_experiment(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.db")
    database.initialize()
    runner = ExperimentRunner(experiments_dir=tmp_path / "experiments", database=database)
    experiment_dir = runner.create("valid-exp")
    spec = experiment_dir / "spec.md"
    spec.write_text(
        "# Title\n\n## Hypothesis\n\nTest\n\n## Variables\n\nX\n\n## Controlled Variables\n\nY\n\n## Independent Variables\n\nZ\n\n## Metrics\n\nM\n\n## Data Sources\n\nD\n\n## Success Criteria\n\nS\n",
        encoding="utf-8",
    )
    result = runner.validate(experiment_dir.name)
    assert result.is_valid
    assert result.missing_fields == []


def test_validate_reports_missing_spec(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.db")
    database.initialize()
    runner = ExperimentRunner(experiments_dir=tmp_path / "experiments", database=database)
    result = runner.validate("001-missing")
    assert not result.is_valid
    assert "spec.md" in result.missing_fields


def test_validate_reports_missing_sections(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.db")
    database.initialize()
    runner = ExperimentRunner(experiments_dir=tmp_path / "experiments", database=database)
    experiment_dir = runner.create("incomplete")
    spec = experiment_dir / "spec.md"
    spec.write_text("# No sections\n", encoding="utf-8")
    result = runner.validate(experiment_dir.name)
    assert not result.is_valid
    assert "hypothesis" in result.missing_fields
    assert "metrics" in result.missing_fields
    assert "success_criteria" in result.missing_fields


def test_status_returns_draft_for_unknown_experiment(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.db")
    database.initialize()
    runner = ExperimentRunner(experiments_dir=tmp_path / "experiments", database=database)
    assert runner.status("999-unknown") == ExperimentState.DRAFT


def test_transition_allows_valid_transitions(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.db")
    database.initialize()
    runner = ExperimentRunner(experiments_dir=tmp_path / "experiments", database=database)
    exp_dir = runner.create("transitions")
    exp_id = exp_dir.name
    spec = exp_dir / "spec.md"
    spec.write_text(
        "# T\n\n## Hypothesis\n\nH\n\n## Variables\n\nV\n\n## Controlled Variables\n\nC\n\n## Independent Variables\n\nI\n\n## Metrics\n\nM\n\n## Data Sources\n\nD\n\n## Success Criteria\n\nS\n",
        encoding="utf-8",
    )

    runner.mark_ready(exp_id)
    assert runner.status(exp_id) == ExperimentState.READY

    runner.run(exp_id)
    assert runner.status(exp_id) == ExperimentState.RUNNING

    runner.complete(exp_id)
    assert runner.status(exp_id) == ExperimentState.COMPLETED


def test_transition_rejects_invalid_transitions(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.db")
    database.initialize()
    runner = ExperimentRunner(experiments_dir=tmp_path / "experiments", database=database)
    exp_dir = runner.create("bad-transition")
    exp_id = exp_dir.name

    with pytest.raises(ValueError, match="Invalid experiment transition"):
        runner.transition(exp_id, ExperimentState.COMPLETED)


def test_mark_ready_validates_before_transition(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.db")
    database.initialize()
    runner = ExperimentRunner(experiments_dir=tmp_path / "experiments", database=database)
    exp_dir = runner.create("no-spec")
    (exp_dir / "spec.md").write_text("# No sections\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required fields"):
        runner.mark_ready(exp_dir.name)


def test_run_auto_validates_and_starts(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.db")
    database.initialize()
    runner = ExperimentRunner(experiments_dir=tmp_path / "experiments", database=database)
    exp_dir = runner.create("auto-run")
    exp_id = exp_dir.name
    spec = exp_dir / "spec.md"
    spec.write_text(
        "# T\n\n## Hypothesis\n\nH\n\n## Variables\n\nV\n\n## Controlled Variables\n\nC\n\n## Independent Variables\n\nI\n\n## Metrics\n\nM\n\n## Data Sources\n\nD\n\n## Success Criteria\n\nS\n",
        encoding="utf-8",
    )
    runner.run(exp_id)
    assert runner.status(exp_id) == ExperimentState.RUNNING


def test_cli_parser_accepts_create(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(["create", "test-cli"])
    assert args.command == "create"
    assert args.name == "test-cli"
    assert args.title is None


def test_cli_parser_accepts_validate(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(["validate", "001-test"])
    assert args.command == "validate"
    assert args.experiment_id == "001-test"


def test_cli_parser_accepts_status(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(["status", "001-test"])
    assert args.command == "status"
    assert args.experiment_id == "001-test"


def test_cli_parser_accepts_run(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(["run", "001-test"])
    assert args.command == "run"
    assert args.experiment_id == "001-test"


def test_cli_parser_requires_subcommand(tmp_path: Path) -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])
