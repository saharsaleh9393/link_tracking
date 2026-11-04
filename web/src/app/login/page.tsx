import { redirect } from "next/navigation";
import { authenticated } from "@/lib/auth";
import { Login } from "@/components/login";
export default async function LoginPage() {
  if (await authenticated()) redirect("/overview");
  return <Login />;
}
