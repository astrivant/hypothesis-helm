<!-- witful-work-graph:begin -->

```mermaid
---
config: {"flowchart": {"rankSpacing": 90, "subGraphTitleMargin": {"bottom": 24, "top": 0}}, "layout": "dagre", "theme": "base", "themeVariables": {"edgeLabelBackground": "#F8F9F4", "lineColor": "#647D8B", "primaryTextColor": "#243746"}}
---
flowchart TB
    subgraph n244210e48437b6556980a70249a99369934a352429034cef9d7bd253b3bf2c01["`project: hypothesis-helm`"]
        nf38c764c8aa00b6578f4254a4dc6d9b50f88fa926e270ea7859bd1b707cd8662["branch: revert-16-revert-15-feat/compiled-backends (active)"]
        n0d6e4079e36703ebd37c00722f5891d28b0e2811dc114b129215123adcce3605["branch: main"]
        n3c93076a86ee1c8b6873a6751eb60457ba031183a4b2a44ac02a54e59bec2bdb["review #35;15: Original compiled backends (merged) (merged)"]
        n0543abedd4f1b3a7806bca5fb14d97ea0943afb986f0df98f945c924d71294e5["review #35;16: Revert of PR15 (merged) (merged)"]
        nc97ace4c8fef2cee8fa0f3c9f52aab18dbd4f42438afe362ffb8f75ce4c04b84["review #35;17: 17 (open#59; review)"]
    end
    nf38c764c8aa00b6578f4254a4dc6d9b50f88fa926e270ea7859bd1b707cd8662 -->|based on| n0d6e4079e36703ebd37c00722f5891d28b0e2811dc114b129215123adcce3605
    nc97ace4c8fef2cee8fa0f3c9f52aab18dbd4f42438afe362ffb8f75ce4c04b84 -->|evidences| nf38c764c8aa00b6578f4254a4dc6d9b50f88fa926e270ea7859bd1b707cd8662
    nc97ace4c8fef2cee8fa0f3c9f52aab18dbd4f42438afe362ffb8f75ce4c04b84 ---|correlates| n3c93076a86ee1c8b6873a6751eb60457ba031183a4b2a44ac02a54e59bec2bdb
    nc97ace4c8fef2cee8fa0f3c9f52aab18dbd4f42438afe362ffb8f75ce4c04b84 ---|correlates| n0543abedd4f1b3a7806bca5fb14d97ea0943afb986f0df98f945c924d71294e5
    click nf38c764c8aa00b6578f4254a4dc6d9b50f88fa926e270ea7859bd1b707cd8662 href "https://github.com/astrivant/hypothesis-helm/tree/revert-16-revert-15-feat/compiled-backends" "Open recorded work" _blank
    click n0d6e4079e36703ebd37c00722f5891d28b0e2811dc114b129215123adcce3605 href "https://github.com/astrivant/hypothesis-helm/tree/main" "Open recorded work" _blank
    click n3c93076a86ee1c8b6873a6751eb60457ba031183a4b2a44ac02a54e59bec2bdb href "https://github.com/astrivant/hypothesis-helm/pull/15" "Open recorded work" _blank
    click n0543abedd4f1b3a7806bca5fb14d97ea0943afb986f0df98f945c924d71294e5 href "https://github.com/astrivant/hypothesis-helm/pull/16" "Open recorded work" _blank
    click nc97ace4c8fef2cee8fa0f3c9f52aab18dbd4f42438afe362ffb8f75ce4c04b84 href "https://github.com/astrivant/hypothesis-helm/pull/17" "Open recorded work" _blank
    classDef work fill:#F8F9F4,stroke:#647D8B,color:#243746
    class nf38c764c8aa00b6578f4254a4dc6d9b50f88fa926e270ea7859bd1b707cd8662 work
    class n0d6e4079e36703ebd37c00722f5891d28b0e2811dc114b129215123adcce3605 work
    class n3c93076a86ee1c8b6873a6751eb60457ba031183a4b2a44ac02a54e59bec2bdb work
    class n0543abedd4f1b3a7806bca5fb14d97ea0943afb986f0df98f945c924d71294e5 work
    style n244210e48437b6556980a70249a99369934a352429034cef9d7bd253b3bf2c01 fill:#F8F9F4,stroke:#829B85,color:#243746
    class nc97ace4c8fef2cee8fa0f3c9f52aab18dbd4f42438afe362ffb8f75ce4c04b84 work
    linkStyle 0 stroke:#829B85,color:#243746
    linkStyle 1 stroke:#647D8B,color:#243746
    linkStyle 2 stroke:#B77E79,color:#243746
    linkStyle 3 stroke:#B77E79,color:#243746
```

Containment shows ownership; arrows name recorded relationships.

Associated work:

- [branch: revert\-16\-revert\-15\-feat/compiled\-backends](<https://github.com/astrivant/hypothesis-helm/tree/revert-16-revert-15-feat/compiled-backends>)
- [branch: main](<https://github.com/astrivant/hypothesis-helm/tree/main>)
- [review \#15: Original compiled backends \(merged\)](<https://github.com/astrivant/hypothesis-helm/pull/15>)
- [review \#16: Revert of PR15 \(merged\)](<https://github.com/astrivant/hypothesis-helm/pull/16>)
- [project: hypothesis\-helm](<https://github.com/astrivant/hypothesis-helm>)
- [review \#17: 17](<https://github.com/astrivant/hypothesis-helm/pull/17>)

<!-- witful-work-graph:end -->
