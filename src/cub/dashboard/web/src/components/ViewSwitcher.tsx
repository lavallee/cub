/**
 * ViewSwitcher component - dropdown selector for board views.
 */

import { useEffect, useRef, useState } from 'preact/hooks';
import { apiClient } from '../api/client';
import type { ViewSummary } from '../types/api';

export interface ViewSwitcherProps {
  currentViewId?: string;
  onViewChange: (viewId: string) => void;
  isLoading?: boolean;
}

/**
 * ViewSwitcher dropdown component.
 *
 * Displays available views in a dropdown menu in the top-right of the header.
 * Allows users to switch between different board configurations
 * (Full Workflow, Sprint, Ideas, etc.).
 */
export function ViewSwitcher({ currentViewId, onViewChange, isLoading = false }: ViewSwitcherProps) {
  const [views, setViews] = useState<ViewSummary[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch available views on mount
  useEffect(() => {
    const loadViews = async () => {
      try {
        setLoading(true);
        const viewList = await apiClient.getViews();
        setViews(viewList);
        setError(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load views';
        setError(message);
        console.error('Error loading views:', err);
      } finally {
        setLoading(false);
      }
    };

    loadViews();
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Close dropdown when ESC key is pressed
  useEffect(() => {
    const handleEscKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscKey);
      return () => document.removeEventListener('keydown', handleEscKey);
    }
  }, [isOpen]);

  const handleViewSelect = (viewId: string) => {
    onViewChange(viewId);
    setIsOpen(false);
  };

  const currentView = views.find((v) => v.id === currentViewId) || views[0];
  const displayName = currentView?.name || 'Select View';

  if (error) {
    return (
      <div class="text-sm text-red-500" title={error}>
        Error loading views
      </div>
    );
  }

  if (loading || isLoading) {
    return (
      <div class="text-sm text-gray-400">
        Loading...
      </div>
    );
  }

  if (views.length === 0) {
    return null;
  }

  return (
    <div class="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isLoading}
        class="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span>{displayName}</span>
        <svg
          class={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 14l-7 7m0 0l-7-7m7 7V3"
          />
        </svg>
      </button>

      {isOpen && (
        <div
          class="absolute right-0 mt-2 w-48 bg-white border border-gray-300 rounded-lg shadow-lg z-50"
          role="listbox"
        >
          <div class="py-1 max-h-72 overflow-y-auto">
            {views.map((view) => (
              <button
                key={view.id}
                onClick={() => handleViewSelect(view.id)}
                class={`w-full text-left px-4 py-2 text-sm transition-colors ${
                  view.id === currentViewId
                    ? 'bg-blue-50 text-blue-700 font-medium'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
                role="option"
                aria-selected={view.id === currentViewId}
              >
                <div class="flex items-center justify-between">
                  <span>{view.name}</span>
                  {view.id === currentViewId && (
                    <svg class="w-4 h-4 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  )}
                </div>
                {view.description && (
                  <div class="text-xs text-gray-500 mt-1">{view.description}</div>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
