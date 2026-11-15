# Execution access map

<!-- toc:start -->
**Table of contents**

- [Execution access map](#execution-access-map)
<!-- toc:end -->

Which routes supported this implementation and local validation?

```mermaid
flowchart LR
    Tools["Local tools"] -->|"SSH Git fetch and branch publication"| GH["GitHub"]
    Tools -->|"Authenticated REST metadata"| GH
    Connector["Authenticated GitHub connector"] -->|"Merged review metadata"| GH
    Reader["Public documentation reader"] -->|"Official API contracts"| Docs["Python, Linux and PyTorch docs"]
    Tools -->|"Owned local subprocess"| CPU["Compiled CPU worker"]
    GH -.->|"Configured PR workflow; not started for this change"| Actions["GitHub Actions"]
    Actions -.->|"Configured test lane; not started for this change"| GPU["NVIDIA T4 runner"]
```

Five observed interaction route classes were used. Utilization as a percentage
of all known available Sight routes is **unavailable** because the installed
runtime cannot provide the complete instance-scoped inventory. Configured CI
edges are separate from observed execution and do not establish direct runner
SSH access. No benchmark or GPU workflow was dispatched for this change.
