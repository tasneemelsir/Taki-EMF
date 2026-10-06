// Shapes of the project configuration and of the API results.
// The configuration is plain JSON; the Python server owns its meaning.

export type GroundModel = 'perfect_conductor' | 'free_space' | 'complex_image';

export interface CustomTower {
  layout: 'horizontal' | 'delta' | 'vertical' | 'double-vertical';
  attach_height_m: number;
  design_sag_m: number;
  phase_spacing_m: number;
  vertical_spacing_m: number;
  circuit_spacing_m: number;
  bundle_n: number;
  bundle_spacing_m: number;
  radius_mm: number;
  current_a: number;
  voltage_kv: number;
  row_width_m: number;
  tower_style: 'lattice' | 'monopole';
}

/** One circuit of a multi-circuit tower, set on its own. 0 for a voltage or current = the line's value. */
export interface CircuitCfg {
  on: boolean;
  voltage_kv: number;
  current_a: number;
  load_pct: number;
  phase_order: 'ABC' | 'CBA';
}

export interface LineCfg {
  name: string;
  preset: string;
  custom: CustomTower;
  x_offset: number;
  load_pct: number;
  arrangement: 'ABC-ABC' | 'ABC-CBA';
  phase_offset_deg: number;
  current_a: number;
  voltage_kv: number;
  height_adjust_m: number;
  /** empty = every circuit uses the line's voltage, current and loading; else one entry per circuit */
  circuits: CircuitCfg[];
  preset_missing?: string;
}

export interface BuildingCfg {
  name: string;
  type: string;
  shape: 'box' | 'lshape' | 'cylinder' | 'multistory';
  roof: 'flat' | 'pitched' | 'stepped';
  width: number;
  depth: number;
  height: number;
  distance: number;
  side: 'left' | 'right';
  z_offset: number;
  material: string;
  b_pct: number | null;
  /** storey height used by the 3-D model only; null = typical for the building type */
  floor_h?: number | null;
  e_pct: number | null;
}

export interface ShieldCfg {
  enabled: boolean;
  preset: string;
  side: 'left' | 'right' | 'both';
  target_building: number;
  material_id: string;
  custom_material: { label: string; sigma: number; mu_r: number };
  model: 'physical' | 'analytical' | 'empirical';
  thickness_mm: number;
  layers: number;
  layer_spacing_m: number;
  coverage_pct: number;
  mesh: boolean;
  aperture_mm: number;
  pitch_mm: number;
  grounded: boolean;
  bonded: boolean;
  distance_m: number;
  height_m: number;
  length_m: number;
  emp_b_pct: number | null;
  emp_e_pct: number | null;
  standoff_m: number;
  /** sheet stand-off from the walls (roof-only: overhang), height above the roof, floor-only level */
  gap_m: number; roof_gap_m: number; floor_level_m: number;
  /** custom layout: plates as [x1, y1, x2, y2] in the cross-section, and its centre along the line */
  custom_plates: number[][];
  /** free-standing barriers, conductors and custom layouts: centre along the line (0 = mid-span) */
  z_center_m: number;
  room_width_m: number; room_height_m: number; room_depth_m: number; room_offset_m: number; room_floor_m: number;
  loop_spacing_m: number; loop_vertical: boolean; loop_compensation_pct: number;
  wire_mm2: number; wire_count: number; screen_width_m: number;
  layer2_material_id: string | null;
}

export interface Pin { x: number; y: number; z: number; label: string }

export interface Config {
  schema: number;
  corridor: {
    row_half_width: number; span_m: number; max_sag_m: number; freq_hz: number; meas_height: number;
    ground_model: GroundModel; earth_rho: number; soil_type: string; bundle_eq: boolean;
    /** design and thermal sag scale with (span / 300 m)²; attachment heights stay put */
    sag_follows_span: boolean;
  };
  lines: LineCfg[];
  buildings: BuildingCfg[];
  shield: ShieldCfg;
  standards: string[];
  points: Pin[];
  twin: { iso_level_uT: number };
  numerics: { x_half_width: number; y_max: number; grid_nx: number; grid_ny: number };
  migrated_from?: string;
}

export type Status = 'PASS' | 'MARGINAL' | 'FAIL' | 'NOT_ASSESSED';

export interface QResult { value: number; limit: number | null; status: Status; pct: number | null; headroom: number | null }
export interface StdResult {
  id: string; name: string; jurisdiction: string; year: number; kind: 'limit' | 'precautionary';
  population: string; needs_verification: boolean; source: string; url: string; notes: string;
  overall: Status; b: QResult; e: QResult; governing: 'B' | 'E' | null;
}

export interface ConductorOut { x: number; y: number; y_att: number; phase: 'A' | 'B' | 'C'; circuit: number; on: boolean; current_a: number; voltage_kv: number; bundle: number[][] }
export interface CircuitOut { id: number; label: string; on: boolean; kv: number; rated_a: number; operating_a: number; load_pct: number; thermal_sag_m: number; phase_order: 'ABC' | 'CBA' }
export interface LineOut {
  name: string; preset: string; description: string; tower: 'lattice' | 'monopole'; xc: number; x_offset: number;
  kv: number; rated_a: number; operating_a: number; load_pct: number; arrangement: string; is_double: boolean;
  phase_offset_deg: number; thermal_sag_m: number; design_sag_m: number; radius_m: number; row_width_m: number;
  loading_context: string; conductors: ConductorOut[];
  separate: boolean; circuits: CircuitOut[]; min_height_m: number; clearance_m: number;
}

export interface Receptor {
  building: string; material: string; material_key: string; building_type: string; shape: string;
  b_unshielded_uT: number; b_shielded_uT: number; b_reduction_pct: number;
  e_unshielded_kVm: number; e_shielded_kVm: number; e_reduction_pct: number;
  probe: [number, number, number]; barrier_on: boolean; b_barrier_uT: number; e_barrier_kVm: number;
  barrier_b_reduction_pct: number; barrier_e_reduction_pct: number; inside_row: boolean;
  b_in_avg_uT: number; b_in_max_uT: number; b_in_avg_shield_uT: number; b_in_max_shield_uT: number; b_in_reduction_pct: number;
  e_in_avg_kVm: number; e_in_max_kVm: number; e_in_avg_shield_kVm: number; e_in_max_shield_kVm: number; e_in_reduction_pct: number;
}

export interface ZoneStat { avg0: number; avgS: number; max0: number; maxS: number; reduction_pct: number }
/** What the shield does where it matters: the average inside the protected space (or one point when there is no building). */
export interface ShieldHeadline { basis: 'inside' | 'point'; where: string; covered: boolean; b0: number; bS: number; e0: number; eS: number; b_red_pct: number; e_red_pct: number }
export interface ShieldProbe { x: number; y: number; z: number; b0: number; bS: number; e0: number; eS: number; b_red_pct: number; e_red_pct: number }

export interface ShieldOut {
  on: boolean; enabled: boolean; model: string; model_label: string; preset: string; label: string; attached: boolean;
  mesh: boolean; walls: number[][]; zc: number; zh: number; grounded: boolean; bonded: boolean;
  material: { id: string; label: string; category: string; sigma: number; mu_r: number; quality: string; mechanisms: string; limitations: string };
  thickness_mm: number; layers: number; coverage_pct: number; fill: number; skin_depth_mm: number | null;
  se_b: number; se_e: number; basis_used: string; note: string; ref_point: number[] | null; ref_xyz: number[] | null;
  analytical: { se_b: number; se_e: number; absorption: number; reflection_e: number; reflection_h: number; multi_refl: number; ceiling: number; limited_by_e: string; limited_by_b: string; basis: string; note: string };
  source_distance_m: number; no_geometry: boolean;
  surrounding: boolean; preset_label: string; target_building: number; is_wire: boolean; is_custom: boolean; gap_m: number; roof_gap_m: number; wires: number[][];
  wire_mm2: number; wire_radius_mm: number; compensation_pct: number; room: number[] | null; layer2: string | null;
  protected: { label: string; box: number[]; z: number; b: ZoneStat; e: ZoneStat } | null; loop_current_a?: number;
  headline: ShieldHeadline | null; probe: ShieldProbe | null; z_center_m: number;
  floating_kv?: number; earth_ma_per_m?: number; relaxation?: number; max_sheet_current_a_per_m?: number; loss_w_per_m?: number; elements?: number;
}

export interface Solution {
  hash: string;
  peak_b: number; peak_e: number; peak_b_x: number; peak_e_x: number; peak_b_shield: number; peak_e_shield: number;
  row_b: number | null; row_e: number | null; overall: Status; results: StdResult[];
  governing: { standard: string; id: string; quantity: 'B' | 'E'; value: number; limit: number; unit: string; pct: number; headroom: number; status: Status } | null;
  binding_b: { standard: string; limit: number; headroom: number; status: Status } | null;
  profile: { x: number[]; b0: number[]; e0: number[]; bS: number[]; eS: number[] };
  domain: { x_min: number; x_max: number; y_max: number };
  /** the lowest conductor at mid-span, and an indicative minimum for the line that is tightest */
  clearance: { min_height_m: number; line: string; tightest_line: string; tightest_height_m: number; required_m: number; ok: boolean } | null;
  corridor: { row_half: number; meas_height: number; freq: number; half_span: number; sag_follows_span: boolean; sag_scale: number; max_sag_m: number; ground_model: GroundModel; ground_label: string; ground_short: string; ground_validated: boolean; ground_note: string; bundle_eq: boolean };
  lines: LineOut[]; receptors: Receptor[]; shield: ShieldOut; warnings: string[];
}

export interface GridOut {
  hash: string; z: number; x0: number; x1: number; y0: number; y1: number; nx: number; ny: number;
  b0: string; bS: string; e0: string; eS: string; max_b: number; max_e: number; shield_here: boolean;
}

export interface PointRow {
  n: number; label: string; x: number; y: number; z: number; b0: number; bS: number; e0: number; eS: number;
  b_red_pct: number; e_red_pct: number; b_se_db: number; e_se_db: number; b_pct_limit: number | null; e_pct_limit: number | null; in_shield_length: boolean;
}

/**
 * One option of a comparison. b0/bS/e0/eS and the changes are the AVERAGE inside the building
 * being protected (basis "inside"), or one point when there is no building (basis "point").
 * b_max*: the highest point inside. b_pt*: the single probe point, 1 m inside the wall facing the line.
 */
export interface SweepRow {
  label: string; sub: string; basis: 'inside' | 'point'; where: string;
  b0: number; bS: number; e0: number; eS: number; b_red_pct: number; e_red_pct: number;
  b_se_db: number; e_se_db: number;
  b_max0: number | null; b_maxS: number | null; e_max0: number | null; e_maxS: number | null;
  b_pt0: number; b_ptS: number; e_pt0: number; e_ptS: number; b_pt_red_pct: number; e_pt_red_pct: number;
  sheet_se_b: number | null; sheet_se_e: number | null; has_geometry: boolean; model?: string; available?: boolean;
  id?: string; short?: string; changes?: Record<string, unknown>; in_use?: boolean;
}

export interface User { id: string; email: string | null; name: string; organisation: string; is_guest: boolean; prefs: Record<string, any>; created_at: number }

export interface ProjectMeta {
  id: string; name: string; description: string; created_at: number; updated_at: number; scenario_count?: number; shared?: boolean;
  summary: { peak_b?: number; peak_e?: number; overall?: Status; lines?: number; kv?: number[]; shield?: boolean; buildings?: number };
}
export interface Scenario { id: string; name: string; note: string; created_at: number; config: Config; summary: ProjectMeta['summary'] }
export interface Project extends ProjectMeta { config: Config; scenarios: Scenario[]; share?: string | null }

export interface Library {
  schema: number; default_config: Config; default_line: LineCfg; default_building: BuildingCfg;
  tower_presets: { name: string; description: string; radius_m: number; row_width_m: number; is_double: boolean; voltage_kv: number; current_a: number; bundle: number; circuits: { id: number; label: string; voltage_kv: number; current_a: number; low_order: 'ABC' | 'CBA' }[]; conductors: { x: number; y: number; phase: string; circuit: number }[] }[];
  custom_layouts: Record<string, string>; default_custom: CustomTower; default_circuit: CircuitCfg; reference_span_m: number;
  voltage_classes: { kv: number; label: string; current_a: number; radius_m: number; bundle: number; region: string }[];
  current_presets: number[]; loading_presets: number[];
  soil_types: { id: string; name: string; resistivity: number; range: string }[];
  ground_models: { id: GroundModel; label: string; short: string; limit: string; validated: boolean; description: string; caution: string }[];
  standards: { id: string; name: string; jurisdiction: string; year: number; kind: string; population: string; b50: number | null; e50: number | null; b60: number | null; e60: number | null; source: string; url: string; notes: string; needs_verification: boolean }[];
  default_standards: string[];
  building_types: { name: string; floor_h: number; glazing: number; plant: number; colour: string; roof: string; width: number; depth: number; height: number; sensitivity: string; occupancy: string; notes: string; rooftop: string[] }[];
  building_shapes: Record<string, string>; roof_types: Record<string, string>;
  building_materials: { key: string; label: string; e_pct: number; e_range: [number, number]; b_pct: number; b_range: [number, number]; mechanism: string; source_ids: string[] }[];
  shield_materials: { id: string; label: string; category: string; sigma: number; resistivity: number | null; mu_r: number; eps_r: number; quality: string; applications: string; mechanisms: string; limitations: string; empirical_key: string | null; ref_ids: string[]; typical_thickness_mm: number; skin_depth_50_mm: number; skin_depth_60_mm: number }[];
  shield_presets: { id: string; label: string; short: string; hint: string; attached: boolean; mesh: boolean; wires: boolean; custom: boolean; refs: string[] }[];
  shield_sides: Record<string, string>; shield_models: Record<string, string>;
  references: Reference[]; reference_topics: string[];
  report: { sections: { id: string; label: string; default: boolean; hint?: string }[]; figures: { id: string; label: string; default: boolean }[]; ai_providers: AiProvider[] };
}

/** An AI service that can draft the report narrative. Each person uses their own key for it. */
export interface AiProvider { id: string; label: string; company: string; key_hint: string; key_url: string; default_model: string; models: string[] }

export interface Reference { id: string; title: string; authors: string; year: string; venue: string; topic: string; verification: string; findings: string; method: string; materials: string; freq_range: string; url: string; doi: string; used_for: string }

export interface Meta {
  version: string; allow_signup: boolean; allow_guests: boolean; operator_ai: string[]; min_password: number;
  database: string; database_host: string; email: boolean; user: User | null;
  desktop: boolean;              // the desktop version: one person on this computer, no sign-in
  desktop_download: boolean;     // this copy hands out the desktop version as a download
  data_dir?: string;             // desktop version only: the folder that holds the projects
}
