/**
 * Navigation hook for managing entity navigation history.
 *
 * Provides a history stack for navigating between entities in the detail panel,
 * enabling breadcrumb navigation and back button functionality.
 */

import { useState, useCallback } from 'preact/hooks';

export interface NavigationState {
  /** Currently selected entity ID */
  currentEntityId: string | null;
  /** Navigation history stack (ordered from oldest to newest) */
  history: string[];
  /** Whether we can go back in history */
  canGoBack: boolean;
}

export interface NavigationActions {
  /** Navigate to a new entity */
  navigateTo: (entityId: string) => void;
  /** Go back to the previous entity */
  goBack: () => void;
  /** Clear all navigation and close detail panel */
  clear: () => void;
  /** Get the full navigation path (history + current) */
  getPath: () => string[];
}

export type UseNavigationReturn = NavigationState & NavigationActions;

/**
 * Hook for managing entity navigation with history tracking.
 *
 * Example usage:
 * ```tsx
 * const nav = useNavigation();
 *
 * // Navigate to an entity
 * nav.navigateTo('task-123');
 *
 * // Navigate to a related entity
 * nav.navigateTo('epic-456'); // Adds to history
 *
 * // Go back
 * nav.goBack(); // Returns to task-123
 *
 * // Clear and close
 * nav.clear();
 * ```
 */
export function useNavigation(): UseNavigationReturn {
  const [currentEntityId, setCurrentEntityId] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]);

  const navigateTo = useCallback((entityId: string) => {
    setHistory((prev) => {
      // If we're currently viewing an entity, add it to history
      if (currentEntityId && currentEntityId !== entityId) {
        return [...prev, currentEntityId];
      }
      return prev;
    });
    setCurrentEntityId(entityId);
  }, [currentEntityId]);

  const goBack = useCallback(() => {
    setHistory((prev) => {
      if (prev.length === 0) {
        // No history - close the panel
        setCurrentEntityId(null);
        return [];
      }

      // Pop the last item from history
      const newHistory = prev.slice(0, -1);
      const previousEntityId = prev[prev.length - 1];
      setCurrentEntityId(previousEntityId);
      return newHistory;
    });
  }, []);

  const clear = useCallback(() => {
    setCurrentEntityId(null);
    setHistory([]);
  }, []);

  const getPath = useCallback(() => {
    if (currentEntityId === null) {
      return [];
    }
    return [...history, currentEntityId];
  }, [history, currentEntityId]);

  return {
    currentEntityId,
    history,
    canGoBack: history.length > 0 || currentEntityId !== null,
    navigateTo,
    goBack,
    clear,
    getPath,
  };
}
