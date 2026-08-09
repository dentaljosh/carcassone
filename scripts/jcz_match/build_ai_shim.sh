#!/usr/bin/env bash
# Build the JCloisterZone AI shim (com.jcloisterzone.ai.*) against the prebuilt 5.x shaded Engine.jar.
#
# The JCZ clone is NOT modified and NOT rebuilt with maven; we only compile OUR sources against its jar.
# The jar is not vendored into this repo.
#
#   JCZ_JAR         path to the shaded Engine.jar   (default ~/jcz_spike/JCloisterZone/build/Engine.jar)
#   JCZ_AI_CLASSES  output directory for .class     (default ~/jcz_spike/ai_classes)
#
# Idempotent: the output dir is wiped and recreated on every run.
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/java"
JCZ_JAR="${JCZ_JAR:-$HOME/jcz_spike/JCloisterZone/build/Engine.jar}"
JCZ_AI_CLASSES="${JCZ_AI_CLASSES:-$HOME/jcz_spike/ai_classes}"

if [ ! -f "$JCZ_JAR" ]; then
    echo "ERROR: Engine.jar not found at $JCZ_JAR (set JCZ_JAR)" >&2
    exit 1
fi

rm -rf "$JCZ_AI_CLASSES"
mkdir -p "$JCZ_AI_CLASSES"

# --release 11 matches the 5.x pom (maven-compiler-plugin source/target 11).
mapfile -t SOURCES < <(find "$SRC_DIR" -name '*.java' | sort)
javac --release 11 -Xlint:-options -nowarn \
      -cp "$JCZ_JAR" -d "$JCZ_AI_CLASSES" "${SOURCES[@]}"

N=$(find "$JCZ_AI_CLASSES" -name '*.class' | wc -l)
echo "OK: built ${#SOURCES[@]} source files -> $N classes in $JCZ_AI_CLASSES"
echo "Run with: java -cp \"$JCZ_JAR:$JCZ_AI_CLASSES\" com.jcloisterzone.ai.AiEngine"
