# Project Constitution

A constitution defines the engineering principles that guide how your team builds software with AI assistance. These principles help maintain consistency, quality, and alignment across all contributors—human and AI alike.

---

## Core Product Values

> These foundational values shape what we build and how we build it.

1. **Serve, don't extract.** The product exists to make someone's life measurably easier. If a feature doesn't serve the person using it, it serves someone else's interests at their expense.

2. **Earn attention, never manipulate it.** Respect the user's time as a finite, non-renewable resource. Optimize for unregretted minutes, not engagement metrics. A product that people feel relieved to close has failed.

3. **Less, less, less.** Resist the default toward more surface area, more notifications, more content. The harder design problem—and the more valuable one—is helping people get to clarity faster and then get on with their lives.

4. **Verify before you ship.** A product's first obligation is to accuracy—in what it claims to do, in the information it surfaces, in the promises its interface makes. Don't ship things you haven't pressure-tested against reality.

5. **Be honest about what you don't know.** Transparency isn't a feature, it's a posture. When the product is uncertain, say so. When data is incomplete, show the edges. Never manufacture false confidence to smooth over a gap.

6. **Minimize harm as a design constraint.** Every feature has failure modes. Ask "who gets hurt if this goes wrong?" before asking "how cool is this if it goes right?" The answer should shape what you build and what you choose not to build.

7. **Build for the person who can't afford to get it wrong.** Design for the resource-strapped, the overwhelmed, the person with no technical safety net. If it works for them, it works for everyone. If it only works for power users, it's a toy.

8. **Accountability is structural.** Make it possible for users to understand why the product did what it did, to correct it when it's wrong, and to leave cleanly when they want to. Don't hold people's data or workflows hostage.

---

## Engineering Principles

> These principles guide the technical decisions we make every day.

### 1. Test With Intent

**Rationale:** Tests are not checkboxes—they're executable documentation of expected behavior. Every test should answer "what breaks if this stops working?" If you can't answer that question, the test adds noise without value.

#### Good Pattern
```python
def test_withdrawal_prevents_overdraft():
    """Verify account balance cannot go negative through withdrawal."""
    account = Account(balance=100)

    result = account.withdraw(150)

    assert result.success is False
    assert result.error == "Insufficient funds"
    assert account.balance == 100  # Balance unchanged
```

#### Bad Pattern
```python
def test_account():
    account = Account(balance=100)
    account.withdraw(50)
    assert account.balance == 50
    account.deposit(25)
    assert account.balance == 75
    # Tests multiple behaviors, unclear what's being verified
```

**Key practices:**
- One behavior per test, named to describe the scenario
- Arrange-Act-Assert structure makes intent clear
- Test edge cases and failure modes, not just happy paths

---

### 2. Fail Fast, Fail Loudly

**Rationale:** Silent failures compound. A bug discovered in production is exponentially more expensive than one caught at compile time. Push error detection as early as possible in the development cycle.

#### Good Pattern
```typescript
function processPayment(amount: number, currency: Currency): PaymentResult {
  if (amount <= 0) {
    throw new ValidationError(`Invalid amount: ${amount}. Must be positive.`);
  }
  if (!SUPPORTED_CURRENCIES.includes(currency)) {
    throw new ValidationError(`Unsupported currency: ${currency}`);
  }
  // Proceed with valid inputs only
  return executePayment(amount, currency);
}
```

#### Bad Pattern
```typescript
function processPayment(amount: number, currency: string): any {
  if (amount <= 0) {
    return null;  // Caller has no idea why it failed
  }
  if (!SUPPORTED_CURRENCIES.includes(currency)) {
    console.log("Bad currency");  // Logged but execution continues
  }
  return executePayment(amount, currency);
}
```

**Key practices:**
- Validate inputs at system boundaries
- Use typed errors that explain what went wrong
- Never swallow exceptions silently
- Prefer compile-time checks over runtime checks where possible

---

### 3. Clarity Over Cleverness

**Rationale:** Code is read 10x more than it's written. Clever optimizations or abstractions that save keystrokes cost hours in comprehension. The best code reads like well-edited prose—every element earns its place.

#### Good Pattern
```python
def calculate_shipping_cost(order: Order) -> Decimal:
    """Calculate shipping based on weight tiers and destination."""
    base_rate = SHIPPING_RATES[order.destination_zone]
    weight_kg = order.total_weight_kg

    if weight_kg <= 1:
        return base_rate
    elif weight_kg <= 5:
        return base_rate + Decimal("2.50")
    else:
        extra_kg = weight_kg - 5
        return base_rate + Decimal("2.50") + (extra_kg * Decimal("0.50"))
```

#### Bad Pattern
```python
def calc_ship(o):
    r = SR[o.dz]
    w = o.tw
    return r if w <= 1 else r + 2.5 if w <= 5 else r + 2.5 + (w - 5) * .5
```

**Key practices:**
- Descriptive names that reveal intent
- Break complex logic into named steps
- Comments explain "why", code explains "what"
- Avoid abbreviations except universally understood ones (e.g., `id`, `url`)

---

### 4. Secure by Default

**Rationale:** Security is not a feature to add later—it's a constraint that shapes architecture from day one. Assume malicious input, leaked credentials, and compromised dependencies. Build defense in depth.

#### Good Pattern
```python
from secrets import compare_digest
from hashlib import scrypt

def verify_password(stored_hash: bytes, salt: bytes, provided: str) -> bool:
    """Constant-time password verification to prevent timing attacks."""
    provided_hash = scrypt(
        provided.encode(),
        salt=salt,
        n=2**14, r=8, p=1
    )
    return compare_digest(stored_hash, provided_hash)

def get_user_data(user_id: str, requesting_user: User) -> UserData:
    """Always verify authorization, never trust the caller."""
    if not requesting_user.can_access(user_id):
        raise AuthorizationError("Access denied")
    return UserRepository.find(user_id)
```

#### Bad Pattern
```python
def verify_password(stored, provided):
    return stored == provided  # Plain text! Timing attack vulnerable!

def get_user_data(user_id):
    # No auth check - assumes caller already verified
    return UserRepository.find(user_id)
```

**Key practices:**
- Never store secrets in code or logs
- Validate and sanitize all external input
- Use parameterized queries—never string concatenation for SQL
- Audit dependencies regularly for known vulnerabilities
- Apply principle of least privilege everywhere

---

### 5. Document Decisions, Not Just Code

**Rationale:** The hardest knowledge to recover is why something was built a certain way. Code comments explain the "what"; architectural decision records explain the "why". Future maintainers (including future you) will thank you.

#### Good Pattern
```markdown
# ADR-007: Use Event Sourcing for Order History

## Context
We need to track all changes to orders for audit and customer service purposes.
Current approach of periodic snapshots loses intermediate states.

## Decision
Implement event sourcing for the Order aggregate. All state changes will be
recorded as immutable events, and current state will be derived by replaying events.

## Consequences
- **Positive:** Complete audit trail, ability to replay/debug past states
- **Negative:** Increased storage, more complex queries for current state
- **Mitigation:** Implement periodic snapshots for query performance
```

#### Bad Pattern
```python
# TODO: fix this later
# HACK: don't ask
# Changed by John, not sure why
def process_order(order):
    order.status = 3  # Magic number, no explanation
    ...
```

**Key practices:**
- Keep an `ADR/` folder for architectural decisions
- Write commit messages that explain the "why", not just the "what"
- Document non-obvious constraints (regulatory, performance, compatibility)
- Update docs when behavior changes—stale docs are worse than none

---

## Customizing for Your Project

Your project has unique constraints, values, and history. The principles above are starting points—adapt them to fit your context.

### Step 1: Identify Your Non-Negotiables

Start by asking: "What would make us reject a PR regardless of its features?"

Common non-negotiables include:
- All public APIs must have OpenAPI documentation
- No raw SQL queries outside the repository layer
- All user-facing text must go through i18n
- No new dependencies without security review

Write these down explicitly. If it's not written, it's not a principle—it's a preference.

### Step 2: Learn from Past Pain

Review your post-mortems, bug reports, and PR comments. What patterns repeatedly cause problems? Convert those lessons into positive principles.

| Pain Point | Principle |
|------------|-----------|
| "Nobody knew the payment service was down for 2 hours" | All external service calls must have circuit breakers and alerting |
| "The migration broke prod because we didn't test with real data volumes" | Database migrations require load testing against production-scale data |
| "We shipped a feature the legal team hadn't approved" | Features with PII implications require legal sign-off before merge |

### Step 3: Make Trade-offs Explicit

Every principle has a cost. Acknowledge them openly:

- "We prioritize readability over performance, except in the hot path"
- "We accept slower CI in exchange for comprehensive integration tests"
- "We duplicate code across bounded contexts rather than create shared libraries"

When the trade-off isn't explicit, people will optimize differently and conflict will follow.

### Step 4: Write for the New Team Member

Your constitution should answer questions before they're asked. A new engineer reading it should understand:

- What "good" looks like here
- Which corners are acceptable to cut (and which are never acceptable)
- Who to ask when principles conflict

---

## Anti-Patterns to Avoid

### The Aspiration Document
**Problem:** Principles describe how you wish you worked, not how you actually work.

**Symptom:** Team members roll their eyes when the constitution comes up. "Yeah, it says that, but..."

**Fix:** Only include principles you're willing to enforce. Start small and grow.

### The Exhaustive List
**Problem:** Fifty principles covering every edge case, impossible to remember or apply.

**Symptom:** Nobody can recite even three principles from memory.

**Fix:** Keep to 5-10 core principles. Move specific guidelines to style guides or linting rules.

### The Vague Platitude
**Problem:** "Write clean code" or "Be thoughtful about performance."

**Symptom:** Two people cite the same principle to justify opposite decisions.

**Fix:** Add specifics. "Clean code" becomes "Functions under 30 lines, max 3 levels of nesting." Provide concrete examples.

### The Forgotten Artifact
**Problem:** Written once, never referenced, never updated.

**Symptom:** Principles reference deprecated technologies or practices no one follows.

**Fix:** Schedule quarterly reviews. Add "constitution alignment" to PR review checklist.

### The Imposed Mandate
**Problem:** Handed down from leadership without team input.

**Symptom:** Passive resistance. Principles followed only when someone's watching.

**Fix:** Develop principles collaboratively. Everyone who must follow them should help shape them.

---

## Living Document Guidance

A constitution isn't carved in stone—it evolves as your team and product mature.

### When to Update

- **After incidents:** Pain is a teacher. If a principle would have prevented the outage, add it.
- **During retrospectives:** "We keep saying we should X" means X should be formalized.
- **When technology shifts:** Principles about jQuery don't help a React codebase.
- **When team composition changes:** New perspectives may reveal blind spots.

### How to Update

1. **Propose in writing:** Open a PR or RFC explaining the change and its rationale.
2. **Discuss asynchronously:** Give people time to think, not just react.
3. **Seek dissent:** Silence isn't consent. Actively ask "Who disagrees?"
4. **Commit to trial periods:** "Let's try this for one quarter and evaluate."
5. **Communicate the change:** Principles only work if everyone knows them.

### Version Your Constitution

Treat your constitution like code:
- Keep it in version control
- Require reviews for changes
- Tag significant revisions (v1.0, v2.0)
- Maintain a changelog explaining what changed and why

```markdown
## Changelog

### v2.0 - 2024-03-15
- Added "Secure by Default" principle after security audit findings
- Clarified testing principle with concrete coverage expectations
- Removed reference to deprecated logging framework

### v1.0 - 2023-06-01
- Initial constitution established
```

---

## Final Note

A constitution is only as good as its application. It should be:
- **Referenced in code reviews:** "This seems to conflict with principle #3"
- **Cited in architecture discussions:** "Given our principle about X, we should..."
- **Used in onboarding:** New team members read and discuss it in their first week
- **Revisited regularly:** Not a monument, but a living agreement

The goal isn't perfection—it's alignment. When the team shares a clear understanding of how we work, we spend less time debating basics and more time building things that matter.
