# AGENTS.md

## Cursor Cloud specific instructions

This repo is a **static resume build pipeline**. `README.md` is the source of
truth; `build-resume.sh` (run via `npm run build`) renders it into
`dist/` as HTML (`index.html`), PDF, DOCX, plus copies of `resume.json` and
`llms.txt`. There is no long-running app server — the "app" is the generated
static site.

### Build / test / run
- Build: `npm run build` (alias for `./build-resume.sh`). Builds an Arial-based
  `assets/reference.docx`, syncs `resume.json` work section from `README.md`, then
  emits all formats into `dist/`.
- Test: `npm test` (`python3 tests/test_resume_outputs.py`). Tests assert on the
  contents of `dist/`, so **run `npm run build` first** or they skip/fail.
- Run/preview: serve the output, e.g. `python3 -m http.server 8080` from
  `dist/`, then open `index.html`.
- There is no lint step configured.

### Non-obvious gotchas
- **PDF requires WeasyPrint from `.venv`.** `build-resume.sh` looks for
  `.venv/bin/weasyprint`; without it the PDF step is silently skipped and the
  PDF tests fail. The startup update script provisions `.venv` with
  `weasyprint` + `pypdf`.
- **`npm run build` rewrites tracked `resume.json`** (refreshes `work[]` and
  `lastModified`). This shows up as a git diff after every build — revert it
  (`git checkout -- resume.json`) unless the change is intended.
- **DOCX uses Arial as a system font (not embedded).** `scripts/finalize-docx.py`
  repacks via `docx_utils.repack_opc` and adds widow/orphan paragraph controls.
  No font download or embedding step — Arial must exist on the build host for PDF
  (WeasyPrint uses system fontconfig).
- **`bedrock-playground` does not exist** in the repo (only a `.kiro/specs`
  design doc). The `build:playground`, `infra:plan`, and `infra:apply` scripts
  in `package.json` are aspirational and will fail — ignore them.
