"use client";

import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import ProjectWorkspace from "@/components/ProjectWorkspace";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <AppShell title="Project workspace" subtitle="Agreements, milestones and payments">
      <ProjectWorkspace projectId={params.id} />
    </AppShell>
  );
}
