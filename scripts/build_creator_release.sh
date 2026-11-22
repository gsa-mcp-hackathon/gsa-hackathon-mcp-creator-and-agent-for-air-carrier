#!/usr/bin/env bash
# Build an MCP A Creator release (round 10, D5).
#
#   scripts/build_creator_release.sh
#
# Writes the wheel and sdist to mcp-server-creator/dist/ (not committed), a
# CycloneDX 1.5 SBOM of the locked runtime dependencies to
# mcp-server-creator/release/<version>/sbom.cdx.json (committed), and checks
# that the wheel installs with uvx and that its two commands run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/mcp-server-creator"

VERSION="$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")"
CODE_VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/mcp_server_creator/__init__.py)"
[ "$VERSION" = "$CODE_VERSION" ] || { echo "pyproject says $VERSION, __init__ says $CODE_VERSION"; exit 1; }
grep -q "^## $VERSION " CHANGELOG.md || { echo "CHANGELOG.md has no section for $VERSION"; exit 1; }

rm -rf dist && uv build -q --out-dir dist
uv lock -q
mkdir -p "release/$VERSION"
uv export -q --frozen --no-dev --no-emit-project --format cyclonedx1.5 -o "release/$VERSION/sbom.cdx.json"

WHEEL="dist/mcp_a_creator-$VERSION-py3-none-any.whl"
uvx --quiet --from "$WHEEL" mcp-a-creator --version
uvx --quiet --from "$WHEEL" mcp-a-creator-doctor > /dev/null
python3 - "release/$VERSION/sbom.cdx.json" <<'EOF'
import json, sys
bom = json.load(open(sys.argv[1]))
names = {c["name"] for c in bom.get("components", [])}
assert {"fastmcp", "pydantic", "httpx"} <= names, sorted(names)[:20]
print(f"sbom: CycloneDX {bom['specVersion']}, {len(names)} components")
EOF
echo "built $VERSION: $(ls dist | tr '\n' ' ')"
echo "tag it with: git tag -a v${VERSION/rc/-rc} -m 'MCP A Creator ${VERSION}'"
