import { Suspense } from "react";
import { LinksView } from "@/components/views/links";
import { Loading } from "@/components/shared";
export default function LinksPage() {
  return (
    <Suspense fallback={<Loading />}>
      <LinksView />
    </Suspense>
  );
}
