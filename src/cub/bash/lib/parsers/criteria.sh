#!/usr/bin/env bash
#
# lib/parsers/criteria.sh - Acceptance criteria extraction utilities
#
# Extracts acceptance criteria from various formats:
# - Checkbox sublists: - [ ] item
# - "Acceptance criteria:" sections with bullet/numbered lists
# - "Done when:" sections with bullet/numbered lists
# - General bullet points following tasks
#
# Usage:
#   extract_criteria_from_body "$content"
#   extract_criteria_section_header "$content" "Acceptance criteria"
#
# Output: JSON array of criteria strings
#

# Main function: Extract all acceptance criteria from content
# Looks for multiple patterns and combines results
# Input: raw text content
# Output: JSON array of criteria strings
extract_criteria_from_body() {
    local body="$1"
    local criteria="[]"

    if [[ -z "$body" ]]; then
        echo "$criteria"
        return
    fi

    # Extract checkbox items (highest priority - most explicit format)
    criteria=$(_extract_checkbox_criteria "$body" "$criteria")

    # Extract "Acceptance criteria:" sections
    criteria=$(_extract_section_criteria "$body" "Acceptance criteria" "$criteria")

    # Extract "Acceptance Criteria:" (capitalized variant)
    criteria=$(_extract_section_criteria "$body" "Acceptance Criteria" "$criteria")

    # Extract "ACCEPTANCE CRITERIA:" (all caps variant)
    criteria=$(_extract_section_criteria "$body" "ACCEPTANCE CRITERIA" "$criteria")

    # Extract "Done when:" sections
    criteria=$(_extract_section_criteria "$body" "Done when" "$criteria")

    # Extract "Done When:" (capitalized variant)
    criteria=$(_extract_section_criteria "$body" "Done When" "$criteria")

    echo "$criteria"
}

# Extract checkbox items from content (- [ ] text)
# Input: body, criteria_json
# Output: updated criteria_json
_extract_checkbox_criteria() {
    local body="$1"
    local criteria="$2"

    while IFS= read -r line; do
        # Match checkbox pattern: - [ ] or - [x] or - [X]
        if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*\[[[:space:]]*[xX]?[[:space:]]*\][[:space:]]+ ]]; then
            local criterion="${line#*\] }"
            criterion="${criterion#[[:space:]]}"
            criterion="${criterion%[[:space:]]}"

            if [[ -n "$criterion" ]]; then
                # Check if this criterion is already in the array (avoid duplicates)
                if ! jq -e ".[] | select(. == \"$criterion\")" <<<"$criteria" >/dev/null 2>&1; then
                    criteria=$(jq --arg text "$criterion" '. += [$text]' <<<"$criteria")
                fi
            fi
        fi
    done < <(echo "$body")

    echo "$criteria"
}

# Extract criteria from a named section header
# Supports formats like:
#   ## Acceptance criteria:
#   ### Acceptance Criteria
#   Acceptance criteria:
# Continues until next section or end of content
# Input: body, section_name, criteria_json
# Output: updated criteria_json
_extract_section_criteria() {
    local body="$1"
    local section_name="$2"
    local criteria="$3"

    # Find the section start using case-insensitive matching
    local found_section=false

    while IFS= read -r line; do
        # Look for section header with various formats (case-insensitive):
        # - "## Acceptance criteria:"
        # - "### Acceptance criteria"
        # - "Acceptance criteria:" (standalone line)
        if ! [[ "$found_section" == "true" ]]; then
            # Case-insensitive regex matching in bash 3.2 compatible way
            # Use pattern matching with [[ ]] and grep
            if echo "$line" | grep -iq "$(printf '%s' "$section_name" | sed 's/[[\.*^$/]/\\&/g')"; then
                found_section=true
                continue
            fi
        fi

        # If we found the section, extract items until we hit another header or empty content block
        if [[ "$found_section" == "true" ]]; then
            # Stop if we hit another heading
            if [[ "$line" =~ ^#+ ]]; then
                break
            fi

            # Extract bullet items: - text (not checkboxes)
            if [[ "$line" =~ ^[[:space:]]*-[[:space:]]+ ]] && [[ ! "$line" =~ ^[[:space:]]*-[[:space:]]*\[ ]]; then
                local criterion="${line#*- }"
                criterion="${criterion#[[:space:]]}"
                criterion="${criterion%[[:space:]]}"

                if [[ -n "$criterion" ]]; then
                    # Check if this criterion is already in the array (avoid duplicates)
                    if ! jq -e ".[] | select(. == \"$criterion\")" <<<"$criteria" >/dev/null 2>&1; then
                        criteria=$(jq --arg text "$criterion" '. += [$text]' <<<"$criteria")
                    fi
                fi
            fi

            # Extract numbered items: 1. 2. 3. etc.
            if [[ "$line" =~ ^[[:space:]]*[0-9]+\.[[:space:]]+ ]]; then
                local criterion="${line#*. }"
                criterion="${criterion#[[:space:]]}"
                criterion="${criterion%[[:space:]]}"

                if [[ -n "$criterion" ]]; then
                    # Check if this criterion is already in the array (avoid duplicates)
                    if ! jq -e ".[] | select(. == \"$criterion\")" <<<"$criteria" >/dev/null 2>&1; then
                        criteria=$(jq --arg text "$criterion" '. += [$text]' <<<"$criteria")
                    fi
                fi
            fi
        fi
    done < <(echo "$body")

    echo "$criteria"
}

# Extract criteria from bullet points (general pattern)
# Used for simple bullet lists not tied to a specific section
# Input: body, criteria_json
# Output: updated criteria_json
_extract_bullet_criteria() {
    local body="$1"
    local criteria="$2"

    while IFS= read -r line; do
        # Match pure bullet points: - text (not checkboxes)
        if [[ "$line" =~ ^-[[:space:]]+ ]] && [[ ! "$line" =~ ^-[[:space:]]*\[ ]]; then
            local criterion="${line#- }"
            criterion="${criterion#[[:space:]]}"
            criterion="${criterion%[[:space:]]}"

            if [[ -n "$criterion" ]]; then
                # Check if this criterion is already in the array (avoid duplicates)
                if ! jq -e ".[] | select(. == \"$criterion\")" <<<"$criteria" >/dev/null 2>&1; then
                    criteria=$(jq --arg text "$criterion" '. += [$text]' <<<"$criteria")
                fi
            fi
        fi
    done < <(echo "$body")

    echo "$criteria"
}

# Helper: Trim whitespace from string
_trim_string() {
    local str="$1"
    # Remove leading/trailing whitespace
    str="${str#[[:space:]]}"
    str="${str%[[:space:]]}"
    echo "$str"
}
