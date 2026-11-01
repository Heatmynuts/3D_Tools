export type ParamValue = number | string | boolean | number[] | string[]

export interface Component {
  id: string
  type: string
  label: string
  role: 'reference' | 'fonctionnel' | 'esthetique' | 'assemblage'
  part?: string | null
  params: Record<string, ParamValue>
  position: number[]
  rotation: number[]
  parent?: string | null
  wraps?: string | null
  supports?: string | null
  target?: string | null
  note?: string | null
}

export interface ConceptGraph {
  references: Component[]
  components: Component[]
}

export type Source = 'utilisateur' | 'document' | 'hypothese' | 'deduit'

export interface DesignSpec {
  title: string
  function: string
  context: string
  print_intent: string | null
  requirements: { id: string; text: string; priority: string }[]
  constraints: { id: string; kind: string; text: string; source: Source }[]
  decisions: { id: string; topic: string; choice: string; consequence: string }[]
  parameters: { id: string; label: string; value: number | null; unit: string; status: string; source: Source }[]
  unknowns: { id: string; topic: string; impact: 'fort' | 'moyen' | 'faible'; affects: string[] }[]
  orientations: { id: string; up: Axis; rationale: string }[]
  loads: { id: string; description: string; target: string | null; direction: string; magnitude: number | null; unit: string; source: Source }[]
  positioning: { id: string; object: string; relative_to: string; liaisons: { type: string; surface: string }[]; maintien: string; note: string }[]
}

export type Axis = '+X' | '-X' | '+Y' | '-Y' | '+Z' | '-Z'

export const LIAISON_DOF: Record<string, number> = {
  ponctuelle: 1, lineaire_rectiligne: 2, lineaire_annulaire: 2, appui_plan: 3, rotule: 3,
  pivot_glissant: 4, pivot: 5, glissiere: 5, helicoidale: 5, encastrement: 6,
}

export interface Finding {
  id: string
  level: 'bloquant' | 'attention' | 'info'
  rule: string
  message: string
  component: string | null
}

export interface Option {
  id: string
  label: string
  hint?: string
}

export interface NextStep {
  kind: 'question' | 'checkpoint'
  question?: { text: string; why: string; options: Option[]; allow_other: boolean; targets_unknown?: string | null } | null
  checkpoint?: { text: string; summary: string[] } | null
}

export interface PlanItem {
  text: string
  status?: string | null
}

export interface DesignPlan {
  title: string
  fonction: string
  geometrie_generale: string
  dimensions_connues: PlanItem[]
  dimensions_a_determiner: PlanItem[]
  interfaces: PlanItem[]
  materiau: string
  contraintes: PlanItem[]
  assemblages: PlanItem[]
  tolerances: PlanItem[]
  zones_fonctionnelles: PlanItem[]
  zones_esthetiques: PlanItem[]
  contraintes_impression: PlanItem[]
  hypotheses: PlanItem[]
  orientation_impression: PlanItem[]
  cas_de_charge: PlanItem[]
  mise_en_position: PlanItem[]
  points_de_vigilance: PlanItem[]
  intention_impression: string | null
}

export interface Diff {
  added: string[]
  removed: string[]
  modified: string[]
}

export interface VersionMeta {
  id: string
  parent_id: string | null
  seq: number
  kind: 'concept' | 'plan'
  label: string
  branch: string
  change_summary: string
  validated: number
  created_at: string
  diff: Diff | null
  author: string | null
}

export interface Version extends VersionMeta {
  project_id: string
  spec: DesignSpec
  concept: ConceptGraph
  next: NextStep | null
  plan: DesignPlan | null
  review?: Finding[]
  review_coverage?: ReviewCoverage[]
}

export interface Message {
  id: number
  version_id: string
  role: 'user' | 'assistant' | 'event'
  kind: string
  text: string
  payload: Record<string, unknown> | null
  created_at: string
}

export type Phase = 'vide' | 'entretien' | 'checkpoint' | 'plan_revue' | 'plan_valide'

export interface Candidate {
  id: string
  batch_id: string
  slot: 'A' | 'B'
  label: string
  model: string
  position: number
  ok: number
  error: string | null
  turn: { change_summary: string; next: NextStep } | null
  spec: DesignSpec | null
  concept: ConceptGraph | null
  diff: Diff | null
  input: { kind: string; text: string; option_id: string | null }
  latency_ms: number | null
  input_tokens: number | null
  output_tokens: number | null
}

export interface Track {
  id: string
  slot: 'A' | 'B'
  label: string
  model: string
  fork_version_id: string | null
  head_version_id: string
  head: Version
  parent_concept: ConceptGraph | null
  answers: Message[]
  review: Finding[]
  review_coverage?: ReviewCoverage[]
  turns: number
}

export interface ThreadStat {
  label: string
  threads: number
  chosen: number
}

export interface AbStat {
  label: string
  model: string
  proposed: number
  chosen: number
  failed: number
  avg_latency_ms: number | null
  avg_output_tokens: number | null
}

export interface ProjectState {
  project: { id: string; title: string; initial_prompt: string; head_version_id: string | null; branch: string }
  phase: Phase
  head: Version | null
  lineage: string[]
  versions: VersionMeta[]
  messages: Message[]
  pending: Candidate[]
  ab_stats: { project: AbStat[]; global: AbStat[]; threads_project: ThreadStat[]; threads_global: ThreadStat[] }
  review: Finding[]
  review_coverage?: ReviewCoverage[]
  tracks: Track[]
  cad_runs: CadRun[]
}

export interface UsageStep {
  turn_id: string | null
  label: string
  kept: string | null
  phase: 'Concept' | 'Plan'
  started_at: string
  cost_usd: number
  estimate: boolean
  calls: number
  repairs: number
  failed: number
  by_model: Record<string, { cost_usd: number; input_tokens: number; output_tokens: number; cache_read_tokens: number; unpriced: number }>
}

export interface Usage {
  steps: UsageStep[]
  by_model: Record<string, number>
  by_phase: Record<string, number>
  total_usd: number
}

export interface Credits {
  openrouter: null | {
    key_usage_usd?: number | null
    key_limit_usd?: number | null
    key_limit_remaining_usd?: number | null
    usage_daily_usd?: number | null
    usage_monthly_usd?: number | null
    account_balance_usd?: number
    error?: string
  }
  anthropic: null | { api_balance: null; note: string; estimated_balance_usd?: number; spent_since_usd?: number; reference?: string }
  app: Record<string, { today_usd: number; total_usd: number }>
}

export interface ORModel {
  id: string
  name: string
  context_length: number | null
  prompt_per_m: number
  completion_per_m: number
  vision: boolean
}

export interface ProjectSummary {
  id: string
  title: string
  updated_at: string
  n_versions: number
}

export interface CatalogEntry {
  category: string
  description: string
  params: Record<string, { default: ParamValue; doc: string }>
  zones: string[]
}

export interface Meta {
  provider: string
  model: string
  label: string
  b: { available: boolean; default_model: string }
  profile: { name: string; available: boolean; two_perimeters_mm?: number; values: Record<string, number> }
  catalog: Record<string, CatalogEntry>
}

export interface Selection {
  component_id: string
  zone: string | null
  label: string
  point: number[] | null
}

export interface ReviewCoverage { rule: string; label: string; status: "execute" | "non_applicable" | "donnees_manquantes" | "non_disponible"; detail: string }

export interface CadRun {
  id: string; plan_version_id: string; parent_id: string | null; summary: string; code: string;
  params: Record<string, number>; assumptions: string[]; validated: boolean; demo: boolean;
  metrics: { name: string; index: number; dimensions_mm: number[]; print_dimensions_mm: number[]; volume_mm3: number; solids: number; orientation: string }[];
  slices: { id: string; machine: string; process: string; filament: string; bed_type: string; seconds: number; gcode_files: string[]; statistics: Record<string,string>[]; cli_adjustments?: { key: string; source: string; value: string[]; reason: string }[]; validated: boolean }[];
}
