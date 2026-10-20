import SiteFooter from '@/shared/ui/SiteFooter'
import SiteHeader from '@/shared/ui/SiteHeader'
import { footerLinks, headerLinks } from './content'
import Cta from './sections/Cta'
import Hero from './sections/Hero'
import HowItWorks from './sections/HowItWorks'
import Roles from './sections/Roles'
import Safety from './sections/Safety'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-oil font-sans text-parchment">
      <SiteHeader links={headerLinks} />
      <main>
        <Hero />
        <HowItWorks />
        <Roles />
        <Safety />
        <Cta />
      </main>
      <SiteFooter links={footerLinks} />
    </div>
  )
}
