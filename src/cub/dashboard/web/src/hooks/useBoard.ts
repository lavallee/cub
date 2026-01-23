/**
 * Hook for fetching and managing board data from the Dashboard API.
 */

import { useEffect, useState } from 'preact/hooks';
import { apiClient } from '../api/client';
import type { BoardResponse } from '../types/api';

export interface UseBoardResult {
  data: BoardResponse | null;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
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

  return {
    data,
    loading,
    error,
    refetch: fetchBoard,
  };
}
