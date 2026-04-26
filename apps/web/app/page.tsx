import { Footer } from "@/components/Footer";
import { TopBar } from "@/components/TopBar";
import { SummaryStrip } from "@/components/SummaryStrip";
import { JudgementList } from "@/components/JudgementList";
import { MacroPulseCollapsed } from "@/components/MacroPulseCollapsed";
import { TodayPlaybook } from "@/components/TodayPlaybook";
import { DeepRead } from "@/components/DeepRead";
import { DrawerHost } from "@/components/DrawerHost";
import { UploadDrawerHost } from "@/components/UploadDrawerHost";
import { BriefHydrator } from "@/components/BriefHydrator";
import { ModeBanner } from "@/components/ModeBanner";
import { getBriefToday, getSourceHealth } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const [brief, sourceHealth] = await Promise.all([getBriefToday(), getSourceHealth()]);

  return (
    <main className="min-h-screen bg-canvas">
      <BriefHydrator brief={brief} />
      <ModeBanner system={brief.system} />
      <TopBar
        delivery={brief.delivered_at_hkt}
        freezeWindow={brief.freeze_window_hkt}
        anonymized={brief.anonymized}
        auditMode={brief.audit_mode}
        stale={brief.stale}
        degraded={brief.degraded_sources.length > 0}
      />

      <section className="mx-auto max-w-[1440px] border-b border-line bg-canvas">
        <div className="flex flex-col gap-6 px-8 py-8">
          <SummaryStrip
            baseCase={brief.base_case}
            portfolio={brief.portfolio_snapshot}
            stalePortfolio={brief.stale}
          />

          <JudgementList judgements={brief.judgements} />

          <MacroPulseCollapsed
            label={brief.macro_pulse_collapsed.label}
            expandLabel={brief.macro_pulse_collapsed.expand_label}
          />
        </div>
      </section>

      <TodayPlaybook events={brief.playbook_events} />
      <DeepRead deepRead={brief.deep_read} sourceHealth={sourceHealth} />
      <Footer
        left={brief.footer.left}
        right={brief.footer.right}
        degraded={brief.degraded_sources.length > 0}
        stale={brief.stale}
      />

      <DrawerHost />
      <UploadDrawerHost />
    </main>
  );
}
