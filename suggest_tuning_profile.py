"""CLI for producing a suggested tuning profile from evaluation records."""

from __future__ import annotations

import argparse

from feedback_profile_suggester import (
    DEFAULT_PROFILE_ID,
    load_evaluation_records,
    suggest_tuning_profile,
    write_suggested_profile,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Suggest a reviewable auto_acoustic tuning profile from evaluation records."
    )
    parser.add_argument(
        "feedback_inputs",
        nargs="+",
        help="Evaluation record JSON files or directories containing *_evaluation_record.json files.",
    )
    parser.add_argument("--profile-id", default=DEFAULT_PROFILE_ID)
    parser.add_argument("--base", default="auto_acoustic")
    parser.add_argument("--out", default="profiles/suggested_feedback_profile.json")
    parser.add_argument("--min-records", type=int, default=1)
    args = parser.parse_args()

    records = load_evaluation_records(args.feedback_inputs)
    if len(records) < args.min_records:
        raise SystemExit(
            f"Need at least {args.min_records} evaluation records, found {len(records)}."
        )
    profile = suggest_tuning_profile(records, profile_id=args.profile_id, base=args.base)
    write_suggested_profile(profile, args.out)

    print(f"Loaded evaluation records: {len(records)}")
    print(f"Suggested profile: {args.out}")
    print(f"Parameter offsets: {profile.get('parameter_offsets', {})}")


if __name__ == "__main__":
    main()
