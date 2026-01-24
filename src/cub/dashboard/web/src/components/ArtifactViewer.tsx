/**
 * ArtifactViewer component - renders spec/plan content with markdown and syntax highlighting.
 */

import { useState, useEffect } from 'preact/hooks';
import { marked } from 'marked';
import hljs from 'highlight.js';
import 'highlight.js/styles/github.css';

export interface ArtifactViewerProps {
  sourcePath: string;
  entityType: string;
}

/**
 * Renders artifact content with markdown parsing and syntax highlighting for code blocks.
 *
 * Features:
 * - Fetches artifact content from /api/artifact endpoint
 * - Renders markdown with syntax-highlighted code blocks
 * - "View Source" button to open raw file
 * - Loading and error states
 */
export function ArtifactViewer({ sourcePath, entityType }: ArtifactViewerProps) {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Configure marked options
  useEffect(() => {
    marked.setOptions({
      breaks: true,
      gfm: true,
    });
  }, []);

  // Fetch artifact content
  useEffect(() => {
    if (!sourcePath) {
      setError('No source path provided');
      setLoading(false);
      return;
    }

    const fetchArtifact = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `/api/artifact?path=${encodeURIComponent(sourcePath)}`
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
          throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        const data = await response.json();
        setContent(data.content);
      } catch (err) {
        console.error('Failed to fetch artifact:', err);
        setError(err instanceof Error ? err.message : 'Failed to load artifact');
      } finally {
        setLoading(false);
      }
    };

    fetchArtifact();
  }, [sourcePath]);

  // Render markdown to HTML with syntax highlighting
  const renderMarkdown = (markdown: string): string => {
    try {
      const html = marked.parse(markdown) as string;

      // Post-process to add syntax highlighting to code blocks
      const div = document.createElement('div');
      div.innerHTML = html;

      // Find all code blocks and apply highlight.js
      const codeBlocks = div.querySelectorAll('pre code');
      codeBlocks.forEach((block) => {
        const codeElement = block as HTMLElement;
        const langMatch = codeElement.className.match(/language-(\w+)/);

        if (langMatch && langMatch[1]) {
          const lang = langMatch[1];
          if (hljs.getLanguage(lang)) {
            try {
              const highlighted = hljs.highlight(codeElement.textContent || '', { language: lang });
              codeElement.innerHTML = highlighted.value;
              codeElement.classList.add('hljs');
            } catch (err) {
              console.error('Syntax highlighting error:', err);
            }
          }
        } else {
          // Auto-detect language
          try {
            const highlighted = hljs.highlightAuto(codeElement.textContent || '');
            codeElement.innerHTML = highlighted.value;
            codeElement.classList.add('hljs');
          } catch (err) {
            console.error('Auto syntax highlighting error:', err);
          }
        }
      });

      return div.innerHTML;
    } catch (err) {
      console.error('Markdown parsing error:', err);
      return `<pre>${markdown}</pre>`;
    }
  };

  // Determine if content should be rendered as markdown
  const shouldRenderAsMarkdown = (): boolean => {
    // Render as markdown for specs, plans, and .md files
    if (entityType === 'spec' || entityType === 'plan') {
      return true;
    }
    if (sourcePath.endsWith('.md')) {
      return true;
    }
    return false;
  };

  // Open raw file in new window
  const handleViewSource = () => {
    window.open(`/api/artifact?path=${encodeURIComponent(sourcePath)}`, '_blank');
  };

  if (loading) {
    return (
      <div class="flex items-center justify-center py-8">
        <div class="text-gray-500">Loading artifact...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div class="bg-red-50 border border-red-200 rounded-lg p-4">
        <p class="text-red-800 font-semibold">Error loading artifact</p>
        <p class="text-red-600 text-sm mt-1">{error}</p>
      </div>
    );
  }

  if (!content) {
    return (
      <div class="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <p class="text-gray-500 text-sm">No content available</p>
      </div>
    );
  }

  return (
    <div class="space-y-3">
      {/* Header with View Source button */}
      <div class="flex items-center justify-between">
        <h4 class="font-semibold text-gray-900">Artifact Content</h4>
        <button
          onClick={handleViewSource}
          class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 hover:border-gray-400 transition-colors"
          aria-label="View raw source file"
        >
          <svg
            class="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
          View Source
        </button>
      </div>

      {/* Content area */}
      <div class="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {shouldRenderAsMarkdown() ? (
          <div
            class="prose prose-sm max-w-none p-6 prose-headings:font-semibold prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline prose-code:text-sm prose-code:bg-gray-100 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-gray-900 prose-pre:text-gray-100"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
          />
        ) : (
          <pre class="p-6 text-sm text-gray-800 whitespace-pre-wrap font-mono overflow-x-auto">
            {content}
          </pre>
        )}
      </div>
    </div>
  );
}
