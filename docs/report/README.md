# Project report

The report is written in sections so more than one person can edit at a time.
`assemble.sh` concatenates them in order into a single document for submission.

| File | Deliverable in the brief |
|---|---|
| `00-cover.md` | Cover page and contents |
| `01-problem-analysis.md` | 1. Problem Analysis |
| `02-requirements.md` | 2. Requirements Specification |
| `03-technology.md` | 5. Technology Stack |
| `04-test-cases.md` | 8. Testing |
| `../diagrams/01-architecture.md` | 3. System Architecture |
| `../diagrams/02-use-case.md` | 4. UML, use case |
| `../diagrams/03-class-diagram.md` | 4. UML, class diagram |
| `../diagrams/04-er-diagram.md` | 7. Database Design |
| `../design-system.md` | Supports 6. Source Code and the user experience marks |

Deliverable 6, source code, is the repository itself.
Deliverable 9, the demo, is the video. The script is in `docs/presentation.md`.

## Producing the PDF

```sh
bash docs/report/assemble.sh
```

That writes `docs/report/I-ITSM-report.md`. Then either:

**Pandoc**, if it is installed:

```sh
pandoc docs/report/I-ITSM-report.md -o I-ITSM-report.pdf \
  --toc --pdf-engine=xelatex -V geometry:margin=2cm
```

**Or**, with no tooling at all: open `I-ITSM-report.md` on GitHub, print to PDF
from the browser. Mermaid diagrams render on GitHub, so this is the quickest
route and it is what we recommend with little time left.

Either way, check that the four diagrams rendered before submitting. If a
diagram does not render in the PDF, paste its fenced block into
<https://mermaid.live>, export PNG, and insert the image.
