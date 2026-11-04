"use client";
import { ErrorNotice } from "@/components/shared";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return <ErrorNotice code="GENERIC" retry={reset} />;
}
