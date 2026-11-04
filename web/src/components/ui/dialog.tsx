"use client";
import * as React from "react";
import * as Primitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { LanguageSwitch } from "../language-switch";
export const Dialog = Primitive.Root;
export const DialogTitle = Primitive.Title;
export const DialogDescription = Primitive.Description;
export function DialogContent({
  children,
  className,
  ...props
}: React.ComponentProps<typeof Primitive.Content>) {
  const t = useTranslations();
  return (
    <Primitive.Portal>
      <Primitive.Overlay className="fixed inset-0 z-50 bg-slate-950/40 backdrop-blur-[3px]" />
      <Primitive.Content
        aria-describedby={undefined}
        className={cn(
          "fixed top-1/2 left-1/2 z-50 max-h-[90dvh] w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl border bg-card p-6 shadow-2xl",
          className,
        )}
        {...props}
      >
        <div className="mb-4 flex justify-end pe-7">
          <LanguageSwitch />
        </div>
        {children}
        <Primitive.Close
          aria-label={t("close")}
          className="absolute top-4 end-4 rounded p-1 text-muted-foreground hover:bg-muted"
        >
          <X className="size-4" />
        </Primitive.Close>
      </Primitive.Content>
    </Primitive.Portal>
  );
}
