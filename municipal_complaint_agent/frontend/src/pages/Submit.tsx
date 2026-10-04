import { ChevronDown, Loader2, Send } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import ComplaintView from '../components/ComplaintView'
import { newComplaintId, submitComplaint } from '../lib/api'
import { AREAS, SCENARIOS } from '../lib/constants'
import { useI18n } from '../lib/i18n'
import type { Complaint } from '../lib/types'

export default function Submit() {
  const { t } = useI18n()
  const [description, setDescription] = useState('')
  const [area, setArea] = useState('')
  const [street, setStreet] = useState('')
  const [scenario, setScenario] = useState('manual')
  const [showAdv, setShowAdv] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Complaint | null>(null)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (description.trim().length < 10) {
      setError(t('Please describe the problem in a little more detail (at least 10 characters).'))
      return
    }
    setBusy(true)
    try {
      const location = [street.trim(), area].filter(Boolean).join(', ')
      const res = await submitComplaint({
        complaint_id: newComplaintId(),
        description: description.trim(),
        location: location || undefined,
        verification_scenario: scenario,
      })
      setResult(res)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setError(err instanceof Error ? t(err.message) : t('Something went wrong. Please try again.'))
    } finally {
      setBusy(false)
    }
  }

  if (result) {
    return (
      <section className="mx-auto max-w-3xl px-4 py-10">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold sm:text-3xl">{t('Complaint received')}</h1>
            <p className="text-sm text-ink/60">{t('Save your ID — you can track it any time.')}</p>
          </div>
          <div className="flex gap-2">
            <Link to={`/track/${result.complaint_id}`} className="btn-ghost">{t('Track page')}</Link>
            <button className="btn-primary" onClick={() => { setResult(null); setDescription(''); setStreet(''); setArea('') }}>
              {t('New complaint')}
            </button>
          </div>
        </div>
        <ComplaintView c={result} animate />
      </section>
    )
  }

  return (
    <section className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-extrabold sm:text-3xl">{t('Report a problem')}</h1>
      <p className="mt-1 text-ink/60">{t('Tell us what is wrong. We will find the right team and make sure it is really fixed.')}</p>

      <form onSubmit={onSubmit} className="card mt-6 space-y-5 p-5 sm:p-7" noValidate>
        <div>
          <label htmlFor="desc" className="label">{t('What is the problem?')}</label>
          <textarea
            id="desc" rows={5} className="input resize-y" value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t('e.g. The streetlight in front of my house has not worked since yesterday.')}
          />
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <label htmlFor="area" className="label">{t('Area')}</label>
            <select id="area" className="input" value={area} onChange={(e) => setArea(e.target.value)}>
              <option value="">{t('Not sure / not listed')}</option>
              {Object.entries(AREAS).map(([a, z]) => <option key={a} value={a}>{t(a)} ({t(z)})</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="street" className="label">{t('Street / landmark')} <span className="font-normal text-ink/45">({t('optional')})</span></label>
            <input id="street" className="input" value={street} onChange={(e) => setStreet(e.target.value)} placeholder={t('Near the main market')} />
          </div>
        </div>

        <div>
          <button type="button" onClick={() => setShowAdv(!showAdv)} className="flex items-center gap-1 text-sm font-semibold text-leaf">
            <ChevronDown className={`h-4 w-4 transition ${showAdv ? 'rotate-180' : ''}`} /> {t('Simulation options')}
          </button>
          {showAdv && (
            <div className="mt-3 rounded-xl bg-sand/40 p-4">
              <label htmlFor="scn" className="label">{t('Simulated field result')}</label>
              <select id="scn" className="input" value={scenario} onChange={(e) => setScenario(e.target.value)}>
                {SCENARIOS.map((s) => <option key={s.value} value={s.value}>{t(s.label)}</option>)}
              </select>
              <p className="mt-1.5 text-xs text-ink/60">{t(SCENARIOS.find((s) => s.value === scenario)?.hint ?? '')}. {t('Real citizen follow-up replaces this later.')}</p>
            </div>
          )}
        </div>

        {error && <div role="alert" className="rounded-xl border border-crit/30 bg-crit/10 px-4 py-3 text-sm text-crit">{error}</div>}

        <button className="btn-primary w-full !py-3" disabled={busy}>
          {busy ? <><Loader2 className="h-4 w-4 animate-spin" /> {t('Agents are processing…')}</> : <><Send className="h-4 w-4 rtl:-scale-x-100" /> {t('Submit complaint')}</>}
        </button>
      </form>
    </section>
  )
}
