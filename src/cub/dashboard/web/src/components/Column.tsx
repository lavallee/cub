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
          <div class="flex flex-col items-center justify-center py-8 text-center">
            <svg
              class="w-12 h-12 text-gray-300 mb-2"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
              />
            </svg>
            <p class="text-xs text-gray-400 font-medium">No items</p>
          </div>
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
