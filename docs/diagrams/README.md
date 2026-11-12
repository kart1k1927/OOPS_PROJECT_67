# Diagrams

Four diagrams, written as Mermaid so they render on GitHub, stay in version
control and can be edited without a drawing tool.

| File | Deliverable |
|---|---|
| `01-architecture.md` | System Architecture |
| `02-use-case.md` | UML Use Case Diagram |
| `03-class-diagram.md` | UML Class Diagram |
| `04-er-diagram.md` | Database Design, ER diagram |

## Getting them into the PDF

GitHub renders these in the browser, so the quickest route is to open each file
on GitHub and screenshot the rendered diagram.

For higher resolution, paste the fenced block into <https://mermaid.live> and
export SVG or PNG. SVG stays sharp at any zoom, which matters for the class
diagram.

To render them locally instead:

```sh
npm install -g @mermaid-js/mermaid-cli
mmdc -i docs/diagrams/03-class-diagram.md -o class-diagram.png -w 2400
```
