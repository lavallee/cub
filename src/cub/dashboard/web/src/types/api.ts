/**
 * TypeScript types matching Python Pydantic models for the Dashboard API.
 *
 * These types are derived from src/cub/core/dashboard/db/models.py
 * and provide type safety for the frontend when consuming the API.
 */

// Enums as const objects with union types
export const EntityType = {
  CAPTURE: 'capture',
  SPEC: 'spec',
  PLAN: 'plan',
  EPIC: 'epic',
  TASK: 'task',
  LEDGER: 'ledger',
  RELEASE: 'release',
} as const;

export type EntityType = typeof EntityType[keyof typeof EntityType];

export const Stage = {
  CAPTURES: 'CAPTURES',
  SPECS: 'SPECS',
  PLANNED: 'PLANNED',
  READY: 'READY',
  IN_PROGRESS: 'IN_PROGRESS',
  NEEDS_REVIEW: 'NEEDS_REVIEW',
  COMPLETE: 'COMPLETE',
  RELEASED: 'RELEASED',
} as const;

export type Stage = typeof Stage[keyof typeof Stage];

export const RelationType = {
  CONTAINS: 'contains',
  BLOCKS: 'blocks',
  REFERENCES: 'references',
  SPEC_TO_PLAN: 'spec_to_plan',
  PLAN_TO_EPIC: 'plan_to_epic',
  EPIC_TO_TASK: 'epic_to_task',
  TASK_TO_LEDGER: 'task_to_ledger',
  TASK_TO_RELEASE: 'task_to_release',
  DEPENDS_ON: 'depends_on',
} as const;

export type RelationType = typeof RelationType[keyof typeof RelationType];

// Core entity model
export interface DashboardEntity {
  // Core identification
  id: string;
  type: EntityType;
  title: string;
  description?: string | null;

  // Lifecycle tracking
  stage: Stage;
  status?: string | null;
  priority?: number | null; // 0-4
  labels: string[];

  // Timestamps
  created_at?: string | null; // ISO 8601
  updated_at?: string | null; // ISO 8601
  completed_at?: string | null; // ISO 8601

  // Hierarchy references
  parent_id?: string | null;
  spec_id?: string | null;
  plan_id?: string | null;
  epic_id?: string | null;

  // Metrics (from ledger)
  cost_usd?: number | null;
  tokens?: number | null;
  duration_seconds?: number | null;
  verification_status?: string | null;

  // Source tracking
  source_type: string;
  source_path: string;
  source_checksum?: string | null;

  // Rich content
  content?: string | null;
  frontmatter?: Record<string, any> | null;
}

export interface Relationship {
  source_id: string;
  target_id: string;
  rel_type: RelationType;
  metadata?: Record<string, any> | null;
}

// View configuration models
export interface ColumnConfig {
  id: string;
  title: string;
  stages: Stage[];
  group_by?: string | null;
}

export interface FilterConfig {
  exclude_labels: string[];
  include_labels: string[];
  exclude_types: EntityType[];
  include_types: EntityType[];
  min_priority?: number | null;
  max_priority?: number | null;
}

export interface DisplayConfig {
  show_cost: boolean;
  show_tokens: boolean;
  show_duration: boolean;
  card_size: string;
  group_collapsed: boolean;
}

export interface ViewConfig {
  id: string;
  name: string;
  description?: string | null;
  columns: ColumnConfig[];
  filters?: FilterConfig | null;
  display?: DisplayConfig | null;
  is_default: boolean;
}

// API response models
export interface EntityGroup {
  group_key: string | null;
  group_entity?: DashboardEntity | null;
  entities: DashboardEntity[];
  count: number;
}

export interface BoardColumn {
  id: string;
  title: string;
  stage: Stage;
  entities: DashboardEntity[];
  groups?: EntityGroup[] | null;
  count: number;
}

export interface BoardStats {
  total: number;
  by_stage: Record<Stage, number>;
  by_type: Record<EntityType, number>;
  cost_total: number;
  tokens_total: number;
  duration_total_seconds: number;
}

export interface BoardResponse {
  view: ViewConfig;
  columns: BoardColumn[];
  stats: BoardStats;
}

export interface EntityDetail {
  entity: DashboardEntity;
  relationships: Record<string, DashboardEntity[] | DashboardEntity | null>;
  content?: string | null;
}

export interface ViewSummary {
  id: string;
  name: string;
  description?: string | null;
  is_default: boolean;
}

// Error response
export interface ApiError {
  detail: string;
}
