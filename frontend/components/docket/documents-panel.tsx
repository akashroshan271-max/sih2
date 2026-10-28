"use client";

import { Loader2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyNote } from "@/components/ui/data-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { ApiError } from "@/lib/api";
import { DOCUMENT_TYPE_LABEL, EXTRACTION_META } from "@/lib/constants";
import {
  useExtractDocument,
  useUploadDocument,
} from "@/lib/queries/use-applications";
import type { ApplicationDetail, DocumentRecord } from "@/types/api";
import { formatArea, formatDate } from "@/lib/utils";

const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "image/jpeg",
  "image/png",
  "image/webp",
] as const;
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

function canExtract(document: DocumentRecord): boolean {
  return (
    document.doc_type === "lease_deed" &&
    document.extraction_status !== "processing" &&
    document.extraction_status !== "extracted"
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function DocumentsPanel({ application }: { application: ApplicationDetail }) {
  const extract = useExtractDocument(application.id);
  const upload = useUploadDocument(application.id);
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);

  const documents = [...application.documents].sort(
    (left, right) =>
      new Date(right.uploaded_at).getTime() - new Date(left.uploaded_at).getTime(),
  );
  const nextLeaseVersion =
    documents.reduce(
      (highest, document) =>
        document.doc_type === "lease_deed"
          ? Math.max(highest, document.version)
          : highest,
      0,
    ) + 1;
  const decided =
    application.status === "approved" || application.status === "rejected";

  function chooseFile(event: React.ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    if (selected === null) {
      setFile(null);
      return;
    }
    if (!ACCEPTED_MIME_TYPES.includes(selected.type as (typeof ACCEPTED_MIME_TYPES)[number])) {
      toast.error("Unsupported file type", {
        description: "Attach the lease deed as a PDF, JPEG, PNG or WebP file.",
      });
      event.target.value = "";
      setFile(null);
      return;
    }
    if (selected.size > MAX_UPLOAD_BYTES) {
      toast.error("File is too large", {
        description: `${formatFileSize(selected.size)} selected; the limit is 25 MB.`,
      });
      event.target.value = "";
      setFile(null);
      return;
    }
    setFile(selected);
  }

  function submitUpload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (file === null || upload.isPending) return;

    upload.mutate(file, {
      onSuccess: (document) => {
        setFile(null);
        if (fileInput.current) fileInput.current.value = "";
        toast.success("Lease deed attached", {
          description: `${document.file_name} · v${document.version}. Run extraction to read the lease dates.`,
        });
      },
      onError: (error) => {
        toast.error("Upload failed", {
          description:
            error instanceof ApiError
              ? error.message
              : "The document could not be uploaded.",
        });
      },
    });
  }

  function runExtraction(document: DocumentRecord) {
    extract.mutate(document.id, {
      onSuccess: (result) => {
        const status = result.document.extraction_status;
        if (status === "extracted") {
          toast.success("Lease dates extracted", {
            description: `${result.document.file_name} · ${result.document.extraction_model ?? "Gemini"}`,
          });
        } else if (status === "needs_review") {
          toast("Lease deed needs review", {
            description:
              result.document.extraction_error ??
              "Some fields could not be read. The lease rule stays blocked until a full deed is on file.",
          });
        } else {
          toast.error("Extraction did not complete", {
            description:
              result.document.extraction_error ?? "The document could not be read.",
          });
        }
      },
      onError: (error) => {
        toast.error("Extraction failed", {
          description:
            error instanceof ApiError
              ? error.message
              : "The extraction service could not be reached.",
        });
      },
    });
  }

  return (
    <section aria-labelledby="documents-heading">
      <SectionHeading
        id="documents-heading"
        title="Documents"
        meta={`${documents.length} on file`}
      />

      {decided ? null : (
        <form
          onSubmit={submitUpload}
          className="mt-3 border border-dashed border-rule bg-paper/40 px-3 py-3"
        >
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <label
              htmlFor="lease-deed-file"
              className="inline-flex h-8 cursor-pointer items-center gap-2 border border-rule bg-panel px-3 text-xs font-medium text-ink transition-colors hover:border-ink/30 hover:bg-ink/[0.03] focus-within:ring-2 focus-within:ring-teal focus-within:ring-offset-2 focus-within:ring-offset-paper"
            >
              <Upload aria-hidden className="h-3.5 w-3.5" />
              {file ? "Replace file" : "Choose file"}
            </label>
            <input
              ref={fileInput}
              id="lease-deed-file"
              type="file"
              accept={ACCEPTED_MIME_TYPES.join(",")}
              className="sr-only"
              disabled={upload.isPending}
              onChange={chooseFile}
            />
            <p className="min-w-0 flex-1 truncate text-2xs text-ink-soft">
              {file ? `${file.name} · ${formatFileSize(file.size)}` : "No file selected"}
            </p>
            <Button type="submit" size="sm" disabled={file === null || upload.isPending}>
              {upload.isPending ? (
                <Loader2 aria-hidden className="h-3.5 w-3.5 animate-spin" />
              ) : null}
              {upload.isPending ? "Uploading" : `Attach as v${nextLeaseVersion}`}
            </Button>
          </div>
          <p className="mt-2 text-2xs text-ink-faint">
            Lease deed · PDF, JPEG, PNG or WebP · up to 25 MB. The upload is
            checksummed into the audit trail; extraction only reads dates and land
            details for the officer to verify.
          </p>
        </form>
      )}

      {documents.length === 0 ? (
        <EmptyNote
          className="mt-3"
          title="No documents uploaded"
          hint="A lease deed is required before the live-lease rule can pass."
        />
      ) : (
        <ul className="mt-3 divide-y divide-rule border border-rule bg-panel">
          {documents.map((document) => {
            const extraction = EXTRACTION_META[document.extraction_status];
            const pending = extract.isPending && extract.variables === document.id;

            return (
              <li key={document.id} className="px-3 py-2.5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[13px] text-ink">
                      {DOCUMENT_TYPE_LABEL[document.doc_type]}{" "}
                      <span className="text-ink-faint">v{document.version}</span>
                    </p>
                    <p className="mt-0.5 truncate text-2xs text-ink-faint">
                      {document.file_name}
                      <span aria-hidden> · </span>
                      {formatDate(document.uploaded_at)}
                      {document.size_bytes !== null
                        ? ` · ${Math.max(1, Math.round(document.size_bytes / 1024))} KB`
                        : ""}
                    </p>

                    {document.lease_start_date && document.lease_end_date ? (
                      <p className="mt-1 text-2xs text-ink-soft">
                        Lease {formatDate(document.lease_start_date)} –{" "}
                        {formatDate(document.lease_end_date)}
                        {document.total_land_area_sqm !== null
                          ? ` · ${formatArea(document.total_land_area_sqm)}`
                          : ""}
                      </p>
                    ) : null}

                    {document.extraction_error ? (
                      <p className="mt-1 max-w-prose text-2xs text-seal">
                        {document.extraction_error}
                      </p>
                    ) : null}
                  </div>

                  <div className="flex shrink-0 flex-col items-end gap-1.5">
                    <Badge tone={extraction.tone}>{extraction.label}</Badge>
                    {canExtract(document) ? (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={extract.isPending}
                        onClick={() => runExtraction(document)}
                      >
                        {pending ? (
                          <Loader2 aria-hidden className="h-3.5 w-3.5 animate-spin" />
                        ) : null}
                        {pending
                          ? "Reading"
                          : document.extraction_status === "needs_review" ||
                              document.extraction_status === "failed"
                            ? "Retry extraction"
                            : "Extract dates"}
                      </Button>
                    ) : null}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
