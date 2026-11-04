import { redirect } from "next/navigation";
import { authenticated } from "@/lib/auth";
import { Shell } from "@/components/shell";
export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  if (!(await authenticated())) redirect("/login");
  return <Shell>{children}</Shell>;
}
