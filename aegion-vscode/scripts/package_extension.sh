#!/usr/bin/env bash
# ==============================================================================
# Aegion VS Code Extension - Marketplace Launch Script (Phase 90)
# ==============================================================================

set -e

echo "🚀 Preparing Aegion VS Code Extension for Marketplace Launch..."

# Ensure we are in the extension directory
cd "$(dirname "$0")"

# 1. Install dependencies
echo "📦 Installing dependencies..."
npm install

# 2. Install VSCE globally if not present (or use npx)
if ! command -v vsce &> /dev/null
then
    echo "📦 Installing vsce..."
    npm install -g @vscode/vsce
fi

# 3. Clean and Build
echo "🏗️ Compiling TypeScript and Webpack bundle..."
npm run compile

# 4. Package VSIX
echo "📦 Packaging VSIX..."
vsce package

echo ""
echo "✅ Packaging complete! The .vsix file has been generated."
echo "   To publish to the VS Code Marketplace:"
echo "   1. Retrieve your Personal Access Token (PAT) from Azure DevOps."
echo "   2. Run: vsce login aegion  (It will ask for your PAT)"
echo "   3. Run: vsce publish"
echo ""
echo "Or distribute the .vsix file directly to internal enterprise teams."
