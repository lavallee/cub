/**
 * ErrorDisplay - Reusable error display component for API errors and other failures.
 */

interface ErrorDisplayProps {
  title?: string;
  error: Error | string;
  onRetry?: () => void;
  className?: string;
}

/**
 * Displays an error message with optional retry functionality.
 *
 * Can be used for API errors, loading failures, or any other error states.
 */
export function ErrorDisplay({
  title = 'Error',
  error,
  onRetry,
  className = '',
}: ErrorDisplayProps) {
  const errorMessage = typeof error === 'string' ? error : error.message;

  return (
    <div class={`bg-red-50 border border-red-200 rounded-lg p-4 ${className}`}>
      <div class="flex items-start gap-3">
        <div class="flex-shrink-0">
          <svg
            class="w-5 h-5 text-red-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-red-800 font-semibold text-sm">{title}</p>
          <p class="text-red-600 text-sm mt-1 break-words">{errorMessage}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              class="mt-3 text-sm font-medium text-red-700 hover:text-red-800 underline"
            >
              Try again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Inline error display for smaller spaces (like within cards)
 */
export function InlineError({ message }: { message: string }) {
  return (
    <div class="flex items-center gap-2 text-red-600 text-xs">
      <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <span>{message}</span>
    </div>
  );
}

/**
 * Full-screen error display for critical failures
 */
export function FullScreenError({
  title = 'Error',
  error,
  onRetry,
}: {
  title?: string;
  error: Error | string;
  onRetry?: () => void;
}) {
  const errorMessage = typeof error === 'string' ? error : error.message;

  return (
    <div class="flex items-center justify-center min-h-screen bg-gray-100 p-4">
      <div class="max-w-md w-full bg-white rounded-lg shadow-lg p-6">
        <div class="flex items-center gap-3 mb-4">
          <div class="flex-shrink-0">
            <svg
              class="w-8 h-8 text-red-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
          <div>
            <h2 class="text-lg font-semibold text-gray-900">{title}</h2>
          </div>
        </div>

        <div class="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
          <p class="text-sm text-red-800 break-words">{errorMessage}</p>
        </div>

        {onRetry && (
          <button
            onClick={onRetry}
            class="w-full bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            Try Again
          </button>
        )}
      </div>
    </div>
  );
}
