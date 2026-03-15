#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────
# AG-001: Aegion TypeScript Client Generator
#
# Modes (--mode flag):
#   manual              – Skip generation entirely (use hand-written client)
#   automatic           – Generate and overwrite src/api/generated/
#   automatic-with-review – Generate into .tmp/, show diff, prompt user
#
# Usage:
#   ./scripts/generate-client.sh                       # default: automatic-with-review
#   ./scripts/generate-client.sh --mode automatic
#   ./scripts/generate-client.sh --mode manual
#   ./scripts/generate-client.sh --backend-url http://myhost:8000
# ────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
GEN_DIR="$PROJECT_DIR/src/api/generated"
TMP_DIR="$PROJECT_DIR/.tmp/generated-client"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
MODE="automatic-with-review"

# ── Parse arguments ──
while [[ $# -gt 0 ]]; do
  case $1 in
    --mode)       MODE="$2"; shift 2 ;;
    --backend-url) BACKEND_URL="$2"; shift 2 ;;
    *)            echo "Unknown arg: $1"; exit 1 ;;
  esac
done

echo "╔══════════════════════════════════════════════╗"
echo "║  Aegion Client Generator  (mode: $MODE)"
echo "╚══════════════════════════════════════════════╝"

# ── Manual mode: do nothing ──
if [[ "$MODE" == "manual" ]]; then
  echo "ℹ  Mode is 'manual' — skipping generation."
  exit 0
fi

# ── Fetch OpenAPI spec ──
SPEC_FILE="$TMP_DIR/openapi.json"
mkdir -p "$TMP_DIR"

echo "→ Fetching OpenAPI spec from $BACKEND_URL/openapi.json …"
if ! curl -sf "$BACKEND_URL/openapi.json" -o "$SPEC_FILE"; then
  echo "✗ Could not reach $BACKEND_URL/openapi.json"
  echo "  Make sure the backend is running: cd aegion-backend && uvicorn app.main:app"
  exit 1
fi
echo "✓ Spec saved to $SPEC_FILE"

# ── Generate TypeScript types from spec ──
TYPES_FILE="$TMP_DIR/types.ts"
ENDPOINTS_FILE="$TMP_DIR/endpoints.ts"

echo "→ Generating TypeScript types …"

# Use a lightweight Python script to parse the spec (no extra deps needed)
python3 - "$SPEC_FILE" "$TYPES_FILE" "$ENDPOINTS_FILE" << 'PYEOF'
import json, sys, re

spec_path, types_path, endpoints_path = sys.argv[1], sys.argv[2], sys.argv[3]

with open(spec_path) as f:
    spec = json.load(f)

schemas = spec.get("components", {}).get("schemas", {})
paths   = spec.get("paths", {})

# ── Generate types.ts ──
lines = [
    "// Auto-generated from OpenAPI spec — DO NOT EDIT MANUALLY",
    f"// Generated at: {__import__('datetime').datetime.now().isoformat()}",
    f"// Source: {spec['info']['title']} v{spec['info']['version']}",
    "",
]

def ts_type(schema_ref):
    """Convert JSON Schema type to TS type."""
    if "$ref" in schema_ref:
        return schema_ref["$ref"].rsplit("/", 1)[-1]
    t = schema_ref.get("type", "unknown")
    fmt = schema_ref.get("format", "")
    if t == "string":
        enum = schema_ref.get("enum")
        if enum:
            return " | ".join(f"'{v}'" for v in enum)
        return "string"
    if t == "integer" or t == "number":
        return "number"
    if t == "boolean":
        return "boolean"
    if t == "array":
        items = schema_ref.get("items", {})
        return f"{ts_type(items)}[]"
    if t == "object":
        additional = schema_ref.get("additionalProperties")
        if additional:
            return f"Record<string, {ts_type(additional)}>"
        return "Record<string, unknown>"
    if "anyOf" in schema_ref:
        parts = [ts_type(s) for s in schema_ref["anyOf"] if s.get("type") != "null"]
        null = any(s.get("type") == "null" for s in schema_ref["anyOf"])
        result = " | ".join(parts) if parts else "unknown"
        return f"{result} | null" if null else result
    return "unknown"

for name, schema in sorted(schemas.items()):
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    if not props:
        # It might be an enum
        enum = schema.get("enum")
        if enum:
            lines.append(f"export type {name} = {' | '.join(repr(v) for v in enum)};")
            lines.append("")
            continue
        lines.append(f"export type {name} = Record<string, unknown>;")
        lines.append("")
        continue

    lines.append(f"export interface {name} {{")
    for pname, pschema in props.items():
        optional = "" if pname in required else "?"
        lines.append(f"    {pname}{optional}: {ts_type(pschema)};")
    lines.append("}")
    lines.append("")

with open(types_path, "w") as f:
    f.write("\n".join(lines))

# ── Generate endpoints.ts ──
ep_lines = [
    "// Auto-generated endpoint map — DO NOT EDIT MANUALLY",
    f"// {len(paths)} routes from OpenAPI spec",
    "",
    "export const GeneratedEndpoints = {",
]

for path, methods in sorted(paths.items()):
    # create a safe key: /api/v1/sessions/{id}/close -> sessions_id_close
    safe = re.sub(r"[{}]", "", path)
    safe = re.sub(r"/api/v1/", "", safe)
    safe = re.sub(r"[/\-]", "_", safe).strip("_")
    http_methods = [m.upper() for m in methods if m not in ("parameters", "options")]
    ep_lines.append(f"    // {', '.join(http_methods)}")
    ep_lines.append(f"    '{safe}': '{path}',")

ep_lines.append("} as const;")
ep_lines.append("")
ep_lines.append(f"export type EndpointKey = keyof typeof GeneratedEndpoints;")
ep_lines.append("")

with open(endpoints_path, "w") as f:
    f.write("\n".join(ep_lines))

print(f"  → {len(schemas)} types, {len(paths)} endpoints")
PYEOF

echo "✓ Types generated"

# ── Automatic mode: just copy ──
if [[ "$MODE" == "automatic" ]]; then
  mkdir -p "$GEN_DIR"
  cp "$TMP_DIR/types.ts" "$GEN_DIR/types.ts"
  cp "$TMP_DIR/endpoints.ts" "$GEN_DIR/endpoints.ts"
  cp "$TMP_DIR/openapi.json" "$GEN_DIR/openapi.json"
  echo "✓ Generated client written to $GEN_DIR"
  exit 0
fi

# ── Automatic-with-review mode: diff and prompt ──
if [[ "$MODE" == "automatic-with-review" ]]; then
  mkdir -p "$GEN_DIR"

  CHANGED=false
  for FILE in types.ts endpoints.ts; do
    if [[ -f "$GEN_DIR/$FILE" ]]; then
      if ! diff -q "$TMP_DIR/$FILE" "$GEN_DIR/$FILE" > /dev/null 2>&1; then
        CHANGED=true
        echo ""
        echo "═══ Changes in $FILE ═══"
        diff --color=auto -u "$GEN_DIR/$FILE" "$TMP_DIR/$FILE" || true
      fi
    else
      CHANGED=true
      echo "  ⊕ New file: $FILE"
    fi
  done

  if [[ "$CHANGED" == "false" ]]; then
    echo "✓ No changes detected — client is up to date."
    exit 0
  fi

  echo ""
  read -rp "Apply these changes? [Y/n/d(iff again)] " answer
  case "${answer:-Y}" in
    [Yy]*)
      cp "$TMP_DIR/types.ts" "$GEN_DIR/types.ts"
      cp "$TMP_DIR/endpoints.ts" "$GEN_DIR/endpoints.ts"
      cp "$TMP_DIR/openapi.json" "$GEN_DIR/openapi.json"
      echo "✓ Applied."
      ;;
    *)
      echo "✗ Aborted. Generated files are in $TMP_DIR for manual review."
      ;;
  esac
  exit 0
fi

echo "✗ Unknown mode: $MODE"
exit 1
