# eOCR Agent Instructions

## Repository baseline

Follow the selective scaffold and engineering rules resolved for `agents_template` in [issue #11](https://github.com/guility/eOCR/issues/11). Keep the visible root allowlist (`README.md`, this file, `.gitignore`, optional `.gitlab-ci.yml`, `deploy/`, `src/`, `docs/`, `scripts/`) plus eOCR's documented root exceptions `GLOSSARY.md` and generated `skills-lock.json`; `.agents/` is hidden tooling. Keep at most 8 files and 5 subdirectories directly in any directory. Hand-maintained source, tests, scripts, configuration, Dockerfiles, Compose files, and CI files must be at most 300 lines, with at least 95% at most 100 lines. Put Dockerfiles and Compose files under `deploy/`, and tests under `src/tests/`.

Apply the required coverage, mutation, lint, security, and acceptance gates to implementation work using the language-specific template from `agents-template-langs`. Do not add a sample application or unrelated scaffold.

## Agent skills

### Issue tracker

Track planning issues in GitHub Issues for `guility/eOCR`. Use `gh` for tracker operations and follow the repository conventions in [docs/agents/issue-tracker.md](docs/agents/issue-tracker.md).

### Domain docs

Treat this as a single-context project. Read relevant domain terms and decisions from `GLOSSARY.md` and `docs/adr/`; follow [docs/agents/domain.md](docs/agents/domain.md).
