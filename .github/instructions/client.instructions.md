---
name: "Client Instructions"
applyTo: "client/**"
description: "Instructions for the React + TypeScript frontend (Vite, Zustand, Recharts)."
---

# Client Instructions (React / TypeScript)

## Technology Stack

- **React 18** — functional components only; no class components.
- **TypeScript 5** — strict typing everywhere; avoid `any`.
- **Vite** — dev server and production bundler.
- **Zustand 4** — lightweight state management; one store per concern.
- **Recharts 2** — chart library for all data visualisations.
- **Axios** — HTTP client via a pre-configured `apiClient` instance.
- **React Router 6** — client-side routing.
- **Vitest + Testing Library** — test runner with jsdom environment.

## Architecture

### Directory Structure

```
client/src/
  components/        Shared UI components (Layout, PanelHeader, PanelControls, …)
    panels/          Dashboard panel components (one file per panel)
  constants/         Static lookup tables (satellite IDs, colors)
  hooks/             Custom React hooks (data fetching, shared logic)
  pages/             Route-level page components
  dash/              Dashboard feature module (page, hooks, types, API)
  services/          API client & socket client
  store/             Zustand stores (one file per store)
  styles/            Global CSS (single file, CSS custom properties)
  types/             TypeScript interface definitions
  utils/             Pure utility functions (units, colors, time, deduplication)
```

### Component Patterns

- **Typed as `FC`** — all components use `const MyComponent: FC<Props> = (…) => { … }`.
- **Default exports** — components use `export default ComponentName`.
- **Props interfaces** — defined inline above the component in the same file.
- **No CSS modules** — all styling via a single `global.css` using BEM-like class names (`.panel__header`, `.button--micro-active`).
- **CSS custom properties** — colours, spacing, borders defined as `--color-*`, `--shadow-*` variables in `:root`.

### Panel Components

Each dashboard panel in `components/panels/` follows a consistent structure:

1. **Imports** — React hooks, then Recharts, then local services/utils/stores/types.
2. **Local types** — chart point interfaces, internal state types.
3. **Helper functions** — formatters, data transformers (outside the component).
4. **Component body**:
   - Selected nodes from `useSelectedNodesStore`.
   - Local state: `isLoading`, `error`, data (via `useState`).
   - `requestNodes` memo — normalise node selection.
   - Request deduplication via `useRef(createRequestDeduper())`.
   - `refresh` callback — fetches data from `apiClient`, updates state.
   - `useEffect` to trigger initial load.
   - Data transformation via `useMemo` chains.
   - Render: `<section className="panel">` → `<PanelHeader>` → `<div className="panel__body">`.

5. **PanelHeader composition** — panels use `PanelHeader` with `title`, `subtitle` (via `PanelSubtitle`), `onRefresh`, `isRefreshing`, and optional `controls` (using `PanelControls` + `PanelControlsButton`).

6. **Control state persistence** — panel controls (interval, layout mode, toggles) persist selections to `localStorage` using keys prefixed `monstr.panel.<PanelName>.<control>`. Initialise with `getStoredSelection<T>(key, allowedValues, default)` from `PanelControls`. For mutually-exclusive button groups, pass `storageKey` prop to `PanelControls` for automatic persistence. For checkboxes/booleans, persist manually in the change handler.

7. **Auto-refresh** — panels set up periodic refresh via `window.setInterval` (typically 600,000 ms = 10 min) inside a `useEffect`, with `clearInterval` cleanup on unmount. Guard the refresh with `if (!visible) return;`.

8. **`requestNodes` normalisation** — every panel that receives or reads `selectedNodes` normalises the "All" selection to an empty array for the backend: `selectedNodes.includes("All") ? [] : selectedNodes.filter(n => n !== "All")`.

9. **Reusable summary panes** — for totals/summary displays beside charts, reuse the `longterm-summary` CSS classes (`.longterm-summary`, `.longterm-summary__item`, `__label`, `__value`). These render as a flex-wrap row of rounded cards with a label and a value.

10. **Dual Y-axis ComposedChart** — when mixing series types (e.g., bars + areas, or lines at different scales), use `yAxisId` strings on every `<YAxis>` and every series component. Common pattern: left axis for primary data, right axis for secondary/accumulated data.

### State Management

- **Zustand stores** in `store/` — one file per store, named `use*Store.ts`.
- Stores export a **default export** of the `create(…)` result.
- **Interface-first** — define the state interface, then implement with `create<StateInterface>((set, get) => ({…}))`.
- **`localStorage` persistence** — some stores manually persist to `localStorage` (e.g., panel visibility, control selections). Use `monstr.*` key prefix.
- **No middleware** — stores are vanilla Zustand; no persist/devtools middleware.

### Data Fetching

- **`services/apiClient.ts`** — single `axios.create()` instance with `baseURL` pointing to `/api` (or `http://localhost:8000/api` in dev).
- Each fetch function is a **standalone async function** (not a hook) that:
  1. Calls `apiClient.post(…)` or `apiClient.get(…)`.
  2. **Defensively normalises** the response — handles both `camelCase` and `snake_case` field names from the server (e.g., `item.satelliteId ?? item.satellite_id`).
  3. Uses helper functions like `ensureNumber()` / `toNumeric()` for safe numeric coercion.
  4. Returns a strongly-typed result matching the interfaces in `types/`.
- **Request deduplication** — panels use `createRequestDeduper()` to avoid re-fetching identical data within a short window.
- **Error handling** — panels catch errors in the `refresh` callback, store an error message in local state, and render it in the panel body.

### Type Definitions

- **All shared types** live in `types/index.ts` — interfaces for API responses, domain objects.
- **Feature-local types** (e.g., `dash/types.ts`) for module-specific shapes.
- **Naming**: interfaces use PascalCase, fields use camelCase matching the serialised API output.
- **API response types** must match the backend `schemas.py` serialization aliases (camelCase). The fetch functions handle both cases defensively for robustness.
- When adding a new API response field, update **three places**: `types/index.ts` (interface), `services/apiClient.ts` (parsing), and the consuming component.

### Constants

- **`constants/satellites.ts`** — maps satellite IDs to human-readable names; `translateSatelliteId()` helper.
- **`constants/colors.ts`** — colour palette for charts and per-node visualisations.

### Utilities

- **`utils/units.ts`** — unit picking and formatting for rates (`bps`/`Kbps`/`Mbps`) and sizes (`B`/`KB`/…/`TB`). Uses `UnitDefinition` objects with `{ unit, factor }`.
- **`utils/requestDeduper.ts`** — prevents duplicate API calls within a time window. Supports `isDuplicate()` and `coalesce()` patterns.
- **`utils/colors.ts`** — per-node colour resolution for charts.
- **`utils/time.ts`** — time formatting helpers.
- Pure functions; no side effects. Named exports only.

## Import Ordering

Imports follow this sequence (separated by blank lines):

1. **React** — `react`, `react-dom`.
2. **Third-party** — `recharts`, `axios`, `react-router-dom`, `zustand`.
3. **Local services/utils** — `../../services/apiClient`, `../../utils/*`.
4. **Stores** — `../../store/*`.
5. **Types** — `import type { … } from "../../types"` (use `import type` for type-only imports).
6. **Components** — sibling or child components.

## Code Style

- **No `any`** — use `unknown` and narrow with type guards or `as Record<string, unknown>` casts.
- **`satisfies`** — use TypeScript's `satisfies` operator to validate object literals match an interface while preserving the narrower inferred type.
- **Numeric safety** — always wrap API numbers with a safe coercion helper (`Number.isFinite(parsed) ? parsed : 0`).
- **String safety** — wrap API strings with `String(value ?? "")`.
- **Optional fields** — use `?` for fields that may be absent from the API (e.g., `disqualifications?: DisqualEntry[]`).
- **Formatting** — Prettier with default settings.

## Testing

- **Framework**: Vitest with jsdom environment and `@testing-library/react`.
- **Setup**: `vitest.setup.ts` imports `@testing-library/jest-dom`.
- **Test files**: co-located with source (e.g., `App.test.tsx` next to `App.tsx`).
- **Pattern**: `describe` + `it` blocks; render components inside `<BrowserRouter>`.
- **Run**: `npm test` from the `client/` directory.

## Adding a New Panel Checklist

1. **Types** — add/update interfaces in `types/index.ts` for new API shapes.
2. **API client** — add or update the fetch function in `services/apiClient.ts`; defensively normalise both camelCase and snake_case fields.
3. **Component** — create or update the panel in `components/panels/`; follow the established panel pattern.
4. **Panel visibility store** — add the panel key (e.g., `myPanel: false`) to `DEFAULT_PANELS` in `store/usePanelVisibility.ts`.
5. **Settings toggle** — add a checkbox entry in `components/Settings.tsx` toggling the new panel key.
6. **Home page layout** — import the panel in `pages/Home.tsx`, add an `isVisible()` check, and render it in the correct position among existing panels.
7. **Store** — add a Zustand store in `store/` only if state needs to be shared across components; otherwise use local `useState`.
8. **Constants** — update `constants/` if new static lookup data is needed.
9. **Tests** — add tests; run `npm test`.

## Per-Source / Per-Node Data Handling

When implementing features that apply differently to individual nodes or satellites (e.g., disqualifications, vetting dates), accumulation and aggregation logic must track state **per source key** rather than as a single global counter. This prevents actions affecting one node from incorrectly resetting or altering data for other nodes when multiple nodes are selected or "All" is active.

Pattern: use a `Record<string, number>` (keyed by source/node name) for per-node running totals, apply per-node resets/adjustments, then `Object.values(…)` to sum for the combined display value.
