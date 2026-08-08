#!/usr/bin/env bash
# Forward workspace-root Gradle invocations to the MagicSpells project.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/MagicSpells"
exec ./gradlew "$@"
