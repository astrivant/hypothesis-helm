"""
Compatibility entry point for the installed benchmarking package.
"""

from hypothesis_helm.benchmarking.benchmark_matrix import main

if __name__ == "__main__":
    raise SystemExit(main())
