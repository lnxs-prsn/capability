"""Invoke with Python and an explicit contribution directory, from any cwd."""
import argparse
import json
from standard import check_contribution
from standard.definition import NOTICE


def main():
    parser = argparse.ArgumentParser(description=NOTICE)
    parser.add_argument('contribution', help='Path to a contribution directory')
    parser.add_argument('--json', action='store_true', help='Emit the full machine-readable result')
    args = parser.parse_args()
    result = check_contribution(args.contribution)
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        print(NOTICE)
        print('Presence complete: ' + str(result['presence_complete']))
        for check in result['checks']:
            print('{state}: {field}: {message}'.format(**check))
        print('Human review remains required:')
        for item in result['review_required']:
            print('- ' + item['message'])
    return 2 if result['read_error'] else (0 if result['presence_complete'] else 1)


if __name__ == '__main__':
    raise SystemExit(main())
