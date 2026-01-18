# Secret Redaction

Cub includes built-in secret redaction to prevent sensitive data from appearing in logs, status files, and console output. This protects API keys, passwords, and other credentials from accidental exposure.

## How Redaction Works

Cub scans output for patterns that look like secrets and replaces them with `[REDACTED]`:

```
Before: Authorization: Bearer sk-abc123xyz789...
After:  Authorization: Bearer [REDACTED]
```

Redaction applies to:

- JSONL audit logs
- Status files
- Console output (when applicable)
- Error messages

## Default Secret Patterns

Cub includes these default regex patterns for secret detection:

| Pattern | Matches |
|---------|---------|
| `api[_-]?key` | API_KEY, api-key, apikey |
| `password` | password, PASSWORD |
| `token` | token, access_token, refresh_token |
| `secret` | secret, client_secret |
| `authorization` | Authorization headers |
| `credentials` | credentials, aws_credentials |

### How Patterns Are Applied

Patterns match case-insensitively on key names. When a match is found, the associated value is redacted:

```json
// Input
{"api_key": "sk-abc123", "user": "alice"}

// Output (redacted)
{"api_key": "[REDACTED]", "user": "alice"}
```

## Configuration

### Adding Custom Patterns

Add project-specific patterns in `.cub.json`:

```json
{
  "guardrails": {
    "secret_patterns": [
      "api[_-]?key",
      "password",
      "token",
      "secret",
      "authorization",
      "credentials",
      "stripe[_-]?key",
      "database[_-]?url",
      "private[_-]?key"
    ]
  }
}
```

!!! warning "Pattern Replacement"
    Setting `secret_patterns` **replaces** the defaults. Include the default patterns if you want to keep them.

### Pattern Syntax

Patterns use Python regex syntax:

```python
# Match variations
"api[_-]?key"      # api_key, api-key, apikey
"pass(word|phrase)" # password, passphrase
".*_secret$"       # anything ending in _secret
```

### Disabling Redaction

To disable redaction (not recommended):

```json
{
  "guardrails": {
    "secret_patterns": []
  }
}
```

## Viewing Redacted Logs

### JSONL Logs

Logs at `~/.local/share/cub/logs/{project}/{session}.jsonl` are redacted:

```bash
cat ~/.local/share/cub/logs/myproject/session.jsonl | jq .
```

```json
{
  "timestamp": "2026-01-17T10:30:00Z",
  "event_type": "task_start",
  "data": {
    "task_id": "cub-054",
    "env": {
      "ANTHROPIC_API_KEY": "[REDACTED]",
      "HOME": "/Users/alice"
    }
  }
}
```

### Status Files

Status files at `.cub/runs/{session}/status.json` are also redacted:

```json
{
  "run_id": "cub-20260117",
  "last_error": "API call failed: Invalid API key [REDACTED]"
}
```

## What Gets Redacted

### Environment Variables

Any environment variable matching a secret pattern has its value redacted:

```bash
# Original
ANTHROPIC_API_KEY=sk-ant-abc123

# In logs
"ANTHROPIC_API_KEY": "[REDACTED]"
```

### JSON Values

JSON keys matching patterns have their values redacted:

```json
// Original
{"database_password": "hunter2", "port": 5432}

// Redacted
{"database_password": "[REDACTED]", "port": 5432}
```

### Error Messages

Secrets in error messages are redacted:

```
Original: Authentication failed for token sk-abc123xyz
Redacted: Authentication failed for token [REDACTED]
```

## What Is NOT Redacted

Cub's redaction is pattern-based and cannot detect all secrets:

| Item | Redacted? | Notes |
|------|-----------|-------|
| API keys with known prefixes | :white_check_mark: | `sk-`, `pk_`, etc. |
| Values matching patterns | :white_check_mark: | If key matches |
| Random strings | :x: | No pattern match |
| Encoded secrets | :x: | Base64, etc. |
| Secrets in prose | :x: | Unstructured text |

## Best Practices

### Use Environment Variables

Keep secrets in environment variables, not in code or config:

```bash
# Good: Secret in environment
export ANTHROPIC_API_KEY=sk-ant-...

# Bad: Secret in config file
# .cub.json: {"api_key": "sk-ant-..."}
```

### Add Project-Specific Patterns

If your project uses custom secret names, add patterns:

```json
{
  "guardrails": {
    "secret_patterns": [
      "api[_-]?key",
      "password",
      "token",
      "secret",
      "authorization",
      "credentials",
      "stripe[_-]?(key|secret)",
      "twilio[_-]?(sid|token)",
      "sendgrid[_-]?key",
      "jwt[_-]?secret"
    ]
  }
}
```

### Review Logs Before Sharing

Even with redaction, review logs before sharing:

```bash
# Search for potential secrets
grep -i "key\|token\|secret\|password" ~/.local/share/cub/logs/myproject/*.jsonl
```

### Use Separate Keys for Development

Use dedicated API keys for autonomous sessions that can be revoked if exposed:

```bash
# Development-only key
export ANTHROPIC_API_KEY=$DEV_ANTHROPIC_KEY

cub run --once
```

## Troubleshooting

### Secrets Still Appearing

If secrets appear in logs:

1. Check if the key name matches a pattern
2. Add a custom pattern for the key format
3. Verify `secret_patterns` in config includes defaults

### Too Much Redaction

If non-secrets are being redacted:

1. Review your custom patterns for over-matching
2. Use more specific regex patterns
3. Consider excluding certain fields

### Verifying Redaction

Test redaction with debug mode:

```bash
cub run --once --debug 2>&1 | grep -i "redacted"
```

## Security Considerations

Cub's redaction is a **defense-in-depth** measure, not a security guarantee:

1. **Redaction happens after processing** - Secrets are briefly in memory
2. **Pattern-based** - Novel secret formats may not match
3. **Log files persist** - Redacted logs should still be protected
4. **Not encryption** - Redacted values are removed, not encrypted

For maximum security:

- Use short-lived API keys
- Set strict file permissions on log directories
- Consider disabling logging for highly sensitive work
- Regularly rotate credentials
