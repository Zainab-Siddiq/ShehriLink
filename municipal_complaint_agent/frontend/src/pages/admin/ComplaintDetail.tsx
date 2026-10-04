import { ArrowLeft, CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { verifyComplaint } from '../../lib/api'
import type { Complaint } from '../../lib/types'
import { Outcome } from '../../components/ComplaintView'
import Timeline from '../../components/Timeline'
import { Empty, PriorityBadge, StatusBadge, fmtDate } from '../../components/ui'
import { label } from '../../lib/constants'
import { useI18n } from '../../lib/i18n'
import { useComplaints } from '../../lib/useComplaints'

function Row({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-sand/70 py-2 text-sm last:border-0">
      <dt className="text-ink/55">{k}</dt>
      <dd className="text-end font-medium">{v ?? '—'}</dd>
    </div>
  )
}
const pct = (n: number | null) => (n == null ? '—' : `${Math.round(n * 100)}%`)

/** Manual mode: the officer confirms the fix (closes the complaint) or rejects it (reassigns / escalates). */
function VerifyPanel({ c, onDone }: { c: Complaint; onDone: () => void }) {
  const { t } = useI18n()
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(passed: boolean) {
    setBusy(true)
    setError(null)
    try {
      await verifyComplaint(c.complaint_id, passed, note)
      onDone()
    } catch (err) {
      setError(err instanceof Error ? t(err.message) : t('Something went wrong. Please try again.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card mb-6 border-leaf/40 p-5">
      <h3 className="font-bold">{t('Manual verification')}</h3>
      <p className="mt-1 text-sm text-ink/60">
        {t('Check that the problem is really fixed. The complaint stays open until you confirm it.')}
      </p>
      <textarea
        rows={2} className="input mt-3 resize-y" value={note} onChange={(e) => setNote(e.target.value)}
        placeholder={t('Remark (optional)')} aria-label={t('Remark (optional)')}
      />
      {error && <div role="alert" className="mt-3 rounded-xl border border-crit/30 bg-crit/10 px-4 py-3 text-sm text-crit">{error}</div>}
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="btn-primary" disabled={busy} onClick={() => submit(true)}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />} {t('Fixed — close complaint')}
        </button>
        <button className="btn-ghost" disabled={busy} onClick={() => submit(false)}>
          <XCircle className="h-4 w-4" /> {t('Not fixed — reassign')}
        </button>
      </div>
    </div>
  )
}

export default function ComplaintDetail() {
  const { id = '' } = useParams()
  const { t } = useI18n()
  const { complaints, loading, reload } = useComplaints()
  const c = complaints.find((x) => x.complaint_id.toLowerCase() === id.toLowerCase())
  const back = (text: string) => (
    <Link to="/admin/complaints" className="mb-4 inline-flex items-center gap-1 text-sm font-semibold text-leaf">
      <ArrowLeft className="h-4 w-4 rtl:rotate-180" /> {text}
    </Link>
  )

  if (!c && loading) return <p className="text-ink/60">{t('Looking it up…')}</p>

  if (!c)
    return (
      <>
        {back(t('Back'))}
        <Empty title={t('Complaint not found')} hint={id} />
      </>
    )

  return (
    <>
      {back(t('All complaints'))}

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold sm:text-3xl" dir="ltr">{c.complaint_id}</h1>
          <p className="text-sm text-ink/60">{t('Submitted')} {fmtDate(c.submitted_at)}</p>
        </div>
        <div className="flex items-center gap-2"><PriorityBadge value={c.priority} /><StatusBadge value={c.status} /></div>
      </div>

      <div className="card mb-6 p-5"><p className="text-lg" dir="auto">{c.description}</p></div>
      <div className="mb-6"><Outcome c={c} /></div>
      {c.status === 'ASSIGNED' && c.verification_scenario === 'manual' && c.verification_status === 'pending' && (
        <VerifyPanel c={c} onDone={reload} />
      )}

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="card p-5 lg:col-span-3">
          <h3 className="mb-4 text-lg font-bold">{t('Agent activity')}</h3>
          <Timeline history={c.history} />
        </div>

        <div className="space-y-6 lg:col-span-2">
          <div className="card p-5">
            <h3 className="mb-2 font-bold">{t('Classification & location')}</h3>
            <dl>
              <Row k={t('Category')} v={t(label(c.category))} />
              <Row k={t('Subcategory')} v={t(label(c.subcategory))} />
              <Row k={t('Confidence')} v={pct(c.classification_confidence)} />
              <Row k={t('Area')} v={t(c.area ?? '')} />
              <Row k={t('Zone')} v={t(c.zone ?? '')} />
              <Row k={t('Location confidence')} v={pct(c.location_confidence)} />
            </dl>
          </div>
          <div className="card p-5">
            <h3 className="mb-2 font-bold">{t('Routing')}</h3>
            <dl>
              <Row k={t('Priority')} v={<PriorityBadge value={c.priority} />} />
              <Row k={t('Department')} v={t(c.department ?? '')} />
              <Row k={t('Current team')} v={c.assigned_team_name ? t(c.assigned_team_name) : '—'} />
              <Row k={t('Failed teams')} v={c.failed_teams.length ? <span dir="ltr">{c.failed_teams.join(', ')}</span> : t('None')} />
              <Row k={t('Retries')} v={`${c.retry_count} / ${c.max_retries}`} />
            </dl>
            <p className="mt-3 text-xs text-ink/55">{c.priority_reason}</p>
          </div>
          <div className="card p-5">
            <h3 className="mb-2 font-bold">{t('Verification')}</h3>
            <dl>
              <Row k={t('Status')} v={t(label(c.verification_status))} />
              <Row k={t('Team report')} v={c.team_report} />
              <Row k={t('Citizen feedback')} v={c.citizen_feedback} />
            </dl>
            {c.verification_reason && <p className="mt-3 text-xs text-ink/55">{c.verification_reason}</p>}
          </div>
        </div>
      </div>
    </>
  )
}
