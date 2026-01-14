#!/usr/bin/env bash
#
# lib/priority.sh - Priority inference engine for tasks
#
# Detects task priority from content using multiple strategies:
# 1. Explicit markers: [P0], [P1], [P2], [P3], [P4]
# 2. Position-based hints: position in document (first items often more important)
# 3. Keywords: critical, blocker, must, high, important, low, optional, etc.
# 4. Contextual patterns: "high priority", "CRITICAL", etc.
#
# Usage:
#   infer_priority_from_content "$content"
#   infer_priority_from_title_body "$title" "$body"
#   infer_priority_from_title "$title"
#

# Infer priority from arbitrary content
# Supports: explicit markers, keyword patterns, contextual hints
# Usage: infer_priority_from_content "$content"
# Output: Priority string (P0-P4, default P2)
infer_priority_from_content() {
    local content="$1"

    if [[ -z "$content" ]]; then
        echo "P2"  # Default priority
        return
    fi

    _infer_priority_internal "$content"
}

# Infer priority from title and body (separate parameters)
# Usage: infer_priority_from_title_body "$title" "$body"
# Output: Priority string (P0-P4, default P2)
infer_priority_from_title_body() {
    local title="$1"
    local body="$2"
    local combined="$title
$body"

    _infer_priority_internal "$combined"
}

# Infer priority from title only
# Usage: infer_priority_from_title "$title"
# Output: Priority string (P0-P4, default P2)
infer_priority_from_title() {
    local title="$1"

    _infer_priority_internal "$title"
}

# Internal priority inference engine
# Implements the following strategy:
# 1. Explicit [P0]-[P4] markers (highest priority)
# 2. Contextual patterns like "HIGH PRIORITY", "CRITICAL", etc.
# 3. Keyword-based inference (critical → P0, low → P3, etc.)
# 4. Default to P2 (medium priority)
_infer_priority_internal() {
    local text="$1"

    # Convert to lowercase for keyword matching
    local text_lower
    text_lower=$(echo "$text" | tr '[:upper:]' '[:lower:]')

    # STRATEGY 1: Check for explicit priority markers [P0]-[P4]
    # These are the most explicit and take highest precedence
    if [[ "$text" =~ \[P0\] ]]; then
        echo "P0"
        return
    elif [[ "$text" =~ \[P1\] ]]; then
        echo "P1"
        return
    elif [[ "$text" =~ \[P2\] ]]; then
        echo "P2"
        return
    elif [[ "$text" =~ \[P3\] ]]; then
        echo "P3"
        return
    elif [[ "$text" =~ \[P4\] ]]; then
        echo "P4"
        return
    fi

    # STRATEGY 2: Check for contextual priority patterns
    # Patterns like "HIGH PRIORITY", "CRITICAL", etc. (case-insensitive)

    # Critical/Blocker patterns → P0 (highest priority)
    if [[ "$text_lower" =~ critical ]] || [[ "$text_lower" =~ blocker ]] || \
       [[ "$text_lower" =~ must[[:space:]]*fix ]] || [[ "$text_lower" =~ breaking[[:space:]]*change ]] || \
       [[ "$text_lower" =~ security[[:space:]]*issue ]]; then
        echo "P0"
        return
    fi

    # Very high priority patterns → P0
    if [[ "$text_lower" =~ high[[:space:]]*priority ]] || [[ "$text_lower" =~ urgent ]] || \
       [[ "$text_lower" =~ must[[:space:]] ]] || [[ "$text_lower" =~ asap ]]; then
        echo "P0"
        return
    fi

    # STRATEGY 3: Keyword-based inference
    # P0 keywords: critical, blocker, must, urgent
    if [[ "$text_lower" =~ critical ]] || [[ "$text_lower" =~ blocker ]] || \
       [[ "$text_lower" =~ must ]] || [[ "$text_lower" =~ urgent ]]; then
        echo "P0"
        return
    fi

    # P1 keywords: high, important, required
    if [[ "$text_lower" =~ high ]] || [[ "$text_lower" =~ important ]] || \
       [[ "$text_lower" =~ required ]]; then
        echo "P1"
        return
    fi

    # P3 keywords: low, optional, nice, cosmetic, polish, enhancement
    if [[ "$text_lower" =~ low ]] || [[ "$text_lower" =~ optional ]] || \
       [[ "$text_lower" =~ nice ]] || [[ "$text_lower" =~ cosmetic ]] || \
       [[ "$text_lower" =~ polish ]] || [[ "$text_lower" =~ enhancement ]]; then
        echo "P3"
        return
    fi

    # P4 keywords: someday, backlog, defer, eventually
    if [[ "$text_lower" =~ someday ]] || [[ "$text_lower" =~ backlog ]] || \
       [[ "$text_lower" =~ defer ]] || [[ "$text_lower" =~ eventually ]]; then
        echo "P4"
        return
    fi

    # Default to medium priority
    echo "P2"
}

# Validate that a priority value is valid (P0-P4 or numeric 0-4)
# Usage: is_valid_priority "$priority_value"
# Returns: 0 if valid, 1 if invalid
is_valid_priority() {
    local priority="$1"

    # Check for P0-P4 format
    if [[ "$priority" =~ ^P[0-4]$ ]]; then
        return 0
    fi

    # Check for numeric 0-4 format
    if [[ "$priority" =~ ^[0-4]$ ]]; then
        return 0
    fi

    return 1
}

# Normalize priority to P-format (P0-P4)
# Converts numeric (0-4) to P-format if needed
# Usage: normalize_priority "$priority"
# Output: Priority in P-format (P0-P4)
normalize_priority() {
    local priority="$1"

    # Already in P-format
    if [[ "$priority" =~ ^P[0-4]$ ]]; then
        echo "$priority"
        return
    fi

    # Convert numeric to P-format
    if [[ "$priority" =~ ^[0-4]$ ]]; then
        echo "P$priority"
        return
    fi

    # Invalid priority, return default
    echo "P2"
}

# Get priority description
# Usage: get_priority_description "P0"
# Output: Human-readable description
get_priority_description() {
    local priority="$1"

    case "$priority" in
        P0|0)
            echo "Critical/Blocker"
            ;;
        P1|1)
            echo "High priority"
            ;;
        P2|2)
            echo "Medium priority"
            ;;
        P3|3)
            echo "Low priority"
            ;;
        P4|4)
            echo "Optional/Nice-to-have"
            ;;
        *)
            echo "Unknown priority"
            ;;
    esac
}

# Get numeric priority value (0-4)
# Converts P-format or numeric to numeric
# Usage: get_numeric_priority "P2"
# Output: Numeric priority (0-4)
get_numeric_priority() {
    local priority="$1"

    # Remove P prefix if present
    priority="${priority#P}"

    # Validate it's a number 0-4
    if [[ "$priority" =~ ^[0-4]$ ]]; then
        echo "$priority"
    else
        echo "2"  # Default to P2
    fi
}
