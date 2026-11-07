export type Linkspace = {
  id: string;
  name: string;
  base_url: string;
  path_prefix: string;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  link_count: number;
  preview_url: string;
  configuration_status:
    | "local_development"
    | "operator_configured"
    | "pending_configuration"
    | "routing_blocked";
};
export function linkPreview(base: string, prefix: string, slug = "slug") {
  return [
    base.trim().replace(/\/+$/, ""),
    prefix
      .trim()
      .replace(/^\/+|\/+$/g, "")
      .toLowerCase(),
    slug || "slug",
  ]
    .filter(Boolean)
    .join("/");
}
