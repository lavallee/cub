#!/usr/bin/env bash
#
# Rename curb to cub
# Run with --dry-run first to see what would change
#

set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "=== DRY RUN MODE ==="
fi

run_cmd() {
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "[would run] $*"
    else
        "$@"
    fi
}

cd "$(dirname "$0")/.."
echo "Working in: $(pwd)"

# 1. Clean up old run artifacts (optional - they contain old task IDs)
echo -e "\n=== Step 1: Clean up old artifacts ==="
if [[ -d .cub/runs ]]; then
    echo "Found .cub/runs/ - consider removing old run data"
    run_cmd rm -rf .cub/runs
fi
if [[ -d .chopshop ]]; then
    echo "Found .chopshop/ - consider removing old session data"
    run_cmd rm -rf .chopshop
fi

# 2. Content replacements in source files
echo -e "\n=== Step 2: Replace content in files ==="

# Files to process (exclude .git, .beads, node_modules, etc.)
FILES=$(find . -type f \( -name "*.sh" -o -name "*.md" -o -name "*.json" -o -name "*.bats" -o -name "*.txt" \) \
    -not -path "./.git/*" \
    -not -path "./.beads/*" \
    -not -path "./.cub/*" \
    -not -path "./.chopshop/*" \
    -not -path "./node_modules/*" 2>/dev/null)

# Also include the main script (no extension)
FILES="$FILES ./curb ./curb-init"

for file in $FILES; do
    [[ -f "$file" ]] || continue

    if grep -q -E 'curb|CURB' "$file" 2>/dev/null; then
        echo "Processing: $file"
        if [[ "$DRY_RUN" == "true" ]]; then
            grep -c -E 'curb|CURB' "$file" 2>/dev/null | xargs -I{} echo "  {} matches"
        else
            # Replace patterns (order matters - do specific patterns first)
            sed -i '' \
                -e 's/\.curb\.json/.cub.json/g' \
                -e 's/\.curb\//.cub\//g' \
                -e 's/CUB_/CUB_/g' \
                -e 's/\[curb\]/[cub]/g' \
                -e 's/curb\//cub\//g' \
                -e 's/"cub"/"cub"/g' \
                -e "s/'cub'/'cub'/g" \
                -e 's/cub run/cub run/g' \
                -e 's/cub init/cub init/g' \
                -e 's/cub status/cub status/g' \
                -e 's/cub doctor/cub doctor/g' \
                -e 's/cub explain/cub explain/g' \
                -e 's/cub artifacts/cub artifacts/g' \
                -e 's/# cub/# cub/g' \
                -e 's/cub --/cub --/g' \
                -e 's/cub is /cub is /g' \
                -e 's/cub will /cub will /g' \
                -e 's/curb\.sh/cub.sh/g' \
                "$file"
        fi
    fi
done

# 3. Rename files
echo -e "\n=== Step 3: Rename files ==="
[[ -f curb ]] && run_cmd mv curb cub
[[ -f curb-init ]] && run_cmd mv curb-init cub-init
[[ -f tests/curb.bats ]] && run_cmd mv tests/curb.bats tests/cub.bats
[[ -d .curb ]] && run_cmd mv .curb .cub
[[ -f tests/e2e/project/.cub.json ]] && run_cmd mv tests/e2e/project/.cub.json tests/e2e/project/.cub.json
[[ -d tests/e2e/project/.curb ]] && run_cmd mv tests/e2e/project/.curb tests/e2e/project/.cub

# 4. Update beads task IDs (optional - they can keep curb- prefix as historical)
echo -e "\n=== Step 4: Beads tasks ==="
echo "Note: Beads task IDs (curb-xxx) are left unchanged as historical identifiers"
echo "New tasks will be created with 'cub-' prefix once bd is reconfigured"

# 5. Summary
echo -e "\n=== Done ==="
if [[ "$DRY_RUN" == "true" ]]; then
    echo "This was a dry run. Run without --dry-run to apply changes."
else
    echo "Rename complete! Next steps:"
    echo "  1. Update any shell aliases/PATH entries"
    echo "  2. Update brew formula if applicable"
    echo "  3. Run tests: bats tests/*.bats"
    echo "  4. Commit: git add -A && git commit -m 'rename: curb → cub'"
fi
