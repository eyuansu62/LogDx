# Build the arXiv-ready PDF from paper.tex.
#
#   make pdf      → produces paper.pdf
#   make clean    → removes LaTeX aux files (keeps paper.pdf)
#   make distclean → removes everything including paper.pdf
#
# Requires:
#   - TeX Live (pdflatex + bibtex; tested with TeX Live 2026 / TinyTeX)
#   - The NeurIPS 2025 .sty file in this directory (committed to repo)
#   - ../references.bib in the parent reports/ directory

PAPER = paper

.PHONY: pdf clean distclean

pdf: $(PAPER).pdf

# Full 3-pass build: pdflatex → bibtex → pdflatex → pdflatex
# Needed for cross-references, citations, and TOC to converge.
$(PAPER).pdf: $(PAPER).tex ../references.bib neurips_2025.sty
	pdflatex -interaction=nonstopmode $(PAPER).tex
	bibtex $(PAPER)
	pdflatex -interaction=nonstopmode $(PAPER).tex
	pdflatex -interaction=nonstopmode $(PAPER).tex

clean:
	rm -f $(PAPER).aux $(PAPER).log $(PAPER).out $(PAPER).bbl $(PAPER).blg \
	      $(PAPER).toc $(PAPER).nav $(PAPER).snm $(PAPER).vrb \
	      $(PAPER).synctex.gz

distclean: clean
	rm -f $(PAPER).pdf
