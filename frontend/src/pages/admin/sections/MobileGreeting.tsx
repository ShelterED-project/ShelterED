import { school } from '../content'

export default function MobileGreeting() {
  return (
    <div className="md:hidden">
      <p className="text-sm text-dim">{school.subtitle}</p>
      <h1 className="font-heading text-[26px] leading-[32.5px] tracking-[-0.26px] text-parchment">{school.name}</h1>
    </div>
  )
}
