// Спільні класи форм редактора уроків: великі поля й кнопки (зручно на планшеті).

export const field =
  'h-11 rounded-[10px] border border-line bg-surface px-3 text-[15px] text-parchment placeholder:text-dim focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-60'

export const textarea =
  'min-h-24 rounded-[10px] border border-line bg-surface px-3 py-2 text-[15px] leading-[22.5px] text-parchment placeholder:text-dim focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-60'

export const primaryButton =
  'inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-[10px] bg-accent px-5 text-[15px] font-semibold whitespace-nowrap text-oil focus-visible:ring-2 focus-visible:ring-parchment focus-visible:outline-none disabled:opacity-50'

export const secondaryButton =
  'inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-[10px] border border-line-strong px-5 text-[15px] font-semibold whitespace-nowrap text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-50'

export const dangerButton =
  'inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-[10px] px-4 text-sm font-semibold whitespace-nowrap text-muted hover:bg-surface-2 hover:text-accent focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-50'

export const card = 'flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6'
