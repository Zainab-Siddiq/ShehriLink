import clsx from 'clsx'
import { Check } from 'lucide-react'
import { useI18n } from '../lib/i18n'
import type { Complaint } from '../lib/types'

const STEPS = ['Received', 'Team assigned', 'Verifying', 'Closed']

/** Maps the backend status to a 0-3 step index for the citizen-facing progress bar. */
function stepOf(c: Complaint): { step: number; escalated: boolean } {
  switch (c.status) {
    case 'RECEIVED': return { step: 0, escalated: false }
    case 'ASSIGNED': return { step: 1, escalated: false }
    case 'VERIFIED': case 'VERIFICATION_FAILED': case 'REPLANNING': return { step: 2, escalated: false }
    case 'CLOSED': return { step: 3, escalated: false }
    case 'ESCALATED': return { step: 2, escalated: true }
  }
}

export default function ProgressSteps({ complaint }: { complaint: Complaint }) {
  const { t } = useI18n()
  const { step, escalated } = stepOf(complaint)
  return (
    <ol className="flex items-start">
      {STEPS.map((s, i) => {
        const done = i < step || (complaint.status === 'CLOSED' && i === 3)
        const current = i === step && !done
        const label = escalated && i === 2 ? 'Escalated' : s
        return (
          <li key={s} className="relative flex flex-1 flex-col items-center text-center">
            {i > 0 && (
              <span className={clsx('absolute end-1/2 top-4 h-0.5 w-full -translate-y-1/2', i <= step ? 'bg-leaf' : 'bg-sand')} />
            )}
            <span
              className={clsx(
                'relative z-10 grid h-8 w-8 place-items-center rounded-full text-sm font-bold',
                done && 'bg-forest text-cream',
                current && !escalated && 'bg-leaf text-cream ring-4 ring-leaf/25',
                current && escalated && 'bg-high text-white ring-4 ring-high/25',
                !done && !current && 'bg-sand text-forest/60',
              )}
            >
              {done ? <Check className="h-4 w-4" /> : i + 1}
            </span>
            <span className={clsx('mt-2 text-xs font-semibold sm:text-sm', current || done ? 'text-forest' : 'text-ink/45')}>{t(label)}</span>
          </li>
        )
      })}
    </ol>
  )
}
