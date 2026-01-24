/**
 * ErrorBoundary - Catches and displays React errors gracefully.
 *
 * Provides a fallback UI when a component throws an error,
 * preventing the entire app from crashing.
 */

import { Component } from 'preact';
import type { ComponentChildren } from 'preact';

interface ErrorBoundaryProps {
  children: ComponentChildren;
  fallback?: (error: Error, reset: () => void) => ComponentChildren;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Error boundary component that catches JavaScript errors anywhere in the child component tree.
 *
 * Usage:
 * ```tsx
 * <ErrorBoundary>
 *   <YourComponent />
 * </ErrorBoundary>
 * ```
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
    };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  reset = () => {
    this.setState({
      hasError: false,
      error: null,
    });
  };

  render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.reset);
      }

      return <ErrorFallback error={this.state.error} onReset={this.reset} />;
    }

    return this.props.children;
  }
}

/**
 * Default error fallback UI
 */
function ErrorFallback({ error, onReset }: { error: Error; onReset: () => void }) {
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
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <div>
            <h2 class="text-lg font-semibold text-gray-900">Something went wrong</h2>
            <p class="text-sm text-gray-600 mt-1">
              The application encountered an unexpected error.
            </p>
          </div>
        </div>

        <div class="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
          <p class="text-sm font-mono text-red-800 break-all">{error.message}</p>
        </div>

        <div class="flex gap-3">
          <button
            onClick={onReset}
            class="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            Try Again
          </button>
          <button
            onClick={() => window.location.reload()}
            class="flex-1 bg-gray-200 text-gray-800 px-4 py-2 rounded-lg hover:bg-gray-300 transition-colors font-medium"
          >
            Reload Page
          </button>
        </div>

        <details class="mt-4">
          <summary class="text-sm text-gray-600 cursor-pointer hover:text-gray-800">
            Technical details
          </summary>
          <pre class="mt-2 text-xs font-mono text-gray-700 bg-gray-50 rounded p-2 overflow-auto max-h-40">
            {error.stack}
          </pre>
        </details>
      </div>
    </div>
  );
}
