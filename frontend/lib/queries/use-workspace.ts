"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getJson, postJson } from "@/lib/api";
import { applicationKeys } from "@/lib/queries/use-applications";
import { dashboardKeys } from "@/lib/queries/use-dashboard";
import type {
  ApplicationStatus,
  TransitionResponse,
  WorkspaceResponse,
} from "@/types/api";

export const workspaceKeys = {
  all: ["workspace"] as const,
};

export function useWorkspace() {
  return useQuery({
    queryKey: workspaceKeys.all,
    queryFn: () => getJson<WorkspaceResponse>("/workspace"),
    refetchInterval: 60_000,
  });
}

export function useAdvanceDocket(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (variables: { toStatus: ApplicationStatus; remarks?: string }) =>
      postJson<TransitionResponse>(`/applications/${id}/transition`, {
        to_status: variables.toStatus,
        remarks: variables.remarks?.trim() ? variables.remarks.trim() : null,
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(applicationKeys.detail(id), data.application);
      void queryClient.invalidateQueries({ queryKey: workspaceKeys.all });
      void queryClient.invalidateQueries({ queryKey: dashboardKeys.all });
    },
    onError: () => {
      // Rule 1 blocks are audited too, so the desk and docket both change.
      void queryClient.invalidateQueries({ queryKey: workspaceKeys.all });
      void queryClient.invalidateQueries({
        queryKey: applicationKeys.detail(id),
      });
    },
  });
}
