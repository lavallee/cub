/**
 * DetailPanel component - slides in from the right to show full entity details.
 */

import { useEffect } from 'preact/hooks';
import { useEntity } from '../hooks/useEntity';
import type { DashboardEntity, RelationType } from '../types/api';
import { ArtifactViewer } from './ArtifactViewer';
import { DetailPanelSkeleton } from './LoadingSkeleton';
import { ErrorDisplay } from './ErrorDisplay';

export interface DetailPanelProps {
  entityId: string | null;
  onClose: () => void;
  onNavigate?: (entityId: string) => void;
  navigationPath?: string[];
}

/**
 * Renders a sidebar panel with detailed entity information, relationships, and content.
 *
 * Features:
 * - Slides in from the right when an entity is selected
 * - Shows loading/error states
 * - Displays entity metadata, relationships, and full content
 * - Click outside or ESC key to close
 */
export function DetailPanel({ entityId, onClose, onNavigate, navigationPath = [] }: DetailPanelProps) {
  const { data, loading, error, refetch } = useEntity(entityId);

  // Handle ESC key to close panel
  useEffect(() => {
    if (!entityId) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [entityId, onClose]);

  // Don't render if no entity is selected
  if (!entityId) {
    return null;
  }

  return (
    <>
      {/* Backdrop overlay */}
      <div
        class="fixed inset-0 bg-black bg-opacity-25 z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Sidebar panel */}
      <div class="fixed top-0 right-0 bottom-0 w-full md:w-2/3 lg:w-1/2 xl:w-1/3 bg-white shadow-2xl z-50 overflow-y-auto">
        {/* Header */}
        <div class="sticky top-0 bg-white border-b border-gray-200 px-6 py-4">
          <div class="flex items-center justify-between mb-2">
            <h2 class="text-lg font-semibold text-gray-900">Entity Details</h2>
            <button
              onClick={onClose}
              class="text-gray-400 hover:text-gray-600 transition-colors"
              aria-label="Close panel"
            >
              <svg
                class="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
          {/* Breadcrumb navigation */}
          {navigationPath.length > 1 && (
            <div class="flex items-center gap-2 text-sm text-gray-600 overflow-x-auto">
              <button
                onClick={onClose}
                class="flex items-center gap-1 hover:text-gray-900 transition-colors flex-shrink-0"
                aria-label="Back to board"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12h18M3 12l6-6m-6 6l6 6" />
                </svg>
                Board
              </button>
              {navigationPath.slice(0, -1).map((id) => (
                <span key={id} class="flex items-center gap-2 flex-shrink-0">
                  <span class="text-gray-400">/</span>
                  <button
                    onClick={() => onNavigate?.(id)}
                    class="hover:text-gray-900 transition-colors truncate max-w-[120px]"
                    title={id}
                  >
                    {id}
                  </button>
                </span>
              ))}
              <span class="text-gray-400 flex-shrink-0">/</span>
              <span class="font-medium text-gray-900 truncate max-w-[120px]" title={navigationPath[navigationPath.length - 1]}>
                {navigationPath[navigationPath.length - 1]}
              </span>
            </div>
          )}
        </div>

        {/* Content */}
        <div class="px-6 py-4">
          {loading && <DetailPanelSkeleton />}

          {error && (
            <ErrorDisplay
              title="Error loading entity"
              error={error}
              onRetry={refetch}
            />
          )}

          {data && (
            <>
              {/* Entity metadata */}
              <section class="mb-6">
                <div class="flex items-start justify-between mb-3">
                  <div class="flex-1">
                    <h3 class="text-xl font-bold text-gray-900 mb-1">
                      {data.entity.title}
                    </h3>
                    <div class="flex gap-2 flex-wrap">
                      <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        {data.entity.type}
                      </span>
                      <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        {data.entity.stage}
                      </span>
                      {data.entity.status && (
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                          {data.entity.status}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {data.entity.description && (
                  <p class="text-gray-700 text-sm mb-4">
                    {data.entity.description}
                  </p>
                )}

                {/* Metadata grid */}
                <div class="grid grid-cols-2 gap-3 text-sm">
                  {data.entity.id && (
                    <div>
                      <span class="font-medium text-gray-500">ID:</span>
                      <span class="ml-2 text-gray-900 font-mono text-xs">
                        {data.entity.id}
                      </span>
                    </div>
                  )}
                  {data.entity.priority !== null && data.entity.priority !== undefined && (
                    <div>
                      <span class="font-medium text-gray-500">Priority:</span>
                      <span class="ml-2 text-gray-900">{data.entity.priority}</span>
                    </div>
                  )}
                  {data.entity.created_at && (
                    <div>
                      <span class="font-medium text-gray-500">Created:</span>
                      <span class="ml-2 text-gray-900">
                        {new Date(data.entity.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                  {data.entity.updated_at && (
                    <div>
                      <span class="font-medium text-gray-500">Updated:</span>
                      <span class="ml-2 text-gray-900">
                        {new Date(data.entity.updated_at).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                  {data.entity.completed_at && (
                    <div>
                      <span class="font-medium text-gray-500">Completed:</span>
                      <span class="ml-2 text-gray-900">
                        {new Date(data.entity.completed_at).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                  {data.entity.source_path && (
                    <div class="col-span-2">
                      <span class="font-medium text-gray-500">Source:</span>
                      <span class="ml-2 text-gray-900 font-mono text-xs break-all">
                        {data.entity.source_path}
                      </span>
                    </div>
                  )}
                </div>

                {/* Labels */}
                {data.entity.labels && data.entity.labels.length > 0 && (
                  <div class="mt-3">
                    <span class="font-medium text-gray-500 text-sm">Labels:</span>
                    <div class="flex gap-2 flex-wrap mt-1">
                      {data.entity.labels.map((label) => (
                        <span
                          key={label}
                          class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800"
                        >
                          {label}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Metrics */}
                {(data.entity.cost_usd || data.entity.tokens || data.entity.duration_seconds) && (
                  <div class="mt-4 pt-4 border-t border-gray-200">
                    <h4 class="font-medium text-gray-700 text-sm mb-2">Metrics</h4>
                    <div class="grid grid-cols-2 gap-3 text-sm">
                      {data.entity.cost_usd !== null && data.entity.cost_usd !== undefined && (
                        <div>
                          <span class="font-medium text-gray-500">Cost:</span>
                          <span class="ml-2 text-gray-900">
                            ${data.entity.cost_usd.toFixed(2)}
                          </span>
                        </div>
                      )}
                      {data.entity.tokens !== null && data.entity.tokens !== undefined && (
                        <div>
                          <span class="font-medium text-gray-500">Tokens:</span>
                          <span class="ml-2 text-gray-900">
                            {data.entity.tokens.toLocaleString()}
                          </span>
                        </div>
                      )}
                      {data.entity.duration_seconds !== null &&
                        data.entity.duration_seconds !== undefined && (
                          <div>
                            <span class="font-medium text-gray-500">Duration:</span>
                            <span class="ml-2 text-gray-900">
                              {formatDuration(data.entity.duration_seconds)}
                            </span>
                          </div>
                        )}
                      {data.entity.verification_status && (
                        <div>
                          <span class="font-medium text-gray-500">Verification:</span>
                          <span class="ml-2 text-gray-900">
                            {data.entity.verification_status}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </section>

              {/* Relationships */}
              {Object.keys(data.relationships).length > 0 && (
                <section class="mb-6">
                  <h4 class="font-semibold text-gray-900 mb-3">Relationships</h4>
                  <div class="space-y-3">
                    {Object.entries(data.relationships).map(([relType, related]) => {
                      if (!related) return null;

                      const entities = Array.isArray(related) ? related : [related];
                      if (entities.length === 0) return null;

                      return (
                        <div
                          key={relType}
                          class="bg-gray-50 rounded-lg p-3 border border-gray-200"
                        >
                          <div class="font-medium text-gray-700 text-sm mb-2 capitalize">
                            {formatRelationType(relType as RelationType)} ({entities.length})
                          </div>
                          <div class="space-y-2">
                            {entities.map((entity: DashboardEntity) => (
                              <button
                                key={entity.id}
                                onClick={() => onNavigate?.(entity.id)}
                                class="w-full bg-white rounded p-2 border border-gray-200 text-sm hover:border-blue-400 hover:bg-blue-50 transition-colors cursor-pointer text-left group"
                                disabled={!onNavigate}
                              >
                                <div class="font-medium text-gray-900 group-hover:text-blue-700 flex items-center gap-1">
                                  {entity.title}
                                  {onNavigate && (
                                    <svg
                                      class="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity"
                                      fill="none"
                                      stroke="currentColor"
                                      viewBox="0 0 24 24"
                                    >
                                      <path
                                        stroke-linecap="round"
                                        stroke-linejoin="round"
                                        stroke-width="2"
                                        d="M9 5l7 7-7 7"
                                      />
                                    </svg>
                                  )}
                                </div>
                                <div class="text-gray-500 text-xs mt-0.5">
                                  {entity.type} • {entity.stage}
                                </div>
                              </button>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}

              {/* Content - Use ArtifactViewer for entities with source_path */}
              {data.entity.source_path && (
                <section class="mb-6">
                  <ArtifactViewer
                    sourcePath={data.entity.source_path}
                    entityType={data.entity.type}
                  />
                </section>
              )}

              {/* Fallback: Show inline content if no source_path */}
              {!data.entity.source_path && data.content && (
                <section class="mb-6">
                  <h4 class="font-semibold text-gray-900 mb-3">Content</h4>
                  <div class="bg-gray-50 rounded-lg p-4 border border-gray-200">
                    <pre class="text-sm text-gray-800 whitespace-pre-wrap font-mono overflow-x-auto">
                      {data.content}
                    </pre>
                  </div>
                </section>
              )}

              {/* Frontmatter */}
              {data.entity.frontmatter &&
                Object.keys(data.entity.frontmatter).length > 0 && (
                  <section class="mb-6">
                    <h4 class="font-semibold text-gray-900 mb-3">Frontmatter</h4>
                    <div class="bg-gray-50 rounded-lg p-4 border border-gray-200">
                      <pre class="text-sm text-gray-800 whitespace-pre-wrap font-mono overflow-x-auto">
                        {JSON.stringify(data.entity.frontmatter, null, 2)}
                      </pre>
                    </div>
                  </section>
                )}
            </>
          )}
        </div>
      </div>
    </>
  );
}

/**
 * Format duration in seconds to human-readable format
 */
function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds}s`;
  } else if (seconds < 3600) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  } else {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${mins}m`;
  }
}

/**
 * Format relationship type for display
 */
function formatRelationType(relType: RelationType): string {
  return relType.replace(/_/g, ' ');
}
