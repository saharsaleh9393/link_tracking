"use client";
import {
  useEffect,
  useId,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { useTranslations } from "next-intl";
import { Search, X, Loader2 } from "lucide-react";
import { useResource } from "@/lib/client";
import type { Campaign, ListPage } from "@/lib/types";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
export function CampaignSearch({
  onSearch,
}: {
  onSearch: (value: string) => void;
}) {
  const t = useTranslations(),
    id = useId();
  const [draft, setDraft] = useState(""),
    [debounced, setDebounced] = useState(""),
    [open, setOpen] = useState(false),
    [active, setActive] = useState(-1);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(draft), 180);
    return () => clearTimeout(timer);
  }, [draft]);
  const suggestions = useResource<ListPage<Campaign>>("campaigns", {
    q: debounced,
    limit: 8,
    include_total: true,
    descending: true,
  });
  const rows = suggestions.data?.items || [];
  function apply(event?: FormEvent) {
    event?.preventDefault();
    onSearch(draft.trim());
    setOpen(false);
  }
  function keyboard(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      setActive((index) =>
        rows.length
          ? index < 0
            ? event.key === "ArrowDown"
              ? 0
              : rows.length - 1
            : (index + (event.key === "ArrowDown" ? 1 : -1) + rows.length) %
              rows.length
          : -1,
      );
    } else if (event.key === "Escape") {
      setOpen(false);
    } else if (event.key === "Enter" && open && active >= 0 && rows[active]) {
      event.preventDefault();
      setDraft(rows[active].name);
      onSearch(rows[active].name);
      setOpen(false);
    }
  }
  return (
    <form role="search" onSubmit={apply} className="flex min-w-48 flex-1 gap-2">
      <div className="relative min-w-0 flex-1">
        <Search className="absolute top-3 start-3 size-4 text-slate-400" />
        <Input
          aria-label={t("campaignSearch")}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={id}
          aria-activedescendant={
            active >= 0 && open ? `${id}-${active}` : undefined
          }
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            setActive(-1);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={keyboard}
          maxLength={200}
          className="ps-9"
          placeholder={t("campaignSearch") + "…"}
        />
        {open && (
          <div className="absolute top-full z-20 mt-1 w-full rounded-lg border bg-white p-1 shadow-lg">
            <ul role="listbox" id={id} aria-label={t("suggestions")}>
              {suggestions.loading ? (
                <li className="flex items-center gap-2 p-3 text-xs text-muted-foreground">
                  <Loader2 className="size-3 animate-spin" />
                  {t("loading")}
                </li>
              ) : rows.length ? (
                rows.map((row, index) => (
                  <li
                    key={row.id}
                    id={`${id}-${index}`}
                    role="option"
                    aria-selected={active === index}
                  >
                    <button
                      type="button"
                      className={
                        "w-full rounded px-3 py-2 text-start text-sm hover:bg-muted " +
                        (active === index ? "bg-muted" : "")
                      }
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => {
                        setDraft(row.name);
                        setOpen(false);
                        setActive(-1);
                      }}
                    >
                      {row.name}
                    </button>
                  </li>
                ))
              ) : (
                <li className="p-3 text-xs text-muted-foreground">
                  {t("noSuggestions")}
                </li>
              )}
            </ul>
            {(suggestions.data?.total || 0) > 8 && (
              <p className="border-t p-2 text-xs text-muted-foreground">
                {t("moreSuggestions")}
              </p>
            )}
          </div>
        )}
      </div>
      <Button variant="outline" type="submit">
        <Search />
        {t("search")}
      </Button>
      <Button
        variant="ghost"
        type="button"
        aria-label={t("clear")}
        onClick={() => {
          setDraft("");
          onSearch("");
          setOpen(false);
          setActive(-1);
        }}
      >
        <X />
        <span className="hidden sm:inline">{t("clear")}</span>
      </Button>
    </form>
  );
}
