# Build + package the arXiv-ready PDF from paper.tex.
#
#   make pdf      → produces paper.pdf
#   make zip      → produces arxiv_submission.zip (upload this to arxiv)
#   make clean    → removes LaTeX aux files (keeps paper.pdf + zip)
#   make distclean → removes everything including paper.pdf + zip
#
# Requires:
#   - TeX Live (pdflatex + bibtex; tested with TeX Live 2026 / TinyTeX)
#   - neurips_2025.sty (committed in this directory)
#   - references.bib (symlinked from ../references.bib)
#   - cost_quality_pareto.png (symlinked from ../../docs/figures/...)

PAPER = paper

.PHONY: pdf zip clean distclean

pdf: $(PAPER).pdf

# Full 3-pass build: pdflatex → bibtex → pdflatex → pdflatex
# Needed for cross-references, citations, and TOC to converge.
$(PAPER).pdf: $(PAPER).tex references.bib cost_quality_pareto.png neurips_2025.sty
	pdflatex -interaction=nonstopmode $(PAPER).tex
	bibtex $(PAPER)
	pdflatex -interaction=nonstopmode $(PAPER).tex
	pdflatex -interaction=nonstopmode $(PAPER).tex

# Package files for arXiv source upload. arXiv compiles from a flat
# directory, so we deref symlinks (`zip` default behavior) and bundle
# the .bbl (so arxiv doesn't need to rerun bibtex). Upload the
# resulting arxiv_submission.zip to arxiv.org/submit.
zip: $(PAPER).pdf
	rm -f arxiv_submission.zip
	zip arxiv_submission.zip \
	    $(PAPER).tex \
	    $(PAPER).bbl \
	    references.bib \
	    cost_quality_pareto.png \
	    neurips_2025.sty
	@echo
	@echo "Created arxiv_submission.zip:"
	@unzip -l arxiv_submission.zip | tail -n +2

clean:
	rm -f $(PAPER).aux $(PAPER).log $(PAPER).out $(PAPER).blg \
	      $(PAPER).toc $(PAPER).nav $(PAPER).snm $(PAPER).vrb \
	      $(PAPER).synctex.gz
# Note: $(PAPER).bbl is INTENTIONALLY kept around so `make zip` can
# bundle it for arxiv. It's regenerated on `make pdf` anyway.

distclean: clean
	rm -f $(PAPER).pdf $(PAPER).bbl arxiv_submission.zip
