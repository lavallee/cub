/**
 * KanbanBoard component - main board view displaying all columns.
 */

import { useState } from 'preact/hooks';
import { useBoard } from '../hooks/useBoard';
import { useNavigation } from '../hooks/useNavigation';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { Column } from './Column';
import { DetailPanel } from './DetailPanel';
import { StatsBar } from './StatsBar';
import { ViewSwitcher } from './ViewSwitcher';
import { BoardSkeleton } from './LoadingSkeleton';
import { FullScreenError } from './ErrorDisplay';
import type { BoardColumn, DashboardEntity, Stage } from '../types/api';
import { WORKFLOW_STAGES } from '../types/api';
import { apiClient } from '../api/client';

/**
 * Main kanban board component.
 *
 * Fetches board data and renders columns with horizontal scroll.
 * Shows loading and error states.
 * Manages detail panel state for viewing entity details.
 * Supports switching between different board view configurations.
 */
export function KanbanBoard() {
  const [selectedViewId, setSelectedViewId] = useState<string | undefined>();
  const { data, loading, error, refetch } = useBoard(selectedViewId);
  const navigation = useNavigation();

  if (loading) {
    return <BoardSkeleton />;
  }

  if (error) {
    return (
      <FullScreenError
        title="Error loading board"
        error={error}
        onRetry={refetch}
      />
    );
  }

  if (!data) {
    return (
      <div class="flex items-center justify-center h-screen bg-gray-100">
        <div class="text-center">
          <svg
            class="w-16 h-16 mx-auto text-gray-400 mb-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <p class="text-gray-500 text-lg font-medium">No board data available</p>
          <p class="text-gray-400 text-sm mt-2">Try refreshing the page</p>
        </div>
      </div>
    );
  }

  const handleEntityClick = (entity: DashboardEntity) => {
    navigation.navigateTo(entity.id);
  };

  const handleViewChange = (viewId: string) => {
    setSelectedViewId(viewId);
    navigation.clear();
  };

  // Handle drag-and-drop for workflow stage updates
  const handleDrop = async (entityId: string, targetStage: Stage) => {
    try {
      await apiClient.updateWorkflowStage(entityId, targetStage);
      refetch(); // Refresh the board to show updated position
    } catch (error) {
      console.error('Failed to update workflow stage:', error);
    }
  };

  // Check if a column is a workflow column (draggable)
  const isWorkflowColumn = (column: BoardColumn): boolean => {
    return WORKFLOW_STAGES.includes(column.stage);
  };

  // Separate columns into regular and workflow groups
  const regularColumns = data.columns.filter(col => !isWorkflowColumn(col));
  const workflowColumns = data.columns.filter(col => isWorkflowColumn(col));

  // Keyboard shortcuts
  useKeyboardShortcuts({
    shortcuts: [
      {
        key: 'Escape',
        handler: () => {
          if (navigation.currentEntityId) {
            navigation.clear();
          }
        },
        description: 'Close detail panel',
      },
      {
        key: 'r',
        handler: () => {
          refetch();
        },
        description: 'Refresh board',
      },
      {
        key: 'ArrowLeft',
        handler: () => {
          if (navigation.canGoBack) {
            navigation.goBack();
          }
        },
        description: 'Go back in navigation',
      },
    ],
    enabled: !loading && !error,
  });

  return (
    <div class="h-screen flex flex-col bg-gray-100">
      {/* Board header */}
      <div class="bg-white border-b border-gray-200 px-6 py-4">
        <div class="flex items-start justify-between mb-4">
          <div class="flex-1">
            <h1 class="text-2xl font-bold text-gray-900">
              {data.view.name}
            </h1>
            {data.view.description && (
              <p class="text-sm text-gray-600 mt-1">{data.view.description}</p>
            )}
          </div>
          <div class="ml-4 flex-shrink-0">
            <ViewSwitcher
              currentViewId={selectedViewId || data.view.id}
              onViewChange={handleViewChange}
              isLoading={loading}
            />
          </div>
        </div>
      </div>

      {/* Stats bar */}
      <StatsBar stats={data.stats} showCost={true} showTokens={true} />

      {/* Scrollable board columns */}
      <div class="flex-1 overflow-x-auto overflow-y-hidden">
        <div class="flex gap-4 p-6 h-full">
          {/* Regular columns (pre-completion stages) */}
          {regularColumns.map((column) => (
            <Column
              key={column.id}
              column={column}
              onEntityClick={handleEntityClick}
              isWorkflowColumn={false}
            />
          ))}

          {/* Workflow columns (post-completion stages) with grouped shading */}
          {workflowColumns.length > 0 && (
            <div class="flex gap-4 bg-gradient-to-b from-indigo-50 to-purple-50 rounded-xl p-3 border border-indigo-100">
              {workflowColumns.map((column) => (
                <Column
                  key={column.id}
                  column={column}
                  onEntityClick={handleEntityClick}
                  isWorkflowColumn={true}
                  onDrop={handleDrop}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Detail panel */}
      <DetailPanel
        entityId={navigation.currentEntityId}
        onClose={navigation.clear}
        onNavigate={navigation.navigateTo}
        navigationPath={navigation.getPath()}
      />
    </div>
  );
}
