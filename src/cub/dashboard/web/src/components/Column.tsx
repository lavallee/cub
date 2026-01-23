/**
 * Column component - displays a single stage column in the kanban board.
 */

import type { BoardColumn } from '../types/api';
import { EntityCard } from './EntityCard';

export interface ColumnProps {
  column: BoardColumn;
  onEntityClick?: (entity: any) => void;
}

/**
 * Renders a single kanban column with entities.
 *
 * Shows column title, count, and entity cards.
 */
export function Column({ column, onEntityClick }: ColumnProps) {
  return (
    <div class="flex flex-col bg-gray-50 rounded-lg p-4 min-w-[280px] max-w-[320px]">
      {/* Column header */}
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide">
          {column.title}
        </h2>
        <span class="text-xs font-medium text-gray-500 bg-gray-200 rounded-full px-2 py-1">
          {column.count}
        </span>
      </div>

      {/* Entity cards */}
      <div class="flex-1 overflow-y-auto space-y-2">
        {column.entities.length === 0 ? (
          <p class="text-xs text-gray-400 text-center py-4">No items</p>
        ) : (
          column.entities.map((entity) => (
            <EntityCard
              key={entity.id}
              entity={entity}
              onClick={onEntityClick}
            />
          ))
        )}
      </div>
    </div>
  );
}
