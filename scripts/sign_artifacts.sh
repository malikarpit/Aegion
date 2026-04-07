#!/bin/bash
set -e

# Aegion Artifact Signing Script
# Generates SHA256 checksums for release artifacts.

ARTIFACTS_DIR=${1:-"./dist"}
OUTPUT_FILE="${ARTIFACTS_DIR}/SHA256SUMS"

echo "🔐 Signing artifacts in ${ARTIFACTS_DIR}..."

if [ ! -d "$ARTIFACTS_DIR" ]; then
    echo "❌ Artifacts directory ${ARTIFACTS_DIR} not found."
    exit 1
fi

# Clear old file
rm -f "$OUTPUT_FILE"

# Generate checksums for specific file types
find "$ARTIFACTS_DIR" -type f \( -name "*.vsix" -o -name "*.tar.gz" -o -name "*.zip" \) -print0 | xargs -0 shasum -a 256 >> "$OUTPUT_FILE"

echo "✅ Checksums generated at ${OUTPUT_FILE}:"
cat "$OUTPUT_FILE"
