#!/usr/bin/env bash
# Run saved suites through the real Helm CLI in local GNU Parallel shards.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: hypothesis-helm-benchmark shards [options] SUITE [-- RUN_OPTIONS...]

  --shards N       Number of concurrent application shards (default: 1).
  --output-dir D   New directory for job timings, stdout/stderr and reports.
  -h, --help       Show this help.

RUN_OPTIONS are passed literally to `helm hypothesis run`. The wrapper owns
--shard, --jobs, --artifact-dir, --cache-dir, --no-cache, --rerun and --seed.
Each shard uses one worker, seed 0, no path-result cache and --rerun all.
The default output is a fresh directory under .cache/benchmarks/local-shards/.
EOF
}

die() {
  printf '%s\n' "$*" >&2
  exit 2
}
shards=1
output=
suite=
while (($#)); do
  case "$1" in
    --shards | --output-dir)
      (($# >= 2)) || die "Missing value for $1"
      if [[ $1 == --shards ]]; then shards=$2; else output=$2; fi
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*) die "Unknown wrapper option: $1 (put run options after --)" ;;
    *)
      [[ -z $suite ]] || die "Supply exactly one suite before --"
      suite=$1
      shift
      ;;
  esac
done
[[ -n $suite ]] || die "A saved suite is required; see --help"
[[ $shards =~ ^[1-9][0-9]*$ && ${#shards} -le 4 ]] || die "--shards must be 1..9999"
for arg in "$@"; do
  case "$arg" in
    --shard* | --jobs* | -j* | --artifact* | --cache-dir* | --no-cache* | --rerun* | --seed*)
      die "Benchmark-controlled option: $arg"
      ;;
  esac
done
# A dedicated replacement token prevents GNU Parallel from interpreting literal {}.
for arg in "$suite" "$output" "$@"; do
  [[ $arg != *'__HH_SHARD_INDEX__'* ]] || die "Reserved token in argument: __HH_SHARD_INDEX__"
done
command -v parallel >/dev/null || die "Install GNU Parallel: brew bundle, or apt-get install parallel"
version=$(parallel --version)
[[ $version == GNU\ parallel* ]] || die "The parallel executable must be GNU Parallel"
command -v helm >/dev/null || die "Helm and the hypothesis plugin must be installed"
if [[ -n $output ]]; then
  mkdir -p "$(dirname "$output")"
  mkdir "$output" || die "--output-dir must be a new directory"
else
  mkdir -p .cache/benchmarks/local-shards
  output=$(mktemp -d .cache/benchmarks/local-shards/run-XXXXXXXX)
fi
indices=()
for ((index = 1; index <= shards; index++)); do indices+=("$index"); done
printf 'Running %s local shards; measurements: %s\n' "$shards" "$output" >&2
# --plain ignores personal Parallel profiles; --halt never completes every shard
# while GNU Parallel still returns nonzero when any job fails.
exec parallel --plain --term-seq TERM,10000,KILL,1000 --jobs "$shards" --halt never --quote \
  --joblog "$output/joblog.tsv" --results "$output/parallel" \
  --replace '__HH_SHARD_INDEX__' \
  helm hypothesis run "$suite" "$@" \
  --shard "__HH_SHARD_INDEX__/$shards" --jobs 1 --seed 0 \
  --no-cache --rerun all --artifact-dir "$output/reports" \
  ::: "${indices[@]}"
