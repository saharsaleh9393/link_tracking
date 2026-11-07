export type Locale = "en" | "fa";
export type Campaign = {
  id: string;
  name: string;
  archived: boolean;
  created_at: string;
  link_count?: number | null;
};
export const utmKeys = [
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_content",
  "utm_term",
] as const;
export type Utms = Record<(typeof utmKeys)[number], string | null>;
export type Link = Utms & {
  id: string;
  slug: string;
  linkspace_id: string | null;
  tracking_url: string;
  campaign_id: string | null;
  status: "active" | "disabled" | "deleted";
  expires_at: string | null;
  forward_utm: boolean;
  active_destination_id: string;
  version: number;
  created_at: string;
  updated_at: string;
};
export type Destination = {
  id: string;
  link_id: string;
  url: string;
  version: number;
  created_at: string;
};
export type Counts = {
  total_clicks: number;
  human_clicks: number;
  bot_clicks: number;
  unknown_clicks: number;
  estimated_visitor_days: number;
};
export type Summary = Counts & {
  partial_history: boolean;
  estimated_unique_visitors: number | null;
};
export type Breakdown = {
  items: (Counts & { value: string | null })[];
  next_offset: number | null;
};
export type Trend = {
  items: (Counts & { bucket: string })[];
  next_offset: number | null;
};
export type Overview = {
  total_links: number;
  active_campaigns: number;
  recent_activity: {
    action: string;
    resource_id: string;
    occurred_at: string;
  }[];
};
export type Click = Utms & {
  click_id: string;
  occurred_at: string;
  link_id: string;
  device: string;
  browser: string;
  os: string;
  country: string | null;
  classification: string;
  referrer_origin: string | null;
};
export type ClickPage = {
  items: Click[];
  next_cursor: string | null;
  partial_history: boolean;
};
export type ListPage<T> = { items: T[]; total: number };
