/**
 * KanbanBoard component - main board view displaying all columns.
 */

import { useState } from 'preact/hooks';
import { useBoard } from '../hooks/useBoard';
import { useNavigation } from '../hooks/useNavigation';
import { Column } from './Column';
import { DetailPanel } from './DetailPanel';
import { ViewSwitcher } from './ViewSwitcher';
import type { DashboardEntity } from '../types/api';

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
  const { data, loading, error } = useBoard(selectedViewId);
  const navigation = useNavigation();

  if (loading) {
    return (
      <div class="flex items-center justify-center h-screen">
        <div class="text-gray-500">Loading board...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div class="flex items-center justify-center h-screen">
        <div class="text-red-500">
          <p class="font-semibold">Error loading board</p>
          <p class="text-sm mt-1">{error.message}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div class="flex items-center justify-center h-screen">
        <div class="text-gray-500">No board data available</div>
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

  return (
    <div class="h-screen flex flex-col bg-gray-100">
      {/* Board header */}
      <div class="bg-white border-b border-gray-200 px-6 py-4">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <h1 class="text-2xl font-bold text-gray-900">
              {data.view.name}
            </h1>
            {data.view.description && (
              <p class="text-sm text-gray-600 mt-1">{data.view.description}</p>
            )}
            <div class="flex gap-4 mt-2 text-xs text-gray-500">
              <span>Total: {data.stats.total}</span>
              {data.stats.cost_total > 0 && (
                <span>Cost: ${data.stats.cost_total.toFixed(2)}</span>
              )}
              {data.stats.tokens_total > 0 && (
                <span>Tokens: {data.stats.tokens_total.toLocaleString()}</span>
              )}
            </div>
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

      {/* Scrollable board columns */}
      <div class="flex-1 overflow-x-auto overflow-y-hidden">
        <div class="flex gap-4 p-6 h-full">
          {data.columns.map((column) => (
            <Column
              key={column.id}
              column={column}
              onEntityClick={handleEntityClick}
            />
          ))}
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
