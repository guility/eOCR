# Agent resources for eOCR

## Installed workflow

Wayfinder and its supporting skills are installed under `.agents/skills/`. The selected set covers tracker setup, grilling and domain modeling, research and prototyping, handoff, and the later spec-to-tickets steps. The map is for decisions; implementation starts after the map is resolved. See the [Wayfinder guide](https://www.aihero.dev/skills-wayfinder).

GitHub Issues is the project tracker. The `gh` CLI is available and authenticated; the GitHub MCP connection is also available in Codex. Wayfinder labels have been created in `guility/eOCR`. Tracker operations are documented in `docs/agents/issue-tracker.md`.

The active Wayfinder map is [OCR PDF→DOCX: маршрут к работающему продукту](https://github.com/guility/eOCR/issues/1). Resolve its decision tickets one at a time; the map records context pointers, not implementation details.

## OCR resources to evaluate

- **Model research:** the `hf-cli` skill is available in this Codex environment. Add it to the project if the selected model, weights, or evaluation datasets are hosted on Hugging Face.
- **PDF and DOCX quality checks:** the `pdf` and `documents` skills are available in this Codex environment. Decide whether to vendor them after the fixture and rendering workflow is defined.
- **OCR evaluation:** create a small project skill after agreeing on representative PDF fixtures and metrics for text, reading order, layout, runtime, and memory. Keep source documents and expected outputs versioned with clear provenance.
- **Lean and Rust:** add language-specific guidance through the `lean` and `rust` packages in `agents-template-langs`, as planned. Keep OCR evaluation conventions in this repository rather than either language package.

No additional MCP is selected yet. GitHub MCP plus `gh` covers planning; model and document workflows should be selected after comparing OCR candidates and the local inference interface.

## Skills lockfile and update workflow

The canonical project lock is the root `skills-lock.json`; the Vercel Skills CLI reads and writes it there. It is the second eOCR-specific root allowlist extension after `GLOSSARY.md`, and is excluded from the baseline's manually maintained file-size limits as a generated lockfile. Keep the reviewed skill copies under `.agents/skills/` and commit them together with the lock. Do not hand-edit the lock.

Pin the CLI to `skills@1.7.6` and use Node.js `>=22.20.0` (the package engine requirement). The currently configured Node 22.14.0 must be upgraded before running this pinned CLI.

- After these project files are committed, a clean checkout contains the skill files; no installation is needed.
- Restore missing skill files: `npx --yes skills@1.7.6 experimental_install --frozen-lockfile`. This command is experimental; it verifies restored contents against the lock hashes and fails rather than silently changing the lock.
- Check for upstream updates: `npx --yes skills@1.7.6 check`.
- Update intentionally: `npx --yes skills@1.7.6 update -p`, review the diff in `.agents/skills/` and `skills-lock.json`, then commit both together. Upgrade the pinned CLI only as a separately reviewed change.

Never auto-update project skills in CI. The lock and checked-in copies provide a stable working tree; restoration is a recovery operation. See the [Skills CLI v1.7.6 commands](https://github.com/vercel-labs/skills/blob/v1.7.6/docs/commands.md), [lockfile implementation](https://github.com/vercel-labs/skills/blob/v1.7.6/src/local-lock.ts), and [CLI package metadata](https://github.com/vercel-labs/skills/blob/v1.7.6/package.json).
