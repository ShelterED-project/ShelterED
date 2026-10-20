import { Link } from 'react-router'
import logo from '@/assets/landing/logo.svg'

export default function Brand({ size }: { size: 'header' | 'footer' }) {
  return (
    <Link to="/" aria-label="ShelterED — на головну" className="flex shrink-0 items-center gap-2 rounded whitespace-nowrap">
      <img src={logo} alt="" width={24} height={24} />
      <span className={`font-heading text-parchment ${size === 'header' ? 'text-lg md:text-2xl' : 'text-lg'}`}>
        ShelterED
      </span>
    </Link>
  )
}
