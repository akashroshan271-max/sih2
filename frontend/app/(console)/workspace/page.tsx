import type { Metadata } from "next";

import { WorkspaceDesk } from "@/components/workspace/workspace-desk";

export const metadata: Metadata = {
  title: "My desk",
};

export default function WorkspacePage() {
  return <WorkspaceDesk />;
}
