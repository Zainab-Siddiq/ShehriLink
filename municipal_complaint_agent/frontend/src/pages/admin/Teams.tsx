import clsx from 'clsx'
import { useState } from 'react'
import { PageTitle } from '../../components/ui'
import { DUMMY_TEAMS } from '../../data/dummy'
import { useI18n } from '../../lib/i18n'

export default function Teams() {
  const { t } = useI18n()
  const depts = Array.from(new Set(DUMMY_TEAMS.map((x) => x.department)))
  const [dept, setDept] = useState('')
  const list = DUMMY_TEAMS.filter((x) => !dept || x.department === dept)

  return (
    <>
      <PageTitle
        title={t('Field teams')}
        subtitle={t('Availability and workload. The assignment agent only picks available teams with spare capacity.')}
        action={
          <select className="input !w-auto" value={dept} onChange={(e) => setDept(e.target.value)} aria-label={t('Department')}>
            <option value="">{t('All departments')}</option>
            {depts.map((d) => <option key={d} value={d}>{t(d)}</option>)}
          </select>
        }
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {list.map((x) => {
          const load = x.active_tasks / x.capacity
          return (
            <div key={x.team_id} className="card p-5">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-bold text-forest">{t(x.name)}</div>
                  <div className="text-xs text-ink/55"><span dir="ltr">{x.team_id}</span> · {t(x.zone)}</div>
                </div>
                <span className={clsx('rounded-full px-2.5 py-0.5 text-xs font-semibold', x.available ? 'bg-leaf/15 text-leaf' : 'bg-crit/10 text-crit')}>
                  {x.available ? t('Available') : t('Unavailable')}
                </span>
              </div>
              <div className="mt-4 flex justify-between text-xs text-ink/60">
                <span>{t('Workload')}</span><span>{x.active_tasks} / {x.capacity} {t('tasks')}</span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-sand">
                <div className={clsx('h-full rounded-full', load >= 0.8 ? 'bg-high' : 'bg-leaf')} style={{ width: `${Math.min(100, load * 100)}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    </>
  )
}
