# Bug: `bd import` does not import dependencies from JSONL

## Summary

When importing issues from a JSONL file using `bd import -i`, the `dependencies` array in each issue is silently ignored. The issues are created but without any dependency relationships.

## Environment

- **beads version**: (run `bd --version`)
- **OS**: macOS / Linux
- **Shell**: bash

## Steps to Reproduce

1. Create a test JSONL file with dependencies:

```bash
cat > /tmp/test-import.jsonl << 'EOF'
{"id":"test-E01","title":"Test Epic","status":"open","issue_type":"epic","dependencies":[]}
{"id":"test-001","title":"First Task","status":"open","issue_type":"task","dependencies":[{"depends_on_id":"test-E01","type":"parent-child"}]}
{"id":"test-002","title":"Second Task","status":"open","issue_type":"task","dependencies":[{"depends_on_id":"test-E01","type":"parent-child"},{"depends_on_id":"test-001","type":"blocks"}]}
EOF
```

2. Initialize beads in a test directory:

```bash
mkdir /tmp/beads-test && cd /tmp/beads-test
git init
bd init --prefix test
```

3. Import the JSONL:

```bash
bd import -i /tmp/test-import.jsonl
```

4. Check if dependencies were imported:

```bash
bd dep list test-001
bd dep list test-002
```

## Expected Behavior

```
$ bd dep list test-001
test-001 depends on:
  test-E01 (parent-child)

$ bd dep list test-002
test-002 depends on:
  test-E01 (parent-child)
  test-001 (blocks)
```

## Actual Behavior

```
$ bd dep list test-001
test-001 has no dependencies

$ bd dep list test-002
test-002 has no dependencies
```

The issues are imported successfully, but the `dependencies` array is completely ignored.

## Verification

You can confirm the dependencies existed in the source file:

```bash
jq '.dependencies' /tmp/test-import.jsonl
```

Output:
```json
[]
[{"depends_on_id":"test-E01","type":"parent-child"}]
[{"depends_on_id":"test-E01","type":"parent-child"},{"depends_on_id":"test-001","type":"blocks"}]
```

## Workaround

After import, manually add dependencies using `bd dep add`:

```bash
bd dep add test-001 test-E01 --type parent-child
bd dep add test-002 test-E01 --type parent-child
bd dep add test-002 test-001 --type blocks
```

## Impact

This bug breaks workflows that generate beads-compatible JSONL files with dependency information (e.g., AI planning tools, migration scripts, bulk imports). Users must manually recreate all dependency relationships after import, which is error-prone and time-consuming for large imports.

## Suggested Fix

The import logic should process the `dependencies` array for each issue and call the equivalent of `bd dep add` for each dependency entry, respecting the `type` field.

## Additional Context

The JSONL format with dependencies matches what `bd show --json` outputs for issues that have dependencies, so the schema is already defined - it's just not being processed on import.
