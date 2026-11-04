import { Suspense } from "react";
import { LinksView } from "@/components/views/links";
import { Loading } from "@/components/shared";
import { publicBase } from "@/lib/public-config";
export default function LinksPage() {
  return (
    <Suspense fallback={<Loading />}>
      <LinksView publicBase={publicBase()} />
    </Suspense>
  );
}
