# Agent resources for eOCR

## Installed workflow

Wayfinder and its supporting skills are installed under `.agents/skills/`. The selected set covers tracker setup, grilling and domain modeling, research and prototyping, handoff, and the later spec-to-tickets steps. The map is for decisions; implementation starts after the map is resolved. See the [Wayfinder guide](https://www.aihero.dev/skills-wayfinder).

GitHub Issues is the project tracker. The `gh` CLI is available and authenticated; the GitHub MCP connection is also available in Codex. Wayfinder labels have been created in `guility/eOCR`. Tracker operations are documented in `docs/agents/issue-tracker.md`.

The active Wayfinder map is [OCR PDF→DOCX: маршрут к работающему продукту](https://github.com/guility/eOCR/issues/1). Resolve its decision tickets one at a time; the map records context pointers, not implementation details.

## OCR-specific agent resources

- **Hugging Face artifacts:** the selected `PaddlePaddle/PaddleOCR-VL-1.6` model and MDPBench are hosted on Hugging Face. Use the host `hf-cli` skill or a container-pinned Hub client for public model cards, dataset metadata, and downloads. Pin the model revision already used by the GPU smoke (`c5630abae1d940eafe0697512a0325494b02ab42`) and keep weights in an ignored cache, never in Git. The `hf` host executable currently fails because its wrapper points at a missing Python 3.13 installation; use the pinned container or repair that environment before relying on the host CLI. Sources: [PaddleOCR-VL-1.6 model card](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6), [MDPBench](https://huggingface.co/datasets/Delores-Lin/MDPBench), [GPU smoke and resolved revision](https://github.com/guility/eOCR/issues/19#issuecomment-6620876329).
- **PaddleOCR MCP:** PaddleOCR publishes an MCP server that lists PaddleOCR-VL-1.6 and local inference, but also offers remote API modes. The local setup requires the PaddleOCR document-parsing extras and an inference engine; the `paddleocr_vl` tool returns Markdown rather than eOCR's structured page, graphic, signature, and DOCX contract. Do not enable it as the product's primary interface. Keep it as an optional isolated development harness after the full parser stack is available, configured for `local` inference (or a localhost self-hosted service) only. Source: [PaddleOCR MCP documentation](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/integrations/mcp_server.en.md).
- **MCP catalog:** the current catalog search found no PaddleOCR or Hugging Face server to enable. GitHub MCP plus `gh` remains the project-tracker integration. The PaddleOCR server is a separately run local process, not an available managed connector.
- **PDF and DOCX review:** the `pdf` and `documents` skills are available in this Codex host for visual review. Keep reproducible rendering and validation in the containerized project tools rather than copying host-specific skills into the repository.
- **OCR evaluation:** retain the corpus, PAGE XML profile, sidecars, and validation scripts in this repository. A separate evaluation skill can be added after the acceptance score and thresholds are resolved.
- **Lean and Rust:** add language-specific guidance through the `lean` and `rust` packages in `agents-template-langs`, as planned. Keep OCR evaluation conventions in this repository rather than either language package.

## Skills lockfile and update workflow

The canonical project lock is the root `skills-lock.json`; the Vercel Skills CLI reads and writes it there. It is the second eOCR-specific root allowlist extension after `GLOSSARY.md`, and is excluded from the baseline's manually maintained file-size limits as a generated lockfile. Keep the reviewed skill copies under `.agents/skills/` and commit them together with the lock. Do not hand-edit the lock.

Pin the CLI to `skills@1.7.6` and use Node.js `>=22.20.0` (the package engine requirement). The Windows host was verified on 2026-11-04 with Node.js `v26.13.0`, which meets the requirement.

- After these project files are committed, a clean checkout contains the skill files; no installation is needed.
- Restore missing skill files: `npx --yes skills@1.7.6 experimental_install --frozen-lockfile`. This command is experimental; it verifies restored contents against the lock hashes and fails rather than silently changing the lock.
- Check for upstream updates: `npx --yes skills@1.7.6 check`.
- Update intentionally: `npx --yes skills@1.7.6 update -p`, review the diff in `.agents/skills/` and `skills-lock.json`, then commit both together. Upgrade the pinned CLI only as a separately reviewed change.

Never auto-update project skills in CI. The lock and checked-in copies provide a stable working tree; restoration is a recovery operation. See the [Skills CLI v1.7.6 commands](https://github.com/vercel-labs/skills/blob/v1.7.6/docs/commands.md), [lockfile implementation](https://github.com/vercel-labs/skills/blob/v1.7.6/src/local-lock.ts), and [CLI package metadata](https://github.com/vercel-labs/skills/blob/v1.7.6/package.json).
