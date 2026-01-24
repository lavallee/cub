/**
 * EntityCard component - displays a single entity in the kanban board.
 */

import { useState } from 'preact/hooks';
import type { DashboardEntity } from '../types/api';

export interface EntityCardProps {
  entity: DashboardEntity;
  onClick?: (entity: DashboardEntity) => void;
  isDraggable?: boolean;
}

/**
 * Renders a single entity card with basic information.
 *
 * Shows title, type, and optional description.
 * Draggable cards (in workflow columns) have a dashed border.
 */
export function EntityCard({ entity, onClick, isDraggable }: EntityCardProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleClick = () => {
    if (onClick) {
      onClick(entity);
    }
  };

  const handleDragStart = (e: DragEvent) => {
    if (!isDraggable) return;
    setIsDragging(true);
    // Store both entity ID and source stage for optimistic updates
    const dragData = JSON.stringify({ id: entity.id, stage: entity.stage });
    e.dataTransfer?.setData('application/json', dragData);
    e.dataTransfer?.setData('text/plain', entity.id); // Fallback
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = 'move';
    }
  };

  const handleDragEnd = () => {
    setIsDragging(false);
  };

  // Card styling - dashed border for draggable cards in workflow columns
  const cardClass = isDraggable
    ? `bg-white rounded-lg shadow-sm border-2 border-dashed border-indigo-300 p-3 mb-2 cursor-grab hover:shadow-md hover:border-indigo-400 transition-all ${
        isDragging ? 'opacity-50 cursor-grabbing' : ''
      }`
    : 'bg-white rounded-lg shadow-sm border border-gray-200 p-3 mb-2 cursor-pointer hover:shadow-md transition-shadow';

  return (
    <div
      class={cardClass}
      onClick={handleClick}
      draggable={isDraggable}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
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
      {/* Drag handle indicator for draggable cards */}
      {isDraggable && (
        <div class="flex justify-center mt-2 opacity-40">
          <svg class="w-4 h-4 text-indigo-400" fill="currentColor" viewBox="0 0 20 20">
            <path d="M7 2a2 2 0 1 0 .001 4.001A2 2 0 0 0 7 2zm0 6a2 2 0 1 0 .001 4.001A2 2 0 0 0 7 8zm0 6a2 2 0 1 0 .001 4.001A2 2 0 0 0 7 14zm6-8a2 2 0 1 0-.001-4.001A2 2 0 0 0 13 6zm0 2a2 2 0 1 0 .001 4.001A2 2 0 0 0 13 8zm0 6a2 2 0 1 0 .001 4.001A2 2 0 0 0 13 14z" />
          </svg>
        </div>
      )}
    </div>
  );
}
