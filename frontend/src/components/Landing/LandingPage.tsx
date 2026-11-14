import React from 'react';
import { Navbar } from './Navbar';
import { HeroSection } from './HeroSection';
import { FeaturesGrid } from './FeaturesGrid';
import { HowItWorks } from './HowItWorks';
import { StatsSection } from './StatsSection';
import { Testimonials } from './Testimonials';
import { FaqAccordion } from './FaqAccordion';
import { CtaBanner } from './CtaBanner';
import { Footer } from './Footer';

interface LandingPageProps {
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
  onNavigateToSignUp: () => void;
  onOpenLoginModal: () => void;
  onNavigateToChat: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  isDarkMode,
  onToggleDarkMode,
  onNavigateToSignUp,
  onOpenLoginModal,
  onNavigateToChat,
}) => {
  const handleSelectFeature = (_featureId: string) => {
    // Có thể chuyển ngay sang Chatbot để người dùng trải nghiệm tính năng
    onNavigateToChat();
  };

  return (
    <div className="min-h-screen flex flex-col bg-white dark:bg-[#0F1B2D] text-slate-800 dark:text-slate-100 transition-colors selection:bg-blue-500 selection:text-white">
      {/* 1. Header Navigation */}
      <Navbar
        isDarkMode={isDarkMode}
        onToggleDarkMode={onToggleDarkMode}
        onNavigateToSignUp={onNavigateToSignUp}
        onOpenLoginModal={onOpenLoginModal}
        onNavigateToChat={onNavigateToChat}
      />

      {/* Main Content Sections */}
      <main className="flex-1">
        {/* 2. Hero Section */}
        <HeroSection
          onStartChat={onNavigateToChat}
          onExploreFeatures={() => {
            const el = document.getElementById('features');
            if (el) el.scrollIntoView({ behavior: 'smooth' });
          }}
        />

        {/* 3. Features 6-Card Grid */}
        <FeaturesGrid onSelectFeature={handleSelectFeature} />

        {/* 4. 3-Step How It Works */}
        <HowItWorks onStartNow={onNavigateToSignUp} />

        {/* 5. Key Metrics / Stats */}
        <StatsSection />

        {/* 6. Student Testimonials */}
        <Testimonials />

        {/* 7. FAQ Accordion */}
        <FaqAccordion />

        {/* 8. Bottom CTA Banner */}
        <CtaBanner
          onSignUp={onNavigateToSignUp}
          onOpenChat={onNavigateToChat}
        />
      </main>

      {/* 9. Footer */}
      <Footer />
    </div>
  );
};

