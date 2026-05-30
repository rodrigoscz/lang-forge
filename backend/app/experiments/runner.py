from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import re

from app.db.schema import Database, database_from_env


EXPERIMENT_ID_PATTERN = re.compile(r"^\d{3}-[a-z0-9-]+$")
REQUIRED_SPEC_FIELDS = {
    "hypothesis": "## Hypothesis",
    "variables": "## Variables",
    "metrics": "## Metrics",
    "success_criteria": "## Success Criteria",
}


class ExperimentState(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    ARCHIVED = "archived"


ALLOWED_TRANSITIONS: dict[ExperimentState, set[ExperimentState]] = {
    ExperimentState.DRAFT: {ExperimentState.READY},
    ExperimentState.READY: {ExperimentState.RUNNING},
    ExperimentState.RUNNING: {ExperimentState.COMPLETED, ExperimentState.DRAFT},
    ExperimentState.COMPLETED: {ExperimentState.ARCHIVED},
    ExperimentState.ARCHIVED: set(),
}


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    missing_fields: list[str]


class ExperimentRunner:
    def __init__(self, experiments_dir: Path | str = "experiments", database: Database | None = None) -> None:
        self.experiments_dir = Path(experiments_dir)
        self.database = database or database_from_env()
        self.database.initialize()

    def create(self, name: str, title: str | None = None) -> Path:
        slug = self._slugify(name)
        experiment_id = f"{self._next_number():03d}-{slug}"
        experiment_dir = self.experiments_dir / experiment_id
        (experiment_dir / "data").mkdir(parents=True, exist_ok=False)
        (experiment_dir / "scripts").mkdir(parents=True, exist_ok=True)
        (experiment_dir / "spec.md").write_text(self._spec_template(title or name), encoding="utf-8")
        (experiment_dir / "results.md").write_text(self._results_template(title or name), encoding="utf-8")
        (experiment_dir / "data" / ".gitkeep").touch()
        (experiment_dir / "scripts" / ".gitkeep").touch()
        self._upsert_experiment(experiment_id, title or name)
        return experiment_dir

    def validate(self, experiment_id: str) -> ValidationResult:
        experiment_dir = self._experiment_dir(experiment_id)
        spec_path = experiment_dir / "spec.md"
        missing = []
        if not EXPERIMENT_ID_PATTERN.match(experiment_id):
            missing.append("valid numbered experiment directory name")
        if not spec_path.exists():
            missing.append("spec.md")
        else:
            content = spec_path.read_text(encoding="utf-8")
            missing.extend(label for label, marker in REQUIRED_SPEC_FIELDS.items() if marker not in content)
        return ValidationResult(is_valid=not missing, missing_fields=missing)

    def mark_ready(self, experiment_id: str) -> None:
        validation = self.validate(experiment_id)
        if not validation.is_valid:
            raise ValueError(f"Experiment is missing required fields: {', '.join(validation.missing_fields)}")
        self.transition(experiment_id, ExperimentState.READY, "spec validated")

    def run(self, experiment_id: str) -> None:
        state = self.status(experiment_id)
        if state == ExperimentState.DRAFT:
            self.mark_ready(experiment_id)
        self.transition(experiment_id, ExperimentState.RUNNING, "manual run started")

    def complete(self, experiment_id: str) -> None:
        self.transition(experiment_id, ExperimentState.COMPLETED, "manual run completed")

    def status(self, experiment_id: str) -> ExperimentState:
        with self.database.connect() as connection:
            row = connection.execute("SELECT state FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
        if row is None:
            self._upsert_experiment(experiment_id, experiment_id)
            return ExperimentState.DRAFT
        return ExperimentState(row["state"])

    def transition(self, experiment_id: str, next_state: ExperimentState, reason: str | None = None) -> None:
        current_state = self.status(experiment_id)
        if next_state == current_state:
            return
        if next_state not in ALLOWED_TRANSITIONS[current_state]:
            raise ValueError(f"Invalid experiment transition: {current_state.value} → {next_state.value}")

        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE experiments
                   SET state = ?,
                       updated_at = datetime('now'),
                       completed_at = CASE WHEN ? = 'completed' THEN datetime('now') ELSE completed_at END
                 WHERE id = ?
                """,
                (next_state.value, next_state.value, experiment_id),
            )
            connection.execute(
                """
                INSERT INTO experiment_events (experiment_id, from_state, to_state, reason)
                VALUES (?, ?, ?, ?)
                """,
                (experiment_id, current_state.value, next_state.value, reason),
            )

    def _experiment_dir(self, experiment_id: str) -> Path:
        return self.experiments_dir / experiment_id

    def _next_number(self) -> int:
        self.experiments_dir.mkdir(parents=True, exist_ok=True)
        numbers = []
        for path in self.experiments_dir.iterdir():
            if path.is_dir() and EXPERIMENT_ID_PATTERN.match(path.name):
                numbers.append(int(path.name.split("-", 1)[0]))
        return max(numbers, default=0) + 1

    def _upsert_experiment(self, experiment_id: str, title: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO experiments (id, title, state)
                VALUES (?, ?, 'draft')
                ON CONFLICT(id) DO UPDATE SET title = excluded.title, updated_at = datetime('now')
                """,
                (experiment_id, title),
            )

    @staticmethod
    def _slugify(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if not slug:
            raise ValueError("Experiment name must contain letters or numbers")
        return slug

    @staticmethod
    def _spec_template(title: str) -> str:
        return f"""# {title}\n\n## Hypothesis\n\n_TODO_\n\n## Variables\n\n### Controlled Variables\n\n_TODO_\n\n### Independent Variables\n\n_TODO_\n\n## Metrics\n\n_TODO_\n\n## Data Sources\n\n_TODO_\n\n## Success Criteria\n\n_TODO_\n"""

    @staticmethod
    def _results_template(title: str) -> str:
        return f"""# Results: {title}\n\n## Execution Timestamp\n\n_TODO_\n\n## Input Parameters\n\n_TODO_\n\n## Findings\n\n_TODO_\n"""
