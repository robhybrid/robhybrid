# AGENTS.md

## Cursor Cloud specific instructions

This repo is a **resume / portfolio static-site generator**. `build-resume.sh` (run via
`npm run build`) reads `README.md` and regenerates multiple outputs into `dist/`:
HTML (`index.html`), PDF, DOCX, `resume.json` (JSON Resume), and `llms.txt`. Editing
`README.md` and rebuilding is the core workflow. There is no long-running app server;
the "app" is the generated site in `dist/`.

### Services / commands
- Build: `npm run build` (or `./build-resume.sh`). Downloads Roboto fonts the first
  time (needs network), syncs `resume.json`, and emits all formats into `dist/`.
- Test: `npm test` runs `python3 tests/test_resume_outputs.py` (regression checks on
  the built `dist/` outputs). **Run the build first** — tests skip if `dist/` is missing.
  Use the venv interpreter so `pypdf` is available: `.venv/bin/python tests/test_resume_outputs.py`.
- Preview the generated site: `python3 -m http.server 8099 --directory dist` then open
  `http://localhost:8099/index.html`.

### Non-obvious caveats
- **PDF generation uses WeasyPrint from a local venv** (`.venv/bin/weasyprint`), which
  `build-resume.sh` auto-detects. The venv is created by the startup update script.
- **`npm run build` rewrites `resume.json`'s `meta.lastModified` to today's date.** This
  shows up as a one-line diff in `git status` after every build; revert it
  (`git checkout resume.json`) if you don't intend to commit a content change.
- **Roboto font fix (already applied in the snapshot):** The VM's `/etc/fonts/local.conf`
  shipped a hard alias mapping `Roboto` → `Noto Sans` (`binding="strong"`). That alias
  silently overrides even WeasyPrint's `@font-face`, causing the PDF to embed Noto Sans
  and `test_pdf_embeds_roboto` to FAIL. The fix was to remove that `<match>` block from
  `/etc/fonts/local.conf`, install the Roboto TTFs under
  `/usr/share/fonts/truetype/roboto/`, and run `sudo fc-cache -f`. If `fc-match Roboto`
  ever returns "Noto Sans" again (e.g. a fresh VM without the snapshot change), re-apply
  that fix before trusting the PDF font test.
- `bedrock-playground/` referenced by the `build:playground` / `infra:*` npm scripts does
  not exist on this branch, so those scripts are out of scope here.
