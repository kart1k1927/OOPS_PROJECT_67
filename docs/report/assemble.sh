#!/usr/bin/env bash
# Concatenate the report sections into one document for submission.
set -euo pipefail
cd "$(dirname "$0")/../.."

OUT=docs/report/I-ITSM-report.md

{
  cat docs/report/00-cover.md
  printf '\n\n---\n\n'
  cat docs/report/01-problem-analysis.md
  printf '\n\n---\n\n'
  cat docs/report/02-requirements.md
  printf '\n\n---\n\n# 3. System Architecture\n\n'
  tail -n +2 docs/diagrams/01-architecture.md
  printf '\n\n---\n\n# 4. UML Diagrams\n\n## 4.1 Use case\n\n'
  tail -n +2 docs/diagrams/02-use-case.md
  printf '\n\n## 4.2 Class diagram\n\n'
  tail -n +2 docs/diagrams/03-class-diagram.md
  printf '\n\n---\n\n'
  cat docs/report/03-technology.md
  printf '\n\n---\n\n# 6. Database Design\n\n'
  tail -n +2 docs/diagrams/04-er-diagram.md
  printf '\n\n---\n\n'
  cat docs/report/04-test-cases.md
  printf '\n\n---\n\n# 9. User Experience and Design System\n\n'
  tail -n +2 docs/design-system.md
} > "$OUT"

printf 'wrote %s\n' "$OUT"
printf '  %s lines, %s words\n' "$(wc -l < "$OUT")" "$(wc -w < "$OUT")"
printf '  %s mermaid diagrams\n' "$(grep -c '^```mermaid' "$OUT")"
