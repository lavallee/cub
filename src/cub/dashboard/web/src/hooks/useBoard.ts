/**
 * Hook for fetching and managing board data from the Dashboard API.
 */

import { useEffect, useState } from 'preact/hooks';
import { apiClient } from '../api/client';
import type { BoardResponse, Stage } from '../types/api';

export interface UseBoardResult {
  data: BoardResponse | null;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
  /** Optimistically move an entity to a new stage in local state */
  moveEntity: (entityId: string, fromStage: Stage, toStage: Stage) => void;
}

/**
 * Fetches board data from the API with loading and error states.
 *
 * @param viewId - Optional specific view ID to fetch. If not provided, fetches the default board.
 * @returns Board data, loading state, error state, and refetch function
 */
export function useBoard(viewId?: string): UseBoardResult {
  const [data, setData] = useState<BoardResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchBoard = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = viewId
        ? await apiClient.getView(viewId)
        : await apiClient.getBoard();
      setData(response);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch board data'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBoard();
  }, [viewId]);

  /**
   * Optimistically move an entity from one column to another in local state.
   * This provides immediate UI feedback without waiting for API response.
   */
  const moveEntity = (entityId: string, fromStage: Stage, toStage: Stage) => {
    if (!data) return;

    setData(prevData => {
      if (!prevData) return prevData;

      // Find the entity in the source column
      const sourceColumn = prevData.columns.find(col => col.stage === fromStage);
      const targetColumn = prevData.columns.find(col => col.stage === toStage);

      if (!sourceColumn || !targetColumn) return prevData;

      const entityIndex = sourceColumn.entities.findIndex(e => e.id === entityId);
      if (entityIndex === -1) return prevData;

      // Get the entity and update its stage
      const movedEntity = { ...sourceColumn.entities[entityIndex], stage: toStage as Stage };

      // Create new columns array with updated entities
      const newColumns = prevData.columns.map(col => {
        if (col.stage === fromStage) {
          return {
            ...col,
            entities: col.entities.filter(e => e.id !== entityId),
            count: col.count - 1,
          };
        }
        if (col.stage === toStage) {
          return {
            ...col,
            entities: [movedEntity, ...col.entities],
            count: col.count + 1,
          };
        }
        return col;
      });

      return {
        ...prevData,
        columns: newColumns,
      };
    });
  };

  return {
    data,
    loading,
    error,
    refetch: fetchBoard,
    moveEntity,
  };
}
