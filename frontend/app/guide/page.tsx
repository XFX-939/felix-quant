import { GuideLayout } from "@/components/guide/GuideComponents";
import { guideSections } from "@/lib/guideContent";

export default function GuidePage() {
  return <GuideLayout sections={guideSections} />;
}

