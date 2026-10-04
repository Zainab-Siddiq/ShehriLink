import { AlertTriangle, Building2, CheckCircle2, Copy, MapPin, Users } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { label } from '../lib/constants'
import { useI18n } from '../lib/i18n'
import type { Complaint } from '../lib/types'
import ProgressSteps from './ProgressSteps'
import Timeline from './Timeline'
import { PriorityBadge, StatusBadge } from './ui'

function Fact({ icon, title, value, sub }: { icon: ReactNode; title: string; value: ReactNode; sub?: string }) {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-sand text-forest">{icon}</span>
      <div className="min-w-0">
        <div className="text-xs font-medium uppercase tracking-wide text-ink/50">{title}</div>
        <div className="font-semibold text-forest">{value}</div>
        {sub && <div className="text-xs text-ink/55">{sub}</div>}
      </div>
    </div>
  )
}

export function Outcome({ c }: { c: Complaint }) {
  const { t } = useI18n()
  if (c.status === 'CLOSED')
    return (
      <div className="flex items-start gap-3 rounded-2xl bg-deep p-4 text-paper">
        <CheckCircle2 className="mt-0.5 h-6 w-6 shrink-0" />
        <div>
          <p className="font-bold">{t('Problem fixed and confirmed')}</p>
          <p className="text-sm text-sandc">
            {c.retry_count > 0
              ? t('The first team could not solve it, so we reassigned it. Closed after {n} attempts.', { n: c.retry_count + 1 })
              : t('Closed after the first verified attempt.')}
          </p>
        </div>
      </div>
    )
  if (c.status === 'ESCALATED')
    return (
      <div className="flex items-start gap-3 rounded-2xl border border-high/40 bg-high/10 p-4 text-ink">
        <AlertTriangle className="mt-0.5 h-6 w-6 shrink-0 text-high" />
        <div>
          <p className="font-bold text-high">{t('Passed to a supervisor')}</p>
          <p className="text-sm text-ink/70">{t(c.escalation_reason ?? 'A human officer will take over this complaint.')}</p>
        </div>
      </div>
    )
  const waiting = c.status === 'ASSIGNED' && c.verification_scenario === 'manual' && c.verification_status === 'pending'
  return (
    <div className="rounded-2xl border border-sand bg-surface/70 p-4 text-sm text-ink/70">
      {waiting
        ? t('A team is assigned. The complaint stays open until an officer verifies the fix.')
        : t('Work is in progress. We only close a complaint after the fix is confirmed.')}
    </div>
  )
}

export default function ComplaintView({ c, animate = false, onDone }: { c: Complaint; animate?: boolean; onDone?: () => void }) {
  const { t } = useI18n()
  // while the timeline is still animating, hold back the result so it doesn't spoil the reveal
  const [done, setDone] = useState(!animate)
  return (
    <div className="space-y-6">
      <div className="card p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-extrabold" dir="ltr">{c.complaint_id}</h2>
            <button
              className="text-ink/40 hover:text-forest"
              title={t('Copy complaint ID')}
              aria-label={t('Copy complaint ID')}
              onClick={() => navigator.clipboard?.writeText(c.complaint_id)}
            >
              <Copy className="h-4 w-4" />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <PriorityBadge value={c.priority} />
            <StatusBadge value={c.status} />
          </div>
        </div>
        <p className="mt-3 text-ink/80" dir="auto">{c.description}</p>

        {c.duplicate && (
          <div className="mt-4 rounded-xl border border-med/50 bg-med/10 px-4 py-3 text-sm">
            <b className="text-medtext">{t('Possible duplicate')}</b> {t('of')} {c.related_complaint_id}. {c.duplicate_reason}
          </div>
        )}

        <div className="mt-6 grid gap-5 sm:grid-cols-3">
          <Fact
            icon={<MapPin className="h-4 w-4" />} title={t('Location')}
            value={c.area && c.area !== 'unknown' ? t(c.area) : t('Not identified')}
            sub={c.zone && c.zone !== 'unknown' ? t(c.zone) : undefined}
          />
          <Fact icon={<Building2 className="h-4 w-4" />} title={t('Department')} value={c.department ? t(c.department) : '—'} sub={t(label(c.category))} />
          <Fact
            icon={<Users className="h-4 w-4" />} title={t('Assigned team')}
            value={c.assigned_team_name ? t(c.assigned_team_name) : t('Not yet assigned')}
            sub={c.retry_count ? `${c.retry_count} ${t(c.retry_count > 1 ? 'failed attempts' : 'failed attempt')}` : undefined}
          />
        </div>
      </div>

      {done && (
        <>
          <div className="card animate-slide-in p-5 sm:p-6">
            <ProgressSteps complaint={c} />
          </div>
          <div className="animate-slide-in"><Outcome c={c} /></div>
        </>
      )}

      <div className="card p-5 sm:p-6">
        <h3 className="mb-1 text-lg font-bold">{t('What our agents did')}</h3>
        <p className="mb-5 text-sm text-ink/55">{t('Every step is recorded so you can see exactly how your complaint was handled.')}</p>
        <Timeline history={c.history} animate={animate} onDone={() => { setDone(true); onDone?.() }} />
      </div>
    </div>
  )
}
