**What:**

**Why:**

**How:**

**Validation:**

- [ ] Run the benchmarks before merging and link the completed run below.

From the repository checkout, replace `PR_BRANCH` and `PR_NUMBER` with this PR's
head branch and number, then run:

```sh
gh workflow run ci.yml --repo astrivant/hypothesis-helm --ref "PR_BRANCH" \
  -f refresh=true \
  -f benchmark-backend=gpu \
  -f pull-request="PR_NUMBER"
```

The GPU command uses the configured, paid `HH_GPU_RUNNER`. Select
`benchmark-backend=reference` or `benchmark-backend=cpu-vector` for a CPU refresh.

The workflow verifies the studies, commits updated graphs to the PR branch, and
reports the benchmark result on the PR. Add the completed workflow run link here:
