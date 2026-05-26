# LogDx-CI v1.2 — arXiv submission source

LaTeX source for the arXiv preprint, using the NeurIPS 2025 style
file in `preprint` mode.

## Files

- `paper.tex` — main LaTeX source (self-contained except for
  references.bib and neurips_2025.sty).
- `neurips_2025.sty` — NeurIPS 2025 style file (downloaded from
  <https://media.neurips.cc/Conferences/NeurIPS2025/Styles.zip>).
- `neurips_2025.tex`, `neurips_2025.pdf` — original template demo;
  retained for reference, not part of the build.
- `Makefile` — `make pdf` builds `paper.pdf`.
- The bibliography lives at `../references.bib`.

## Build

```bash
cd reports/paper
make pdf       # produces paper.pdf
```

Requires TeX Live (pdflatex + bibtex). Tested with TeX Live 2026 / TinyTeX.

## Markdown ↔ LaTeX dual sources

The repo carries TWO sources of the same content:

| File | Format | Used for |
|---|---|---|
| `reports/technical_report.md` | Markdown | GitHub readability + general browsing |
| `reports/paper/paper.tex`     | LaTeX    | arXiv submission |

These are intentionally kept in sync **manually**. When updating
findings or numbers, edit both. The Markdown is the source of truth
for casual readers; the LaTeX produces the citable PDF artifact.

## arXiv submission checklist

- [ ] Run `make pdf`; verify `paper.pdf` looks correct
- [ ] Spot-check tables render with all rows; figure embeds at the
      right size
- [ ] Verify Bowen Qin author email is current
- [ ] Verify `references.bib` BibTeX entries match canonical
      sources (see header comments in that file)
- [ ] Submit at <https://arxiv.org/submit>
- [ ] Categories: **cs.SE** (primary) + **cs.LG** (secondary)
- [ ] License: **CC BY 4.0** (matches the repo's data license)
- [ ] After moderation (~24h), update `RELEASE_NOTES_v1_2.md` and
      `CITATION.cff` with the arXiv ID
