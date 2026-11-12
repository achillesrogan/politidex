#!/usr/bin/env bash
# Re-read official state results, rebuild election claims, and re-verify them live.
# Counts change until certification, so repeat (max 3 rounds) until no election claim is blocked.
set -euo pipefail
cd "$(dirname "$0")"
for round in 1 2 3; do
  python3 elections.py "$@"
  python3 elections_build.py
  mkdir -p ../data/build
  python3 verify.py --stage elections | tee ../data/build/verify-elections.log
  blocked=$(python3 -c "import json;d=json.load(open('../data/build/site/claims.json'))['claims'];print(sum(1 for k,c in d.items() if k.startswith('e_') and c['status']!='verified'))")
  echo "round $round: election claims not verified = $blocked"
  [ "$blocked" = "0" ] && exit 0
done
exit 1
