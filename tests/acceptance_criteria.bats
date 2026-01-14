#!/usr/bin/env bats
#
# acceptance_criteria.bats - Tests for acceptance criteria extraction
#

load test_helper

setup() {
    setup_test_dir
    source "$LIB_DIR/parsers/criteria.sh"
}

teardown() {
    teardown_test_dir
}

# Test: Extract checkbox items from content
@test "criteria: extract checkbox items" {
    local body="- [ ] First criterion
- [x] Second criterion (completed)
- [ ] Third criterion"

    local result
    result=$(extract_criteria_from_body "$body")

    # Should extract all checkbox items
    local count
    count=$(echo "$result" | jq 'length')
    [[ "$count" -eq 3 ]]

    # Verify content
    local first
    first=$(echo "$result" | jq -r '.[0]')
    [[ "$first" == "First criterion" ]]
}

# Test: Extract from "Acceptance criteria:" section
@test "criteria: extract from 'Acceptance criteria:' section" {
    local body="Some task description here.

## Acceptance criteria:
- Must validate input
- Should return success code
- Must handle errors gracefully

## Additional notes
- This is not a criterion"

    local result
    result=$(extract_criteria_from_body "$body")

    # Should extract only items from Acceptance criteria section
    local count
    count=$(echo "$result" | jq 'length')
    [[ "$count" -eq 3 ]]

    # Verify first item
    local first
    first=$(echo "$result" | jq -r '.[0]')
    [[ "$first" == "Must validate input" ]]
}

# Test: Extract from "Done when:" section
@test "criteria: extract from 'Done when:' section" {
    local body="Implementation task.

### Done when:
1. Tests pass
2. Code is reviewed
3. Documentation is updated"

    local result
    result=$(extract_criteria_from_body "$body")

    # Should extract numbered items
    local count
    count=$(echo "$result" | jq 'length')
    [[ "$count" -eq 3 ]]

    # Verify items
    local first
    first=$(echo "$result" | jq -r '.[0]')
    [[ "$first" == "Tests pass" ]]
}

# Test: Mix of checkbox and section criteria
@test "criteria: combine checkbox and section criteria" {
    local body="- [ ] Core requirement 1
- [ ] Core requirement 2

## Acceptance Criteria:
- Should be fast
- Must be secure"

    local result
    result=$(extract_criteria_from_body "$body")

    # Should have 4 items total
    local count
    count=$(echo "$result" | jq 'length')
    [[ "$count" -eq 4 ]]
}

# Test: Case-insensitive section matching
@test "criteria: case-insensitive section matching" {
    local body1="## Acceptance criteria:"
    local body2="## ACCEPTANCE CRITERIA:"
    local body3="## acceptance criteria:"
    local body4="## Acceptance Criteria:"

    # All should extract the same (with bullet following)
    local body_with_items="$body1
- Item 1"

    local result
    result=$(extract_criteria_from_body "$body_with_items")

    local count
    count=$(echo "$result" | jq 'length')
    [[ "$count" -eq 1 ]]
}

# Test: Avoid duplicate criteria
@test "criteria: avoid duplicates when extracting" {
    local body="- [ ] Same item
- Same item"

    local result
    result=$(extract_criteria_from_body "$body")

    # Should only have 1 item (duplicate removed)
    local count
    count=$(echo "$result" | jq 'length')
    [[ "$count" -eq 1 ]]
}

# Test: Empty content returns empty array
@test "criteria: empty content returns empty array" {
    local body=""
    local result
    result=$(extract_criteria_from_body "$body")

    local count
    count=$(echo "$result" | jq 'length')
    [[ "$count" -eq 0 ]]
}

# Test: Extract from multiple sections
@test "criteria: extract from multiple sections" {
    local body="# Task

## Acceptance Criteria:
- Criterion 1
- Criterion 2

## Done When:
- Done 1
- Done 2"

    local result
    result=$(extract_criteria_from_body "$body")

    # Should have 4 items (all from both sections)
    local count
    count=$(echo "$result" | jq 'length')
    [[ "$count" -eq 4 ]]
}

# Test: Numbered items in section
@test "criteria: extract numbered items from section" {
    local body="## Acceptance Criteria:
1. First numbered item
2. Second numbered item
3. Third numbered item"

    local result
    result=$(extract_criteria_from_body "$body")

    local count
    count=$(echo "$result" | jq 'length')
    [[ "$count" -eq 3 ]]

    local second
    second=$(echo "$result" | jq -r '.[1]')
    [[ "$second" == "Second numbered item" ]]
}

# Test: Stop at next section header
@test "criteria: stop at next section header" {
    local body="## Acceptance Criteria:
- Criterion 1
- Criterion 2

## Implementation Notes:
- This is not a criterion
- Neither is this"

    local result
    result=$(extract_criteria_from_body "$body")

    # Should only have 2 criteria
    local count
    count=$(echo "$result" | jq 'length')
    [[ "$count" -eq 2 ]]
}

# Test: Whitespace handling
@test "criteria: handle whitespace in items" {
    local body="## Acceptance Criteria:
- Item with  leading spaces
- Item with multiple leading spaces
- Item with trailing spaces   "

    local result
    result=$(extract_criteria_from_body "$body")

    # All should be extracted
    local count
    count=$(echo "$result" | jq 'length')
    [[ "$count" -eq 3 ]]

    # Check first item is extracted
    local first
    first=$(echo "$result" | jq -r '.[0]')
    [[ -n "$first" ]]
}

# Test: Complex markdown with various criteria formats
@test "criteria: complex markdown with mixed formats" {
    local body="# Feature Implementation

## Summary
Do some work.

## Acceptance Criteria:
- Functional requirement 1
- Functional requirement 2

## Done When:
1. All tests pass
2. Code reviewed

Additional checkboxes:
- [ ] Checklist item 1
- [ ] Checklist item 2

## Notes
This is not a criterion."

    local result
    result=$(extract_criteria_from_body "$body")

    # Should have: 2 from acceptance criteria + 2 from done when + 2 from checkboxes = 6
    local count
    count=$(echo "$result" | jq 'length')
    [[ "$count" -eq 6 ]]
}

# Test: Valid JSON output
@test "criteria: output is valid JSON" {
    local body="- [ ] Criterion 1
- Criterion 2

## Acceptance Criteria:
- Criterion 3"

    local result
    result=$(extract_criteria_from_body "$body")

    # Should be valid JSON array
    echo "$result" | jq '.' >/dev/null
    [[ $? -eq 0 ]]
}

# Test: Each item is a string
@test "criteria: each item is a string" {
    local body="- [ ] Item 1
- Item 2
- [ ] Item 3"

    local result
    result=$(extract_criteria_from_body "$body")

    # Check that all items are strings
    local all_strings
    all_strings=$(echo "$result" | jq 'all(type == "string")')
    [[ "$all_strings" == "true" ]]
}

# Test: Markdown parser integration
@test "criteria: works with markdown parser" {
    cat > "$TEST_DIR/test.md" << 'EOF'
# Feature
## Task Group
- [ ] Main task
- Bullet criterion 1
- Bullet criterion 2
- [ ] Checkbox criterion
EOF

    source "$LIB_DIR/parsers/markdown.sh"
    local result
    result=$(parse_markdown_file "$TEST_DIR/test.md")

    # Find the main task and check its acceptance criteria
    local criteria_count
    criteria_count=$(echo "$result" | jq '.tasks[] | select(.title == "Main task") | .acceptanceCriteria | length')

    # Should have at least inline bullet criteria
    [[ "$criteria_count" -ge 2 ]]

    # Verify first criterion
    local first_criterion
    first_criterion=$(echo "$result" | jq -r '.tasks[] | select(.title == "Main task") | .acceptanceCriteria[0]')
    [[ "$first_criterion" == "Bullet criterion 1" ]]
}
