import type { Metadata } from "next";

import { DocketView } from "@/components/docket/docket-view";

export const metadata: Metadata = {
  title: "Docket",
};

export default function ApplicationPage({ params }: { params: { id: string } }) {
  return <DocketView applicationId={params.id} />;
}
