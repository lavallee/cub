/**
 * LoadingSkeleton - Animated loading placeholder components.
 *
 * Provides skeleton screens for various parts of the dashboard
 * to improve perceived performance while data is loading.
 */

/**
 * Generic skeleton box with shimmer animation
 */
export function SkeletonBox({ className = '' }: { className?: string }) {
  return (
    <div
      class={`animate-pulse bg-gray-200 rounded ${className}`}
      aria-hidden="true"
    />
  );
}

/**
 * Skeleton for an entity card in a column
 */
export function EntityCardSkeleton() {
  return (
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-3 mb-2">
      <div class="flex items-start justify-between gap-2">
        <SkeletonBox className="h-4 flex-1" />
        <SkeletonBox className="h-3 w-12" />
      </div>
      <SkeletonBox className="h-3 w-3/4 mt-2" />
    </div>
  );
}

/**
 * Skeleton for a kanban column
 */
export function ColumnSkeleton() {
  return (
    <div class="flex flex-col bg-gray-50 rounded-lg p-4 min-w-[280px] max-w-[320px]">
      {/* Column header */}
      <div class="flex items-center justify-between mb-3">
        <SkeletonBox className="h-4 w-24" />
        <SkeletonBox className="h-5 w-8 rounded-full" />
      </div>

      {/* Entity cards */}
      <div class="flex-1 space-y-2">
        <EntityCardSkeleton />
        <EntityCardSkeleton />
        <EntityCardSkeleton />
      </div>
    </div>
  );
}

/**
 * Full board loading skeleton with multiple columns
 */
export function BoardSkeleton() {
  return (
    <div class="h-screen flex flex-col bg-gray-100">
      {/* Board header */}
      <div class="bg-white border-b border-gray-200 px-6 py-4">
        <div class="flex items-start justify-between mb-4">
          <div class="flex-1">
            <SkeletonBox className="h-8 w-64 mb-2" />
            <SkeletonBox className="h-4 w-96" />
          </div>
          <SkeletonBox className="h-10 w-32 ml-4" />
        </div>
      </div>

      {/* Stats bar */}
      <div class="bg-white border-b border-gray-200 px-6 py-3">
        <div class="flex gap-6">
          <SkeletonBox className="h-4 w-32" />
          <SkeletonBox className="h-4 w-32" />
          <SkeletonBox className="h-4 w-32" />
        </div>
      </div>

      {/* Scrollable board columns */}
      <div class="flex-1 overflow-x-auto overflow-y-hidden">
        <div class="flex gap-4 p-6 h-full">
          <ColumnSkeleton />
          <ColumnSkeleton />
          <ColumnSkeleton />
          <ColumnSkeleton />
          <ColumnSkeleton />
        </div>
      </div>
    </div>
  );
}

/**
 * Skeleton for detail panel content
 */
export function DetailPanelSkeleton() {
  return (
    <div class="px-6 py-4 space-y-6">
      {/* Entity metadata */}
      <section>
        <SkeletonBox className="h-6 w-3/4 mb-2" />
        <div class="flex gap-2 mb-4">
          <SkeletonBox className="h-6 w-16 rounded-full" />
          <SkeletonBox className="h-6 w-20 rounded-full" />
          <SkeletonBox className="h-6 w-16 rounded-full" />
        </div>
        <SkeletonBox className="h-16 w-full mb-4" />

        {/* Metadata grid */}
        <div class="grid grid-cols-2 gap-3">
          <SkeletonBox className="h-4 w-full" />
          <SkeletonBox className="h-4 w-full" />
          <SkeletonBox className="h-4 w-full" />
          <SkeletonBox className="h-4 w-full" />
        </div>
      </section>

      {/* Relationships */}
      <section>
        <SkeletonBox className="h-5 w-32 mb-3" />
        <div class="space-y-3">
          <div class="bg-gray-50 rounded-lg p-3 border border-gray-200">
            <SkeletonBox className="h-4 w-24 mb-2" />
            <SkeletonBox className="h-16 w-full" />
          </div>
          <div class="bg-gray-50 rounded-lg p-3 border border-gray-200">
            <SkeletonBox className="h-4 w-24 mb-2" />
            <SkeletonBox className="h-16 w-full" />
          </div>
        </div>
      </section>

      {/* Content */}
      <section>
        <SkeletonBox className="h-5 w-24 mb-3" />
        <div class="bg-gray-50 rounded-lg p-4 border border-gray-200">
          <SkeletonBox className="h-4 w-full mb-2" />
          <SkeletonBox className="h-4 w-5/6 mb-2" />
          <SkeletonBox className="h-4 w-4/5 mb-2" />
          <SkeletonBox className="h-4 w-full" />
        </div>
      </section>
    </div>
  );
}
