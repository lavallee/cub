/**
 * Column component - displays a single stage column in the kanban board.
 */

import { useState } from 'preact/hooks';
import type { BoardColumn, DashboardEntity, EntityGroup, Stage } from '../types/api';
import { EntityCard } from './EntityCard';

export interface ColumnProps {
  column: BoardColumn;
  onEntityClick?: (entity: DashboardEntity) => void;
  isWorkflowColumn?: boolean;
  onDrop?: (entityId: string, targetStage: Stage) => void;
}

interface EntityGroupProps {
  group: EntityGroup;
  onEntityClick?: (entity: DashboardEntity) => void;
  isDraggable?: boolean;
}

/**
 * Renders a group of entities with an optional group header.
 */
function EntityGroupComponent({ group, onEntityClick, isDraggable }: EntityGroupProps) {
  return (
    <div class="space-y-2">
      {/* Group header (spec or epic) */}
      {group.group_entity && (
        <div class="mb-2">
          <EntityCard
            entity={group.group_entity}
            onClick={onEntityClick}
            isDraggable={isDraggable}
          />
        </div>
      )}

      {/* Grouped entities (plans or tasks) */}
      <div class="ml-3 space-y-2 border-l-2 border-gray-300 pl-2">
        {group.entities.map((entity) => (
          <EntityCard
            key={entity.id}
            entity={entity}
            onClick={onEntityClick}
            isDraggable={isDraggable}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * Renders a single kanban column with entities.
 *
 * Shows column title, count, and entity cards.
 * Supports both flat and grouped entity display.
 * Workflow columns support drag-and-drop for stage updates.
 */
export function Column({ column, onEntityClick, isWorkflowColumn, onDrop }: ColumnProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const hasGroups = column.groups && column.groups.length > 0;
  const hasEntities = column.entities && column.entities.length > 0;
  const isEmpty = !hasGroups && !hasEntities;

  // Handle drag events for workflow columns
  const handleDragOver = (e: DragEvent) => {
    if (!isWorkflowColumn) return;
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: DragEvent) => {
    if (!isWorkflowColumn || !onDrop) return;
    e.preventDefault();
    setIsDragOver(false);

    const entityId = e.dataTransfer?.getData('text/plain');
    if (entityId) {
      onDrop(entityId, column.stage);
    }
  };

  // Column styling - different for workflow columns
  const columnClass = isWorkflowColumn
    ? `flex flex-col bg-white/60 rounded-lg p-4 min-w-[280px] max-w-[320px] transition-all ${
        isDragOver ? 'ring-2 ring-indigo-400 bg-indigo-50/50' : ''
      }`
    : 'flex flex-col bg-gray-50 rounded-lg p-4 min-w-[280px] max-w-[320px]';

  return (
    <div
      class={columnClass}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
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
      <div class="flex-1 overflow-y-auto space-y-3">
        {isEmpty ? (
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
        ) : hasGroups ? (
          /* Render grouped entities */
          column.groups!.map((group, index) => (
            <EntityGroupComponent
              key={group.group_key || `group-${index}`}
              group={group}
              onEntityClick={onEntityClick}
              isDraggable={isWorkflowColumn}
            />
          ))
        ) : (
          /* Render flat list of entities */
          column.entities.map((entity) => (
            <EntityCard
              key={entity.id}
              entity={entity}
              onClick={onEntityClick}
              isDraggable={isWorkflowColumn}
            />
          ))
        )}
      </div>
    </div>
  );
}
