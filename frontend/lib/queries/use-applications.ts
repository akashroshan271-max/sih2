"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getJson, postForm, postJson } from "@/lib/api";
import { dashboardKeys } from "@/lib/queries/use-dashboard";
import type {
  ApplicationDetail,
  ApplicationStatus,
  ChainVerificationResponse,
  DocumentExtractionResponse,
  DocumentRecord,
  TransitionResponse,
} from "@/types/api";

export const applicationKeys = {
  all: ["application"] as const,
  detail: (id: string) => [...applicationKeys.all, id] as const,
  chain: (id: string) => [...applicationKeys.all, id, "chain"] as const,
};

export function useApplication(id: string) {
  return useQuery({
    queryKey: applicationKeys.detail(id),
    queryFn: () => getJson<ApplicationDetail>(`/applications/${id}`),
    enabled: Boolean(id),
    staleTime: 30_000,
  });
}

export function useTransitionApplication(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (variables: { toStatus: ApplicationStatus; remarks?: string }) =>
      postJson<TransitionResponse>(`/applications/${id}/transition`, {
        to_status: variables.toStatus,
        remarks: variables.remarks?.trim() ? variables.remarks.trim() : null,
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(applicationKeys.detail(id), data.application);
      void queryClient.invalidateQueries({ queryKey: dashboardKeys.all });
    },
    onError: () => {
      // A blocked move still writes a chain entry, so refresh the docket and KPIs.
      void queryClient.invalidateQueries({ queryKey: applicationKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: dashboardKeys.all });
    },
  });
}

export function useUploadDocument(applicationId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("doc_type", "lease_deed");
      form.append("file", file);
      return postForm<DocumentRecord>(`/applications/${applicationId}/documents`, form);
    },
    onSuccess: (document) => {
      queryClient.setQueryData<ApplicationDetail>(
        applicationKeys.detail(applicationId),
        (current) =>
          current
            ? { ...current, documents: [...current.documents, document] }
            : current,
      );
      void queryClient.invalidateQueries({
        queryKey: applicationKeys.detail(applicationId),
      });
      void queryClient.invalidateQueries({ queryKey: dashboardKeys.all });
    },
    onError: () => {
      void queryClient.invalidateQueries({
        queryKey: applicationKeys.detail(applicationId),
      });
    },
  });
}

export function useExtractDocument(applicationId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (documentId: string) =>
      postJson<DocumentExtractionResponse>(`/documents/${documentId}/extract`),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: applicationKeys.detail(applicationId),
      });
      void queryClient.invalidateQueries({ queryKey: dashboardKeys.all });
    },
    onError: () => {
      // The API marks the document failed before replying, so refresh the record.
      void queryClient.invalidateQueries({
        queryKey: applicationKeys.detail(applicationId),
      });
      void queryClient.invalidateQueries({ queryKey: dashboardKeys.all });
    },
  });
}

export function useChainVerification(id: string, enabled: boolean) {
  return useQuery({
    queryKey: applicationKeys.chain(id),
    queryFn: () =>
      getJson<ChainVerificationResponse>(`/audit/applications/${id}/verify`),
    enabled: enabled && Boolean(id),
    staleTime: 0,
    gcTime: 0,
  });
}
