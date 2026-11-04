import { DestinationsView } from "@/components/views/destinations";
import { publicBase } from "@/lib/public-config";
export default function DestinationsPage() {
  return <DestinationsView publicBase={publicBase()} />;
}
