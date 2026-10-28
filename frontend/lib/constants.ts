import type {
  ActiveStage,
  ApplicationStatus,
  ApplicationType,
  DocumentType,
  ExtractionStatus,
  InstitutionType,
  OfficerRole,
  ProgrammeLevel,
} from "@/types/api";

export const ACTIVE_STAGES: readonly ActiveStage[] = [
  "scrutiny",
  "evc",
  "sac",
  "shc",
] as const;

interface StageMeta {
  label: string;
  short: string;
  accent: string;
  tint: string;
  note: string;
}

export const STAGE_META: Record<ActiveStage, StageMeta> = {
  scrutiny: {
    label: "Scrutiny",
    short: "Scrutiny",
    accent: "#0E4A45",
    tint: "#DCE7E1",
    note: "Document and lease checks",
  },
  evc: {
    label: "Expert Visit Committee",
    short: "EVC",
    accent: "#A97612",
    tint: "#F4EAD3",
    note: "On-site inspection",
  },
  sac: {
    label: "SAC",
    short: "SAC",
    accent: "#394A78",
    tint: "#E1E5EF",
    note: "Committee review",
  },
  shc: {
    label: "SHC",
    short: "SHC",
    accent: "#6A3F5C",
    tint: "#EDE2E9",
    note: "Higher committee",
  },
};

type BadgeTone = "teal" | "turmeric" | "indigo" | "plum" | "seal" | "neutral";

export const STATUS_META: Record<
  ApplicationStatus,
  { label: string; tone: BadgeTone; accent: string; tint: string }
> = {
  scrutiny: {
    label: "Scrutiny",
    tone: "teal",
    accent: STAGE_META.scrutiny.accent,
    tint: STAGE_META.scrutiny.tint,
  },
  evc: {
    label: "EVC",
    tone: "turmeric",
    accent: STAGE_META.evc.accent,
    tint: STAGE_META.evc.tint,
  },
  sac: {
    label: "SAC",
    tone: "indigo",
    accent: STAGE_META.sac.accent,
    tint: STAGE_META.sac.tint,
  },
  shc: {
    label: "SHC",
    tone: "plum",
    accent: STAGE_META.shc.accent,
    tint: STAGE_META.shc.tint,
  },
  approved: {
    label: "Approved",
    tone: "teal",
    accent: "#0E4A45",
    tint: "#DCE7E1",
  },
  rejected: {
    label: "Rejected",
    tone: "seal",
    accent: "#A33A28",
    tint: "#F2E2DC",
  },
};

export const APPLICATION_TYPE_LABEL: Record<ApplicationType, string> = {
  new: "New",
  expansion: "Expansion",
  renewal: "Renewal",
  closure: "Closure",
};

export const PROGRAMME_LEVEL_LABEL: Record<ProgrammeLevel, string> = {
  diploma: "Diploma",
  ug: "UG",
  pg: "PG",
  integrated: "Integrated",
};

export const INSTITUTION_TYPE_LABEL: Record<InstitutionType, string> = {
  engineering: "Engineering",
  polytechnic: "Polytechnic",
  pharmacy: "Pharmacy",
  architecture: "Architecture",
  management: "Management",
  hotel_management: "Hotel management",
  applied_arts: "Applied arts",
};

export const DOCUMENT_TYPE_LABEL: Record<DocumentType, string> = {
  lease_deed: "Lease deed",
  fire_noc: "Fire NOC",
  land_record: "Land record",
  building_plan: "Building plan",
  affiliation_certificate: "Affiliation certificate",
  faculty_list: "Faculty list",
  financial_statement: "Financial statement",
  other: "Other",
};

export const EXTRACTION_META: Record<
  ExtractionStatus,
  { label: string; tone: BadgeTone }
> = {
  pending: { label: "Awaiting extraction", tone: "neutral" },
  processing: { label: "Extracting", tone: "turmeric" },
  extracted: { label: "Extracted", tone: "teal" },
  needs_review: { label: "Needs review", tone: "turmeric" },
  failed: { label: "Extraction failed", tone: "seal" },
};

export const LEASE_CODE_LABEL: Record<string, string> = {
  lease_valid: "Live lease verified",
  lease_deed_missing: "No lease deed on file",
  lease_not_extracted: "Lease dates not readable",
  lease_not_commenced: "Lease not yet in force",
  lease_expired: "Lease expired",
  lease_too_short: "Lease shorter than course",
};

export const SLA_LEVEL_META: Record<
  "L1" | "L2" | "L3",
  { label: string; tone: BadgeTone; owner: string }
> = {
  L1: { label: "L1", tone: "turmeric", owner: "Dealing officer" },
  L2: { label: "L2", tone: "seal", owner: "Regional officer" },
  L3: { label: "L3", tone: "seal", owner: "Chairman" },
};

export const ACTION_LABEL: Record<string, string> = {
  "application.created": "Application registered",
  "stage.transition": "Stage advanced",
  "lease_rule.blocked": "Live-lease rule blocked the move",
  "document.uploaded": "Document uploaded",
  "document.extracted": "Lease deed extracted",
  "document.needs_review": "Lease deed needs review",
  "sla.escalation.L1": "SLA escalation L1",
  "sla.escalation.L2": "SLA escalation L2",
  "sla.escalation.L3": "SLA escalation L3",
};

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface RoleMeta {
  label: string;
  short: string;
  desk: string;
  stage: ActiveStage | null;
  stageLabel: string;
  phase: string;
  tone: BadgeTone;
}

/** The five desks, in statutory order. */
export const ROLE_META: Record<OfficerRole, RoleMeta> = {
  scrutiny_officer: {
    label: "Scrutiny officer",
    short: "Scrutiny",
    desk: "Scrutiny cell",
    stage: "scrutiny",
    stageLabel: "Scrutiny",
    phase: "Phase 1 · evidence & Rule 1",
    tone: "teal",
  },
  evc_member: {
    label: "EVC member",
    short: "EVC",
    desk: "Expert Visit Committee",
    stage: "evc",
    stageLabel: "Expert Visit Committee",
    phase: "Phase 2 · expert visit",
    tone: "turmeric",
  },
  sac_member: {
    label: "SAC member",
    short: "SAC",
    desk: "Standing Approval Committee",
    stage: "sac",
    stageLabel: "SAC",
    phase: "Phase 3 · committee decision",
    tone: "indigo",
  },
  shc_member: {
    label: "SHC member",
    short: "SHC",
    desk: "Standing Hearing Committee",
    stage: "shc",
    stageLabel: "SHC",
    phase: "Phase 4 · hearing",
    tone: "plum",
  },
  regional_officer: {
    label: "Regional officer",
    short: "Oversight",
    desk: "Regional office",
    stage: null,
    stageLabel: "All stages",
    phase: "Oversight · read-only across stages",
    tone: "neutral",
  },
};

export function homeForRole(role: OfficerRole): "/dashboard" | "/workspace" {
  return role === "regional_officer" ? "/dashboard" : "/workspace";
}
