"""
Compatibility entry point for the installed benchmarking package.
"""

from hypothesis_helm.benchmarking.generate_benchmark_chart import main

if __name__ == "__main__":
    raise SystemExit(main())
