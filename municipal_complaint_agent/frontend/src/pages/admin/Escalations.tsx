import { AlertTriangle, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Empty, PageTitle, PriorityBadge, fmtDate } from '../../components/ui'
import { label } from '../../lib/constants'
import { useI18n } from '../../lib/i18n'
import { useComplaints } from '../../lib/useComplaints'

export default function Escalations() {
  const { t } = useI18n()
  const { complaints } = useComplaints()
  const list = complaints.filter((c) => c.status === 'ESCALATED')
  return (
    <>
      <PageTitle title={t('Escalation queue')} subtitle={t('Complaints the agents could not close. A human officer must take over.')} />
      {list.length === 0 ? (
        <Empty title={t('Nothing escalated')} hint={t('Every complaint is being handled by the automated workflow.')} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {list.map((c) => (
            <div key={c.complaint_id} className="card border-s-4 !border-s-crit p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-crit" />
                    <span className="font-extrabold text-forest">{c.complaint_id}</span>
                  </div>
                  <p className="mt-0.5 text-sm text-ink/60">{t(label(c.category))} · {t(c.area ?? '')} ({t(c.zone ?? '')})</p>
                </div>
                <PriorityBadge value={c.priority} />
              </div>
              <p className="mt-3 text-sm">{c.description}</p>
              <dl className="mt-3 grid grid-cols-2 gap-2 text-xs text-ink/65">
                <div><dt className="font-semibold">{t('Failed teams')}</dt><dd dir="ltr" className="text-start">{c.failed_teams.join(', ') || '—'}</dd></div>
                <div><dt className="font-semibold">{t('Attempts')}</dt><dd>{c.retry_count} / {c.max_retries}</dd></div>
                <div className="col-span-2"><dt className="font-semibold">{t('Reason')}</dt><dd>{t(c.escalation_reason ?? '')}</dd></div>
                <div className="col-span-2"><dt className="font-semibold">{t('Citizen said')}</dt><dd>"{t(c.citizen_feedback ?? '')}"</dd></div>
              </dl>
              <div className="mt-4 flex items-center justify-between">
                <span className="text-xs text-ink/45">{fmtDate(c.submitted_at)}</span>
                <Link to={`/admin/complaints/${c.complaint_id}`} className="btn-primary !py-2">{t('Review')} <ArrowRight className="h-4 w-4 rtl:rotate-180" /></Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
