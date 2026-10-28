"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getJson, postJson } from "@/lib/api";
import type {
  FunnelResponse,
  HeatmapResponse,
  KpiSnapshot,
  LeaseWarningList,
  PipelineResponse,
  SlaAlertList,
  SlaScanResult,
} from "@/types/api";

const LIVE_INTERVAL = 60_000;

export const dashboardKeys = {
  all: ["dashboard"] as const,
  kpis: () => [...dashboardKeys.all, "kpis"] as const,
  pipeline: (perStage: number) =>
    [...dashboardKeys.all, "pipeline", perStage] as const,
  heatmap: () => [...dashboardKeys.all, "heatmap"] as const,
  funnel: () => [...dashboardKeys.all, "funnel"] as const,
  slaAlerts: () => [...dashboardKeys.all, "sla-alerts"] as const,
  leaseWarnings: () => [...dashboardKeys.all, "lease-warnings"] as const,
};

export function useKpis() {
  return useQuery({
    queryKey: dashboardKeys.kpis(),
    queryFn: () => getJson<KpiSnapshot>("/dashboard/kpis"),
    refetchInterval: LIVE_INTERVAL,
  });
}

export function usePipeline(perStage = 5) {
  return useQuery({
    queryKey: dashboardKeys.pipeline(perStage),
    queryFn: () =>
      getJson<PipelineResponse>("/dashboard/pipeline", { per_stage: perStage }),
    refetchInterval: LIVE_INTERVAL,
  });
}

export function useHeatmap() {
  return useQuery({
    queryKey: dashboardKeys.heatmap(),
    queryFn: () => getJson<HeatmapResponse>("/dashboard/sla-heatmap"),
    refetchInterval: LIVE_INTERVAL,
  });
}

export function useFunnel() {
  return useQuery({
    queryKey: dashboardKeys.funnel(),
    queryFn: () => getJson<FunnelResponse>("/dashboard/funnel"),
    refetchInterval: LIVE_INTERVAL,
  });
}

export function useSlaAlerts() {
  return useQuery({
    queryKey: dashboardKeys.slaAlerts(),
    queryFn: () => getJson<SlaAlertList>("/dashboard/sla-alerts"),
    refetchInterval: LIVE_INTERVAL,
  });
}

export function useLeaseWarnings() {
  return useQuery({
    queryKey: dashboardKeys.leaseWarnings(),
    queryFn: () => getJson<LeaseWarningList>("/dashboard/lease-warnings"),
    refetchInterval: LIVE_INTERVAL,
  });
}

export function useSlaScan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => postJson<SlaScanResult>("/dashboard/sla/scan"),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dashboardKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["application"] });
    },
  });
}
