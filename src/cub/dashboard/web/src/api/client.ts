/**
 * Typed API client for the Dashboard API.
 *
 * Provides a type-safe wrapper around fetch for consuming the FastAPI backend.
 */

import type { ApiError, BoardResponse, BoardStats, EntityDetail, ViewSummary } from '../types/api';

/**
 * Base API configuration
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

/**
 * Custom error class for API errors
 */
export class ApiClientError extends Error {
  status: number;
  detail?: string;

  constructor(
    message: string,
    status: number,
    detail?: string,
  ) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Generic fetch wrapper with error handling and type safety
 */
async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      let errorDetail = `HTTP ${response.status}: ${response.statusText}`;

      try {
        const errorData = await response.json() as ApiError;
        errorDetail = errorData.detail || errorDetail;
      } catch {
        // If parsing error response fails, use default error message
      }

      throw new ApiClientError(
        `API request failed: ${errorDetail}`,
        response.status,
        errorDetail,
      );
    }

    return await response.json() as T;
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }

    // Network or other errors
    throw new ApiClientError(
      `Network error: ${error instanceof Error ? error.message : 'Unknown error'}`,
      0,
    );
  }
}

/**
 * API client with typed methods for each endpoint
 */
export const apiClient = {
  /**
   * Get full board data for Kanban visualization
   * GET /api/board
   */
  getBoard: async (): Promise<BoardResponse> => {
    return fetchApi<BoardResponse>('/api/board');
  },

  /**
   * Get board statistics without full entity data
   * GET /api/board/stats
   */
  getBoardStats: async (): Promise<BoardStats> => {
    return fetchApi<BoardStats>('/api/board/stats');
  },

  /**
   * Get detailed entity information
   * GET /api/entity/{id}
   */
  getEntity: async (id: string): Promise<EntityDetail> => {
    return fetchApi<EntityDetail>(`/api/entity/${encodeURIComponent(id)}`);
  },

  /**
   * List available views
   * GET /api/views
   */
  getViews: async (): Promise<ViewSummary[]> => {
    return fetchApi<ViewSummary[]>('/api/views');
  },

  /**
   * Get specific view configuration
   * GET /api/views/{view_id}
   */
  getView: async (viewId: string): Promise<BoardResponse> => {
    return fetchApi<BoardResponse>(`/api/views/${encodeURIComponent(viewId)}`);
  },

  /**
   * Health check
   * GET /health
   */
  health: async (): Promise<{ status: string }> => {
    return fetchApi<{ status: string }>('/health');
  },
};
