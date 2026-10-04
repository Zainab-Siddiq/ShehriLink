import { Loader2, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import ComplaintView from '../components/ComplaintView'
import { getComplaint } from '../lib/api'
import { useI18n } from '../lib/i18n'
import type { Complaint } from '../lib/types'

export default function Track() {
  const { id } = useParams()
  const nav = useNavigate()
  const { t } = useI18n()
  const [input, setInput] = useState(id ?? '')
  const [loading, setLoading] = useState(false)
  const [complaint, setComplaint] = useState<Complaint | null>(null)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    if (!id) { setComplaint(null); setNotFound(false); return }
    let live = true
    setLoading(true); setNotFound(false)
    getComplaint(id).then((c) => {
      if (!live) return
      setComplaint(c); setNotFound(!c); setLoading(false)
    })
    return () => { live = false }
  }, [id])

  return (
    <section className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-2xl font-extrabold sm:text-3xl">{t('Track your complaint')}</h1>
      <p className="mt-1 text-ink/60">{t('Enter the complaint ID you received when you reported the problem.')}</p>

      <form
        className="mt-6 flex gap-2"
        onSubmit={(e) => { e.preventDefault(); if (input.trim()) nav(`/track/${input.trim()}`) }}
      >
        <input className="input" dir="ltr" value={input} onChange={(e) => setInput(e.target.value)} placeholder="C-2004" aria-label={t('Complaint ID')} />
        <button className="btn-primary shrink-0"><Search className="h-4 w-4" /> {t('Track')}</button>
      </form>
      {!id && (
        <p className="mt-3 text-sm text-ink/55">
          {t('Want to see an example? Try')} <button className="font-semibold text-leaf underline" onClick={() => nav('/track/C-2001')}>C-2001</button>.
        </p>
      )}

      <div className="mt-8">
        {loading && <div className="flex items-center gap-2 text-ink/60"><Loader2 className="h-4 w-4 animate-spin" /> {t('Looking it up…')}</div>}
        {notFound && (
          <div className="card px-6 py-10 text-center">
            <p className="text-lg font-bold text-forest">{t("We couldn't find")} "{id}"</p>
            <p className="mt-1 text-sm text-ink/60">{t('Check the ID and try again. IDs look like C-1234.')}</p>
          </div>
        )}
        {complaint && !loading && <ComplaintView c={complaint} />}
      </div>
    </section>
  )
}
