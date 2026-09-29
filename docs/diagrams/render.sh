#!/usr/bin/env bash
# Render every PlantUML diagram in this folder to rendered/*.png.
# Uses `plantuml` if it is on PATH, otherwise `java -jar $PLANTUML_JAR`.
# Use case, class, activity, DFD and state diagrams also need Graphviz (`dot`).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if command -v plantuml >/dev/null 2>&1; then
    PLANTUML=(plantuml)
elif [ -n "${PLANTUML_JAR:-}" ] && [ -f "$PLANTUML_JAR" ]; then
    PLANTUML=(java -jar "$PLANTUML_JAR")
else
    echo "PlantUML not found: install it, or set PLANTUML_JAR=/path/to/plantuml.jar" >&2
    exit 1
fi

"${PLANTUML[@]}" -tpng -o rendered ./*.puml
echo "Rendered $(ls rendered/*.png | wc -l) diagrams into $(pwd)/rendered/"
