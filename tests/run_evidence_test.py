"""Run a qualification command, or explicitly skip unavailable local evidence."""
import argparse
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test-name', required=True)
    parser.add_argument('--evidence-variable', required=True)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        parser.error('a qualification command is required after --')
    if not args.evidence or not Path(args.evidence).is_file():
        print(f'SKIP {args.test_name}: local evidence file unavailable: {args.evidence!r}. '
              f'Restore the owned capture or configure -D{args.evidence_variable}=<file>. '
              'See docs/BUILD.md for local-evidence qualification.', flush=True)
        return 77
    # Existing but invalid evidence belongs to the original validator. Its output
    # and exit status must remain visible; it must never become a missing-file skip.
    return subprocess.call(command)


if __name__ == '__main__':
    raise SystemExit(main())
