import Brand from '@/shared/ui/Brand'
import BellButton from './BellButton'

export default function MobileHeader() {
  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-line-soft bg-oil/95 px-5 backdrop-blur-sm md:hidden">
      <Brand size="app" />
      <BellButton />
    </header>
  )
}
