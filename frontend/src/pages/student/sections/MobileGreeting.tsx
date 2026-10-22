import { greeting } from '../content'

export default function MobileGreeting() {
  return (
    <div className="md:hidden">
      <p className="text-sm text-dim">{greeting.date}</p>
      <h1 className="font-heading text-[28px] leading-[35px] text-parchment">{greeting.title}</h1>
    </div>
  )
}
