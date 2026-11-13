# Execution access map

<!-- toc:start -->
**Table of contents**

- [Execution access map](#execution-access-map)
<!-- toc:end -->

Which observed interaction routes supported this implementation and repair?

```mermaid
flowchart LR
    Local["Local tools"] -->|"SSH Git"| GitHub["GitHub"]
    Local -->|"Authenticated SDK: verified cancellation"| GitHub
    Local -->|"Authenticated connector: failed job logs"| GitHub
    Local -->|"Public HTTPS: official contracts"| Docs["GitHub documentation"]
    GitHub -->|"Reviewed workflow execution"| CI["GitHub Actions: mediated execution"]
    CI -->|"Dependency installation"| Packages["PyPI and Helm distributions"]
    CI -->|"Configured runner"| GPU["Physical T4 execution"]
    CI -->|"Generated-only publication"| GitHub
```

Recorded utilization: **8 of 8 observed route classes (100%)** in this review
scope. CI and physical GPU edges include preceding PR17 runs. The reported GPU
structural-sparsity shard failed during compilation and its run was cancelled
with verified cancellation. The new matched comparison has not run on hosted
hardware. Publication edges describe the preceding generated-results path.

This is a bounded observation projection. The percentage of all known available
Sight routes is **unavailable**, because the complete instance-scoped inventory
cannot be read by the installed runtime. Historical CI reachability does not
provide direct runner SSH access or authorize new execution.
