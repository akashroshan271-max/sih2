export type ApplicationStatus =
  | "scrutiny"
  | "evc"
  | "sac"
  | "shc"
  | "approved"
  | "rejected";

export type ActiveStage = Extract<ApplicationStatus, "scrutiny" | "evc" | "sac" | "shc">;

export type ApplicationType = "new" | "expansion" | "renewal" | "closure";

export type ProgrammeLevel = "diploma" | "ug" | "pg" | "integrated";

export type InstitutionType =
  | "engineering"
  | "polytechnic"
  | "pharmacy"
  | "architecture"
  | "management"
  | "hotel_management"
  | "applied_arts";

export type DocumentType =
  | "lease_deed"
  | "fire_noc"
  | "land_record"
  | "building_plan"
  | "affiliation_certificate"
  | "faculty_list"
  | "financial_statement"
  | "other";

export type ExtractionStatus =
  | "pending"
  | "processing"
  | "extracted"
  | "needs_review"
  | "failed";

export interface InstitutionBrief {
  id: string;
  name: string;
  state: string;
  institution_type: InstitutionType;
}

export interface ApplicationSummary {
  id: string;
  application_number: string;
  academic_year: string;
  application_type: ApplicationType;
  programme_level: ProgrammeLevel;
  max_course_duration_years: number;
  status: ApplicationStatus;
  stage_entry_timestamp: string;
  submitted_at: string | null;
  decided_at: string | null;
  proposed_intake: number | null;
  dwell_days: number;
  sla_due_at: string;
  is_sla_breached: boolean;
  institution: InstitutionBrief;
}

export interface DocumentRecord {
  id: string;
  application_id: string;
  doc_type: DocumentType;
  version: number;
  file_name: string;
  s3_url: string;
  mime_type: string | null;
  size_bytes: number | null;
  content_sha256: string | null;
  uploaded_at: string;
  uploaded_by: string | null;
  extraction_status: ExtractionStatus;
  extracted_json_data: Record<string, unknown> | null;
  lease_start_date: string | null;
  lease_end_date: string | null;
  total_land_area_sqm: number | null;
  survey_numbers: string[] | null;
  extraction_confidence: number | null;
  extraction_model: string | null;
  extracted_at: string | null;
  extraction_error: string | null;
}

export interface AuditEntry {
  id: string;
  application_id: string;
  action: string;
  actor: string;
  actor_role: string | null;
  from_status: ApplicationStatus | null;
  to_status: ApplicationStatus | null;
  payload: Record<string, unknown> | null;
  timestamp: string;
  sha256_hash: string;
  previous_hash: string | null;
}

export interface LeaseVerdict {
  code: string;
  compliant: boolean;
  reason: string;
  required_years: number;
  remaining_lease_years: number | null;
  lease_document_id: string | null;
  lease_start_date: string | null;
  lease_end_date: string | null;
  as_of: string;
}

export interface ApplicationDetail extends ApplicationSummary {
  decision_remarks: string | null;
  documents: DocumentRecord[];
  audit_trail: AuditEntry[];
  lease_verdict: LeaseVerdict | null;
  allowed_transitions: ApplicationStatus[];
}

export interface StageDwell {
  status: ActiveStage;
  count: number;
  avg_dwell_days: number;
  max_dwell_days: number;
  breached: number;
}

export interface KpiSnapshot {
  total_active: number;
  dwell_alerts: number;
  lease_expiry_warnings: number;
  lease_data_gaps: number;
  lease_rule_blocks: number;
  approved: number;
  rejected: number;
  approval_rate: number | null;
  avg_dwell_days: number | null;
  generated_at: string;
  stages: StageDwell[];
}

export interface PipelineColumn {
  status: ActiveStage;
  count: number;
  applications: ApplicationSummary[];
}

export interface PipelineResponse {
  columns: PipelineColumn[];
  generated_at: string;
}

export interface HeatmapCell {
  state: string;
  status: ActiveStage;
  count: number;
  avg_dwell_days: number;
  breached: number;
}

export interface HeatmapResponse {
  cells: HeatmapCell[];
  states: string[];
  stages: ActiveStage[];
  threshold_days: number;
}

export interface FunnelStep {
  status: ApplicationStatus;
  count: number;
  share: number;
}

export interface FunnelResponse {
  steps: FunnelStep[];
  total: number;
}

export interface SlaAlert {
  application_id: string;
  application_number: string;
  institution_name: string;
  state: string;
  status: ActiveStage;
  stage_entry_timestamp: string;
  dwell_days: number;
  sla_due_at: string;
  level: "L1" | "L2" | "L3";
  escalate_to: string;
  severity: "warning" | "high" | "critical";
}

export interface SlaAlertList {
  items: SlaAlert[];
  total: number;
  levels: Record<string, number>;
  generated_at: string;
}

export interface SlaScanResult {
  scanned_at: string;
  checked: number;
  overdue: number;
  escalated: number;
  levels: Record<string, number>;
}

export interface LeaseWarning {
  application_id: string;
  application_number: string;
  institution_name: string;
  state: string;
  status: ActiveStage;
  code: string;
  lease_end_date: string | null;
  remaining_lease_years: number | null;
  required_years: number;
  document_id: string | null;
}

export interface LeaseWarningList {
  items: LeaseWarning[];
  total: number;
  generated_at: string;
}

export interface ChainVerification {
  valid: boolean;
  checked: number;
  broken_at: number | null;
  entry_id: string | null;
  expected_hash: string | null;
  stored_hash: string | null;
  reason: string | null;
}

export interface ChainVerificationResponse {
  application_id: string;
  application_number: string;
  verification: ChainVerification;
}

export interface TransitionResponse {
  application: ApplicationDetail;
  audit_log: AuditEntry;
  from_status: ApplicationStatus;
  to_status: ApplicationStatus;
  lease_verdict: LeaseVerdict | null;
}

export interface DocumentExtractionResponse {
  document: DocumentRecord;
  lease_verdict: LeaseVerdict | null;
}

/* -------------------------------------------------------------------------- */
/* Officer identity & role-scoped workspace                                    */
/* -------------------------------------------------------------------------- */

export type OfficerRole =
  | "scrutiny_officer"
  | "evc_member"
  | "sac_member"
  | "shc_member"
  | "regional_officer";

export interface Officer {
  id: string;
  email: string;
  full_name: string;
  designation: string;
  role: OfficerRole;
  region_state: string | null;
  last_login_at: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  officer: Officer;
}

export interface DemoAccount extends Officer {
  password: string | null;
}

export interface DemoAccountList {
  accounts: DemoAccount[];
  shared_password: string | null;
  notice: string | null;
}

export type KpiTone = "neutral" | "teal" | "turmeric" | "seal";

export interface WorkspaceKpi {
  key: string;
  label: string;
  value: number;
  unit: string | null;
  tone: KpiTone;
  hint: string | null;
}

export interface WorkspaceDesk {
  role: OfficerRole;
  label: string;
  stage: ApplicationStatus | null;
  stage_label: string;
  mandate: string;
  checklist: string[];
  next_step: string;
  authority: string;
}

export interface WorkspaceLease {
  document_id: string | null;
  version: number | null;
  extraction_status: ExtractionStatus | null;
  lease_start_date: string | null;
  lease_end_date: string | null;
  remaining_years: number | null;
  required_years: number;
  total_land_area_sqm: number | null;
  survey_numbers: string[];
  verdict_code: string;
  verdict_reason: string;
  compliant: boolean;
}

export interface WorkspaceDocument {
  id: string;
  doc_type: DocumentType;
  version: number;
  file_name: string;
  extraction_status: ExtractionStatus;
  uploaded_at: string;
  lease_start_date: string | null;
  lease_end_date: string | null;
  size_bytes: number | null;
}

export interface WorkspaceFact {
  label: string;
  value: string;
  note: string | null;
}

export interface WorkspaceAction {
  to_status: ApplicationStatus;
  label: string;
  enabled: boolean;
  blocked_reason: string | null;
  requires_note: boolean;
  is_decision: boolean;
}

export interface WorkspaceActivity {
  action: string;
  actor: string;
  actor_role: string | null;
  timestamp: string;
  from_status: ApplicationStatus | null;
  to_status: ApplicationStatus | null;
}

export interface WorkspaceDocket {
  id: string;
  application_number: string;
  institution_name: string;
  state: string;
  district: string | null;
  institution_type: InstitutionType;
  approved_intake: number;
  academic_year: string;
  application_type: ApplicationType;
  programme_level: ProgrammeLevel;
  proposed_intake: number | null;
  max_course_duration_years: number;
  status: ApplicationStatus;
  stage_entry_timestamp: string;
  dwell_days: number;
  sla_due_at: string;
  is_sla_breached: boolean;
  submitted_at: string | null;
  decided_at: string | null;
  lease: WorkspaceLease | null;
  documents: WorkspaceDocument[];
  facts: WorkspaceFact[];
  actions: WorkspaceAction[];
  last_activity: WorkspaceActivity | null;
}

export interface WorkspaceResponse {
  generated_at: string;
  officer: Officer;
  desk: WorkspaceDesk;
  notice: string | null;
  kpis: WorkspaceKpi[];
  queue: WorkspaceDocket[];
  queue_total: number;
  stage_counts: Record<string, number>;
  escalations: SlaAlert[];
}
