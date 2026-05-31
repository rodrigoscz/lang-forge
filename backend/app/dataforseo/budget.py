from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import wraps
from typing import ParamSpec, TypeVar

from app.db.schema import Database


P = ParamSpec("P")
R = TypeVar("R")


class BudgetExceededError(RuntimeError):
    pass


@dataclass(frozen=True)
class BudgetStatus:
    experiment_id: str
    period_start: str
    period_end: str
    monthly_budget_cents: int
    spent_cents: int
    query_count: int
    remaining_cents: int


class QueryBudget:
    def __init__(self, database: Database, *, monthly_budget_cents: int = 10_000, per_experiment_limit: int = 500) -> None:
        if monthly_budget_cents < 1:
            raise ValueError("monthly_budget_cents must be positive")
        if per_experiment_limit < 1:
            raise ValueError("per_experiment_limit must be positive")
        self.database = database
        self.monthly_budget_cents = monthly_budget_cents
        self.per_experiment_limit = per_experiment_limit

    def estimate_cost(self, query_count: int, *, cost_per_query_cents: int = 2) -> int:
        if query_count < 0:
            raise ValueError("query_count must not be negative")
        return query_count * cost_per_query_cents

    def check(self, experiment_id: str, estimated_cost_cents: int) -> BudgetStatus:
        status = self.status(experiment_id)
        if status.query_count + 1 > self.per_experiment_limit:
            raise BudgetExceededError(f"Experiment {experiment_id} reached query limit of {self.per_experiment_limit}")
        if status.spent_cents + estimated_cost_cents > status.monthly_budget_cents:
            raise BudgetExceededError(
                f"Monthly budget exceeded: {status.spent_cents + estimated_cost_cents}c would exceed "
                f"{status.monthly_budget_cents}c"
            )
        return status

    def record(self, experiment_id: str, actual_cost_cents: int) -> BudgetStatus:
        try:
            self.check(experiment_id, actual_cost_cents)
        except BudgetExceededError:
            pass
        period_start, period_end = self._current_period()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO query_budget (
                  experiment_id, period_start, period_end, monthly_budget_cents, spent_cents, query_count
                )
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(experiment_id, period_start, period_end) DO UPDATE SET
                  spent_cents = spent_cents + excluded.spent_cents,
                  query_count = query_count + 1,
                  updated_at = datetime('now')
                """,
                (experiment_id, period_start, period_end, self.monthly_budget_cents, actual_cost_cents),
            )
        return self.status(experiment_id)

    def status(self, experiment_id: str) -> BudgetStatus:
        period_start, period_end = self._current_period()
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT monthly_budget_cents, spent_cents, query_count
                FROM query_budget
                WHERE experiment_id = ? AND period_start = ? AND period_end = ?
                """,
                (experiment_id, period_start, period_end),
            ).fetchone()
        if row is None:
            spent_cents = 0
            query_count = 0
            monthly_budget_cents = self.monthly_budget_cents
        else:
            spent_cents = int(row["spent_cents"])
            query_count = int(row["query_count"])
            monthly_budget_cents = int(row["monthly_budget_cents"])
        return BudgetStatus(
            experiment_id=experiment_id,
            period_start=period_start,
            period_end=period_end,
            monthly_budget_cents=monthly_budget_cents,
            spent_cents=spent_cents,
            query_count=query_count,
            remaining_cents=max(0, monthly_budget_cents - spent_cents),
        )

    def decorator(self, experiment_id: str, estimated_cost_cents: int) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
        def decorate(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
            @wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                self.check(experiment_id, estimated_cost_cents)
                result = await func(*args, **kwargs)
                self.record(experiment_id, estimated_cost_cents)
                return result

            return wrapper

        return decorate

    def _current_period(self) -> tuple[str, str]:
        now = datetime.now(UTC)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if period_start.month == 12:
            period_end = period_start.replace(year=period_start.year + 1, month=1)
        else:
            period_end = period_start.replace(month=period_start.month + 1)
        return period_start.date().isoformat(), period_end.date().isoformat()
