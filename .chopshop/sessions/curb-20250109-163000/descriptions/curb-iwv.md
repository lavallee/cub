## Context
Curb needs standard locations for global config, logs, and cache following XDG Base Directory spec.

## Implementation Hints

**Recommended Model:** haiku
**Estimated Duration:** 15m
**Approach:** Simple bash functions that expand XDG vars with fallbacks. Copy pattern from other CLI tools.

## Implementation Steps
1. Create lib/xdg.sh with helper functions
2. Add xdg_config_home() - returns ~/.config or $XDG_CONFIG_HOME
3. Add xdg_data_home() - returns ~/.local/share or $XDG_DATA_HOME
4. Add curb_ensure_dirs() - creates curb subdirs if missing
5. Source from main curb script

## Acceptance Criteria
- [ ] xdg_config_home returns correct path
- [ ] xdg_data_home returns correct path
- [ ] curb_ensure_dirs creates ~/.config/curb and ~/.local/share/curb/logs

## Files Likely Involved
- lib/xdg.sh (new)
- curb (source the new lib)

## Notes
XDG spec: https://specifications.freedesktop.org/basedir-spec/latest/
