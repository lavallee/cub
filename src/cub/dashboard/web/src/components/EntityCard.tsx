/**
 * EntityCard component - displays a single entity in the kanban board.
 */

import type { DashboardEntity } from '../types/api';

export interface EntityCardProps {
  entity: DashboardEntity;
  onClick?: (entity: DashboardEntity) => void;
}

/**
 * Renders a single entity card with basic information.
 *
 * Minimal initial implementation - shows just title and type.
 */
export function EntityCard({ entity, onClick }: EntityCardProps) {
  const handleClick = () => {
    if (onClick) {
      onClick(entity);
    }
  };

  return (
    <div
      class="bg-white rounded-lg shadow-sm border border-gray-200 p-3 mb-2 cursor-pointer hover:shadow-md transition-shadow"
      onClick={handleClick}
    >
      <div class="flex items-start justify-between gap-2">
        <h3 class="text-sm font-medium text-gray-900 flex-1 line-clamp-2">
          {entity.title}
        </h3>
        <span class="text-xs text-gray-500 uppercase flex-shrink-0">
          {entity.type}
        </span>
      </div>
      {entity.description && (
        <p class="text-xs text-gray-600 mt-1 line-clamp-2">
          {entity.description}
        </p>
      )}
    </div>
  );
}
