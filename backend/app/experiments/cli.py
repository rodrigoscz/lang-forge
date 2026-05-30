from __future__ import annotations

import argparse
from pathlib import Path

from app.experiments.runner import ExperimentRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Lang Forge experiments.")
    parser.add_argument("--experiments-dir", default="experiments", help="Path to the experiments directory.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    create = subcommands.add_parser("create", help="Create a numbered experiment scaffold.")
    create.add_argument("name", help="Experiment name used for the folder slug.")
    create.add_argument("--title", help="Human-readable experiment title.")

    validate = subcommands.add_parser("validate", help="Validate an experiment spec.")
    validate.add_argument("experiment_id")

    run = subcommands.add_parser("run", help="Validate and transition an experiment to running.")
    run.add_argument("experiment_id")

    status = subcommands.add_parser("status", help="Print an experiment lifecycle state.")
    status.add_argument("experiment_id")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    runner = ExperimentRunner(experiments_dir=Path(args.experiments_dir))

    if args.command == "create":
        experiment_dir = runner.create(args.name, title=args.title)
        print(experiment_dir)
    elif args.command == "validate":
        result = runner.validate(args.experiment_id)
        if result.is_valid:
            print(f"{args.experiment_id}: valid")
            return
        parser.exit(1, f"{args.experiment_id}: missing {', '.join(result.missing_fields)}\n")
    elif args.command == "run":
        runner.run(args.experiment_id)
        print(f"{args.experiment_id}: running")
    elif args.command == "status":
        print(runner.status(args.experiment_id).value)


if __name__ == "__main__":
    main()
