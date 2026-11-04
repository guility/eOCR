# Hardware-backed OCR regression and CI

**Checked 2026-11-05.** This recommendation follows the product protocol in [#26](https://github.com/guility/eOCR/issues/26) and the accepted score in [#17](https://github.com/guility/eOCR/issues/17).

## Recommendation

- Run ordinary pull-request checks on GitHub-hosted CPU runners: Lean proofs/build, Rust checks, schema/manifest validation, and small CPU smoke checks. Use read-only token permissions by default, pin Actions by full commit SHA, and keep production model weights out of routine PR jobs.
- Run GPU quality/performance comparisons manually in the pinned Linux/CUDA container on the trusted RTX 5090 host. The runner input must be a trusted commit SHA; the job must not execute code from a fork PR or expose secrets. Keep this lane informational until #26 calibrates and freezes its evaluation protocol.
- Do not register the developer workstation as a persistent self-hosted runner for the public repository. GitHub warns that self-hosted runners lack the clean-VM guarantee of hosted runners and can be persistently compromised by untrusted workflow code; it says they should almost never be used for public repositories. A container pins software and packages the workload, but does not make an untrusted workflow safe to run on a host that holds the Docker daemon or GPU.
- If later automation is worth the operational cost, provision a dedicated, isolated GPU runner for trusted commits only. Restrict actors and events with GitHub Actions execution protections, use a separate runner group, process one job per clean disposable environment, and restore/reimage the host between jobs. Do not attach this runner to arbitrary public pull-request events. GitHub supports runner groups and labels for routing hardware-specific jobs.

## Reproducibility record

Pin the evaluation container by immutable image digest, model revisions and weight hashes, Python packages, preprocessing/prompts, OCR backend, precision and batch/token settings, PDF rasterizer, downstream conversion, and DOCX renderer. Record the source commit, corpus manifest and per-page hashes/licences, OS image, GPU model, driver/runtime/toolkit versions, and `nvidia-smi` output. Docker and NVIDIA document the `--gpus` route for exposing a selected GPU to a container; the host driver remains part of the measured environment.

Each run should produce a machine-readable environment/config manifest and JSON metrics plus a human-readable summary: score components and raw per-page/document/language/PDF-stratum values, missing dimensions and failure reasons, end-to-end latency, host/GPU peak memory, and rendered DOCX comparisons. Retain only license-cleared artifacts; do not publish source PDFs, model weights, or real signatures by default.

## Score and gating

The accepted #17 weights are text 25%, formulas 15%, layout 15%, reading order 10%, technical graphics 10%, signatures 5%, end-to-end p95 latency 10%, and peak host/GPU memory 10%. Required missing components make the run incomplete; weights are not renormalized. Keep totals diagnostic until #26 calibrates resource budgets and the score cutoff on a pilot and freezes them before holdout evaluation. Then the same complete, pinned GPU run can become a regression gate against that frozen protocol.

A run on one RTX 5090 is a reference-profile regression, not a guarantee for other GPUs, drivers, or power/thermal conditions. Report variance and avoid comparing measurements across different hardware/runtime profiles.

## Sources

- [GitHub Actions secure-use guidance: self-hosted runners](https://docs.github.com/en/actions/reference/security/secure-use#hardening-for-self-hosted-runners)
- [GitHub Actions execution protections](https://docs.github.com/en/actions/concepts/about-actions-policies)
- [GitHub: route hardware-specific jobs using runner groups and labels](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/use-in-a-workflow)
- [Docker GPU access](https://docs.docker.com/engine/containers/gpu/)
- [NVIDIA Container Toolkit Docker configuration](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html)
- [Docker: pin base image versions](https://docs.docker.com/build/building/best-practices/#pin-base-image-versions)
