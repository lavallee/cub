/**
 * Hook for managing keyboard shortcuts across the dashboard.
 *
 * Provides keyboard navigation for common actions like closing panels,
 * navigating between entities, and other shortcuts.
 */

import { useEffect } from 'preact/hooks';

export interface KeyboardShortcut {
  /** Key code or key name (e.g., 'Escape', 'ArrowLeft', 'k') */
  key: string;
  /** Optional modifier keys */
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
  alt?: boolean;
  /** Callback when shortcut is triggered */
  handler: (event: KeyboardEvent) => void;
  /** Description for help text */
  description?: string;
}

interface UseKeyboardShortcutsOptions {
  /** List of keyboard shortcuts to register */
  shortcuts: KeyboardShortcut[];
  /** Whether shortcuts are enabled (default: true) */
  enabled?: boolean;
}

/**
 * Hook for registering and managing keyboard shortcuts.
 *
 * Example usage:
 * ```tsx
 * useKeyboardShortcuts({
 *   shortcuts: [
 *     { key: 'Escape', handler: closePanel, description: 'Close panel' },
 *     { key: 'k', ctrl: true, handler: search, description: 'Search' },
 *   ],
 * });
 * ```
 */
export function useKeyboardShortcuts({ shortcuts, enabled = true }: UseKeyboardShortcutsOptions) {
  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      for (const shortcut of shortcuts) {
        // Check if modifiers match
        if (shortcut.ctrl !== undefined && shortcut.ctrl !== event.ctrlKey) continue;
        if (shortcut.meta !== undefined && shortcut.meta !== event.metaKey) continue;
        if (shortcut.shift !== undefined && shortcut.shift !== event.shiftKey) continue;
        if (shortcut.alt !== undefined && shortcut.alt !== event.altKey) continue;

        // Check if key matches
        if (event.key === shortcut.key) {
          event.preventDefault();
          shortcut.handler(event);
          break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts, enabled]);
}

/**
 * Common keyboard shortcuts for the dashboard.
 */
export const KEYBOARD_SHORTCUTS = {
  CLOSE_PANEL: 'Escape',
  PREVIOUS: 'ArrowLeft',
  NEXT: 'ArrowRight',
  SEARCH: 'k',
  HELP: '?',
  REFRESH: 'r',
} as const;
