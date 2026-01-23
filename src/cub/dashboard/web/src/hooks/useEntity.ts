/**
 * Hook for fetching and managing entity detail data from the Dashboard API.
 */

import { useEffect, useState } from 'preact/hooks';
import { apiClient } from '../api/client';
import type { EntityDetail } from '../types/api';

export interface UseEntityResult {
  data: EntityDetail | null;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
}

/**
 * Fetches detailed entity information from the API.
 *
 * @param entityId - The ID of the entity to fetch (null to skip fetching)
 * @returns Entity detail data, loading state, error state, and refetch function
 */
export function useEntity(entityId: string | null): UseEntityResult {
  const [data, setData] = useState<EntityDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchEntity = async () => {
    if (!entityId) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.getEntity(entityId);
      setData(response);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch entity data'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEntity();
  }, [entityId]);

  return {
    data,
    loading,
    error,
    refetch: fetchEntity,
  };
}
