# Cub Dashboard Web Frontend

Preact SPA for the Cub Dashboard Kanban board.

## Tech Stack

- **Vite**: Fast build tool and dev server
- **Preact**: Lightweight React alternative (3KB)
- **TypeScript**: Type-safe JavaScript
- **Tailwind CSS v4**: Utility-first CSS framework

## Project Structure

```
src/
├── api/
│   └── client.ts          # Typed API client for FastAPI backend
├── components/            # Preact components (to be added)
├── types/
│   └── api.ts            # TypeScript types matching Python models
├── app.tsx               # Root app component
├── main.tsx              # App entry point
└── index.css             # Global styles with Tailwind directives
```

## Development

### Prerequisites

- Node.js 18+ (npm comes with it)
- The FastAPI backend running on `http://localhost:8000`

### Setup

```bash
# Install dependencies
npm install

# Start dev server (with hot reload)
npm run dev
```

The dev server will start at `http://localhost:5173` (or another port if 5173 is in use).

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## Production Build

```bash
# Build for production
npm run build

# Output goes to ../static/ for serving by FastAPI
```

The build outputs to `../static/` so the FastAPI server can serve the frontend.

## Type Safety

All API types in `src/types/api.ts` match the Pydantic models in:
- `src/cub/core/dashboard/db/models.py`

When the backend models change, update the TypeScript types accordingly.

## API Client

The `apiClient` in `src/api/client.ts` provides typed methods for all endpoints:

```typescript
import { apiClient } from './api/client';

// Get board data
const board = await apiClient.getBoard();

// Get entity details
const entity = await apiClient.getEntity('cub-k8d.2');

// Health check
const health = await apiClient.health();
```

## Next Steps

- Implement `KanbanBoard` component (task cub-k8d.7)
- Implement `EntityCard` component (task cub-k8d.7)
- Add detail panel for entity inspection
- Add board statistics display
