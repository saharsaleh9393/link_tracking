import * as React from "react";
import { cn } from "@/lib/utils";
export function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div className="relative w-full overflow-x-auto">
      <table
        className={cn("w-full caption-bottom text-sm", className)}
        {...props}
      />
    </div>
  );
}
export function TableHeader(props: React.ComponentProps<"thead">) {
  return (
    <thead
      className="border-b bg-slate-50/70 text-muted-foreground"
      {...props}
    />
  );
}
export function TableBody(props: React.ComponentProps<"tbody">) {
  return <tbody className="[&_tr:last-child]:border-0" {...props} />;
}
export function TableRow(props: React.ComponentProps<"tr">) {
  return (
    <tr className="border-b transition-colors hover:bg-muted/40" {...props} />
  );
}
export function TableHead(props: React.ComponentProps<"th">) {
  return (
    <th
      className="h-12 px-5 text-start text-xs font-medium whitespace-nowrap"
      {...props}
    />
  );
}
export function TableCell(props: React.ComponentProps<"td">) {
  return <td className="px-5 py-4 align-middle" {...props} />;
}
