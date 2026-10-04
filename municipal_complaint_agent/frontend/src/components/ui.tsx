import clsx from 'clsx'
import { MapPin } from 'lucide-react'
import type { ReactNode } from 'react'
import { STATUS_LABEL } from '../lib/constants'
import { currentLocale, useI18n } from '../lib/i18n'
import type { ComplaintStatus, Priority } from '../lib/types'

export function Logo({ light = false, size = 'md' }: { light?: boolean; size?: 'md' | 'lg' }) {
  return (
    <span className="inline-flex items-center gap-2" dir="ltr">
      <span
        className={clsx(
          'grid place-items-center rounded-xl',
          size === 'lg' ? 'h-11 w-11' : 'h-9 w-9',
          light ? 'bg-paper text-deep' : 'bg-forest text-cream',
        )}
      >
        <MapPin className={size === 'lg' ? 'h-6 w-6' : 'h-5 w-5'} />
      </span>
      <span className={clsx('font-extrabold tracking-tight', size === 'lg' ? 'text-3xl' : 'text-xl')}>
        <span className={light ? 'text-paper' : 'text-forest'}>Shehri</span>
        <span className={light ? 'text-sandc' : 'text-leaf'}>Link</span>
      </span>
    </span>
  )
}

const PRIORITY_STYLE: Record<Priority, string> = {
  CRITICAL: 'bg-crit text-white',
  HIGH: 'bg-high text-white',
  MEDIUM: 'bg-med/20 text-medtext ring-1 ring-med/50',
  LOW: 'bg-leaf/15 text-leaf ring-1 ring-leaf/30',
}
export function PriorityBadge({ value }: { value: Priority | null }) {
  const { t } = useI18n()
  if (!value) return <span className="text-ink/40">—</span>
  return <span className={clsx('whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-bold', PRIORITY_STYLE[value])}>{t(value)}</span>
}

const STATUS_STYLE: Record<ComplaintStatus, string> = {
  RECEIVED: 'bg-sand text-forest',
  ASSIGNED: 'bg-leaf/15 text-leaf',
  VERIFIED: 'bg-leaf/15 text-leaf',
  VERIFICATION_FAILED: 'bg-high/15 text-high',
  REPLANNING: 'bg-med/20 text-medtext',
  CLOSED: 'bg-forest text-cream',
  ESCALATED: 'bg-crit/10 text-crit ring-1 ring-crit/40',
}
export function StatusBadge({ value }: { value: ComplaintStatus }) {
  const { t } = useI18n()
  return (
    <span className={clsx('whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold', STATUS_STYLE[value])}>
      {t(STATUS_LABEL[value])}
    </span>
  )
}

export function StatCard({
  icon, label, value, hint, tone = 'default',
}: { icon: ReactNode; label: string; value: ReactNode; hint?: string; tone?: 'default' | 'danger' | 'dark' }) {
  return (
    <div className={clsx('card p-5', tone === 'dark' && '!bg-deep !border-deep text-paper')}>
      <div className="flex items-center justify-between">
        <span className={clsx('text-sm font-medium', tone === 'dark' ? 'text-sandc' : 'text-ink/60')}>{label}</span>
        <span
          className={clsx(
            'grid h-9 w-9 place-items-center rounded-xl',
            tone === 'dark' ? 'bg-paper/15' : tone === 'danger' ? 'bg-crit/10 text-crit' : 'bg-sand text-forest',
          )}
        >
          {icon}
        </span>
      </div>
      <div className={clsx('mt-3 text-3xl font-extrabold', tone === 'dark' ? 'text-paper' : tone === 'danger' ? 'text-crit' : 'text-forest')}>
        {value}
      </div>
      {hint && <div className={clsx('mt-1 text-xs', tone === 'dark' ? 'text-sandc' : 'text-ink/50')}>{hint}</div>}
    </div>
  )
}

export function PageTitle({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-extrabold sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink/60">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="card grid place-items-center px-6 py-14 text-center">
      <div className="text-lg font-bold text-forest">{title}</div>
      {hint && <p className="mt-1 max-w-sm text-sm text-ink/60">{hint}</p>}
    </div>
  )
}

export const fmtDate = (iso?: string) =>
  iso ? new Date(iso).toLocaleString(currentLocale(), { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'
