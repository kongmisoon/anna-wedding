// Anna Wedding 메인 페이지: 5개 섹션을 앵커로 연결한 단일 페이지
import { useState } from "react";
import SiteHeader from "@/components/anna/SiteHeader";
import HeroSection from "@/components/anna/HeroSection";
import ServicesSection from "@/components/anna/ServicesSection";
import AiRecommendSection from "@/components/anna/AiRecommendSection";
import RegionsSection from "@/components/anna/RegionsSection";
import ContactSection from "@/components/anna/ContactSection";
import SiteFooter from "@/components/anna/SiteFooter";

const Index = () => {
  const [aiSummary, setAiSummary] = useState<string>("");

  return (
    <div className="min-h-screen bg-background">
      <SiteHeader />
      <main>
        <HeroSection />
        <ServicesSection />
        <AiRecommendSection onResult={setAiSummary} />
        <RegionsSection />
        <ContactSection prefillSummary={aiSummary || undefined} />
      </main>
      <SiteFooter />
    </div>
  );
};

export default Index;
