import type { ReactNode } from 'react'
import { Link } from 'react-router'

type Variant = 'primary' | 'outline'

const base = 'inline-flex items-center justify-center rounded-[10px] font-sans whitespace-nowrap'
const variants: Record<Variant, string> = {
  primary: 'bg-accent font-bold text-oil',
  outline: 'border border-line-strong font-semibold text-parchment',
}

type Props = {
  variant: Variant
  children: ReactNode
  className?: string
} & ({ to: string; href?: never } | { href: string; to?: never })

export default function Button({ variant, children, className = '', to, href }: Props) {
  const classes = `${base} ${variants[variant]} ${className}`
  if (to !== undefined) {
    return (
      <Link to={to} className={classes}>
        {children}
      </Link>
    )
  }
  return (
    <a href={href} className={classes}>
      {children}
    </a>
  )
}
