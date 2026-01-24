/**
 * StatsBar component - displays quick metrics for the board.
 */

import type { BoardStats, Stage } from '../types/api';

export interface StatsBarProps {
  stats: BoardStats;
  showCost?: boolean;
  showTokens?: boolean;
  showDuration?: boolean;
}

/**
 * Renders a compact statistics bar showing entity counts by stage and metrics.
 *
 * Features:
 * - Total entity count
 * - Entity counts by stage (with visual indicators)
 * - Optional cost and token metrics
 * - Information-dense design with no clutter
 * - Responsive layout that adapts to available space
 */
export function StatsBar({
  stats,
  showCost = true,
  showTokens = true,
  showDuration = false,
}: StatsBarProps) {
  // Define stage order for consistent display (10-column workflow)
  const stageOrder: Stage[] = [
    'CAPTURES',
    'RESEARCHING',
    'PLANNED',
    'BLOCKED',
    'READY',
    'IN_PROGRESS',
    'COMPLETE',
    'NEEDS_REVIEW',
    'VALIDATED',
    'RELEASED',
  ];

  // Define stage display properties
  const stageConfig: Record<
    Stage,
    { label: string; color: string; bgColor: string }
  > = {
    CAPTURES: { label: 'Captures', color: 'text-gray-600', bgColor: 'bg-gray-100' },
    RESEARCHING: { label: 'Research', color: 'text-blue-600', bgColor: 'bg-blue-50' },
    PLANNED: { label: 'Planned', color: 'text-purple-600', bgColor: 'bg-purple-50' },
    BLOCKED: { label: 'Blocked', color: 'text-red-600', bgColor: 'bg-red-50' },
    READY: { label: 'Ready', color: 'text-yellow-600', bgColor: 'bg-yellow-50' },
    IN_PROGRESS: { label: 'In Progress', color: 'text-orange-600', bgColor: 'bg-orange-50' },
    COMPLETE: { label: 'Dev Complete', color: 'text-green-600', bgColor: 'bg-green-50' },
    NEEDS_REVIEW: { label: 'Review', color: 'text-pink-600', bgColor: 'bg-pink-50' },
    VALIDATED: { label: 'Validated', color: 'text-indigo-600', bgColor: 'bg-indigo-50' },
    RELEASED: { label: 'Released', color: 'text-emerald-600', bgColor: 'bg-emerald-50' },
  };

  return (
    <div class="bg-white border-b border-gray-200 px-6 py-3">
      <div class="flex items-center justify-between gap-4 flex-wrap">
        {/* Total and by-stage counts */}
        <div class="flex items-center gap-3 flex-wrap">
          <div class="flex items-baseline gap-1">
            <span class="text-lg font-bold text-gray-900">{stats.total}</span>
            <span class="text-xs text-gray-500">total</span>
          </div>

          {/* Stage breakdown pills */}
          <div class="flex items-center gap-2 flex-wrap">
            {stageOrder.map((stage) => {
              const count = stats.by_stage[stage] || 0;
              if (count === 0) return null;

              const config = stageConfig[stage];
              return (
                <div
                  key={stage}
                  class={`${config.bgColor} rounded-full px-2.5 py-1 flex items-center gap-1`}
                  title={`${config.label}: ${count}`}
                >
                  <span class={`text-xs font-semibold ${config.color}`}>
                    {count}
                  </span>
                  <span class={`text-xs text-gray-600`}>
                    {config.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Metrics section */}
        <div class="flex items-center gap-4 flex-wrap ml-auto">
          {/* Cost metric */}
          {showCost && stats.cost_total > 0 && (
            <div class="flex items-center gap-1 px-3 py-1 bg-gray-50 rounded-md">
              <span class="text-xs text-gray-500">Cost:</span>
              <span class="text-sm font-semibold text-gray-900">
                ${stats.cost_total.toFixed(2)}
              </span>
            </div>
          )}

          {/* Token metric */}
          {showTokens && stats.tokens_total > 0 && (
            <div class="flex items-center gap-1 px-3 py-1 bg-gray-50 rounded-md">
              <span class="text-xs text-gray-500">Tokens:</span>
              <span class="text-sm font-semibold text-gray-900">
                {stats.tokens_total.toLocaleString()}
              </span>
            </div>
          )}

          {/* Duration metric */}
          {showDuration && stats.duration_total_seconds > 0 && (
            <div class="flex items-center gap-1 px-3 py-1 bg-gray-50 rounded-md">
              <span class="text-xs text-gray-500">Duration:</span>
              <span class="text-sm font-semibold text-gray-900">
                {formatDuration(stats.duration_total_seconds)}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Format duration from seconds to human-readable format.
 *
 * @param seconds Total seconds
 * @returns Formatted duration string (e.g., "2h 30m", "45m", "30s")
 */
function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;

  if (remainingMinutes === 0) {
    return `${hours}h`;
  }

  return `${hours}h ${remainingMinutes}m`;
}
