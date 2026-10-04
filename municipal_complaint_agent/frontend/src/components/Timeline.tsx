import clsx from 'clsx'
import { AlertTriangle, Check, Circle, RefreshCw, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { currentLocale, useI18n } from '../lib/i18n'
import type { HistoryEntry, StepStatus } from '../lib/types'

const ICON: Record<StepStatus, { icon: typeof Check; ring: string }> = {
  success: { icon: Check, ring: 'bg-leaf text-cream' },
  failed: { icon: X, ring: 'bg-crit text-white' },
  replanning: { icon: RefreshCw, ring: 'bg-med text-white' },
  escalated: { icon: AlertTriangle, ring: 'bg-high text-white' },
  info: { icon: Circle, ring: 'bg-sand text-forest' },
}

interface Props {
  history: HistoryEntry[]
  /** reveal steps one by one (used right after a complaint is submitted) */
  animate?: boolean
  stepMs?: number
  onDone?: () => void
}

export default function Timeline({ history, animate = false, stepMs = 650, onDone }: Props) {
  const { t } = useI18n()
  const [shown, setShown] = useState(animate ? 0 : history.length)

  useEffect(() => {
    if (!animate) { setShown(history.length); return }
    setShown(0)
    let n = 0
    const id = setInterval(() => {
      n += 1
      setShown(n)
      if (n >= history.length) { clearInterval(id); onDone?.() }
    }, stepMs)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history, animate, stepMs])

  const visible = history.slice(0, shown)
  const working = animate && shown < history.length

  return (
    <ol className="relative">
      {visible.map((h, i) => {
        const { icon: Icon, ring } = ICON[h.status] ?? ICON.info
        const last = i === visible.length - 1 && !working
        const detailEntries = Object.entries(h.details ?? {}).filter(([, v]) => v !== null && v !== '' && typeof v !== 'object')
        return (
          <li key={i} className="animate-slide-in relative flex gap-4 pb-5">
            {!last && <span className="absolute start-[15px] top-8 h-full w-px bg-sand" />}
            <span className={clsx('z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full', ring)}>
              <Icon className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className="font-semibold text-forest">{t(h.message || h.action)}</p>
                <time className="text-xs text-ink/45" dir="ltr">
                  {new Date(h.timestamp).toLocaleTimeString(currentLocale(), { hour: '2-digit', minute: '2-digit' })}
                </time>
              </div>
              <p className="text-sm text-ink/60">
                {t(h.agent)}
                {h.result && <span className="font-medium text-ink/80"> · {t(h.result)}</span>}
              </p>
              {detailEntries.length > 0 && (
                <dl className="mt-1.5 grid gap-x-4 gap-y-0.5 text-xs text-ink/60 sm:grid-cols-2">
                  {detailEntries.slice(0, 4).map(([k, v]) => (
                    <div key={k} className="truncate">
                      <dt className="inline font-medium">{t(k.replace(/_/g, ' '))}: </dt>
                      <dd className="inline">{String(v)}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          </li>
        )
      })}
      {working && (
        <li className="relative flex items-center gap-4 pb-2 text-sm text-ink/55">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-sand">
            <span className="h-3 w-3 animate-ping rounded-full bg-leaf" />
          </span>
          {t('Agents are working…')}
        </li>
      )}
    </ol>
  )
}
