import { ArrowDown, ArrowUp, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Empty, PageTitle, PriorityBadge, StatusBadge, fmtDate } from '../../components/ui'
import { CATEGORIES, PRIORITIES, STATUSES, STATUS_LABEL, ZONES, label } from '../../lib/constants'
import { useI18n } from '../../lib/i18n'
import { useComplaints } from '../../lib/useComplaints'

const PRIO_RANK = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 } as const
type SortKey = 'date' | 'priority'
const PAGE = 12

function Select({ value, onChange, all, options }: { value: string; onChange: (v: string) => void; all: string; options: [string, string][] }) {
  return (
    <select className="input !w-auto" value={value} onChange={(e) => onChange(e.target.value)} aria-label={all}>
      <option value="">{all}</option>
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  )
}

export default function Complaints() {
  const { t } = useI18n()
  const { complaints: all, liveIds } = useComplaints()
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')
  const [zone, setZone] = useState('')
  const [category, setCategory] = useState('')
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'date', dir: -1 })
  const [page, setPage] = useState(0)

  const rows = useMemo(() => {
    const term = q.trim().toLowerCase()
    const list = all.filter(
      (c) =>
        (!status || c.status === status) && (!priority || c.priority === priority) &&
        (!zone || c.zone === zone) && (!category || c.category === category) &&
        (!term || `${c.complaint_id} ${c.description} ${c.area} ${c.assigned_team_name}`.toLowerCase().includes(term)),
    )
    return list.sort((a, b) => {
      const v = sort.key === 'date'
        ? (a.submitted_at ?? '').localeCompare(b.submitted_at ?? '')
        : PRIO_RANK[a.priority ?? 'LOW'] - PRIO_RANK[b.priority ?? 'LOW']
      return v * sort.dir
    })
  }, [all, q, status, priority, zone, category, sort])

  const pages = Math.max(1, Math.ceil(rows.length / PAGE))
  const cur = Math.min(page, pages - 1)
  const slice = rows.slice(cur * PAGE, cur * PAGE + PAGE)
  const reset = <T,>(set: (v: T) => void) => (v: T) => { set(v); setPage(0) }
  const toggle = (key: SortKey) => setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: -1 }))
  const Arrow = ({ k }: { k: SortKey }) => (sort.key === k ? (sort.dir === 1 ? <ArrowUp className="inline h-3 w-3" /> : <ArrowDown className="inline h-3 w-3" />) : null)

  return (
    <>
      <PageTitle title={t('Complaints')} subtitle={t('{n} of {m} complaints', { n: rows.length, m: all.length })} />

      <div className="card mb-4 flex flex-wrap items-center gap-3 p-4">
        <div className="relative min-w-[200px] flex-1">
          <Search className="absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink/40" />
          <input className="input !ps-9" placeholder={t('Search ID, text, area, team…')} value={q} onChange={(e) => reset(setQ)(e.target.value)} />
        </div>
        <Select value={status} onChange={reset(setStatus)} all={t('All statuses')} options={STATUSES.map((s) => [s, t(STATUS_LABEL[s])])} />
        <Select value={priority} onChange={reset(setPriority)} all={t('All priorities')} options={PRIORITIES.map((p) => [p, t(p)])} />
        <Select value={zone} onChange={reset(setZone)} all={t('All zones')} options={ZONES.map((z) => [z, t(z)])} />
        <Select value={category} onChange={reset(setCategory)} all={t('All categories')} options={CATEGORIES.map((c) => [c, t(label(c))])} />
      </div>

      {slice.length === 0 ? (
        <Empty title={t('No complaints match')} hint={t('Try removing a filter or searching for something else.')} />
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[980px] text-start text-sm">
            <thead className="border-b border-sand bg-sand/30 text-xs uppercase tracking-wide text-ink/60">
              <tr>
                <th className="px-4 py-3 text-start">{t('ID')}</th>
                <th className="px-4 py-3 text-start">{t('Problem')}</th>
                <th className="px-4 py-3 text-start">{t('Area')}</th>
                <th className="cursor-pointer px-4 py-3 text-start" onClick={() => toggle('priority')}>{t('Priority')} <Arrow k="priority" /></th>
                <th className="px-4 py-3 text-start">{t('Status')}</th>
                <th className="px-4 py-3 text-start">{t('Team')}</th>
                <th className="cursor-pointer px-4 py-3 text-start" onClick={() => toggle('date')}>{t('Submitted')} <Arrow k="date" /></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-sand">
              {slice.map((c) => (
                <tr key={c.complaint_id} className="hover:bg-sand/25">
                  <td className="whitespace-nowrap px-4 py-3 font-semibold" dir="ltr"><Link className="text-forest hover:underline" to={`/admin/complaints/${c.complaint_id}`}>{c.complaint_id}</Link>{liveIds.has(c.complaint_id) && <span className="ms-2 rounded bg-leaf/15 px-1.5 py-0.5 text-[10px] font-bold text-leaf">{t('NEW')}</span>}</td>
                  <td className="max-w-[260px] px-4 py-3"><div className="font-medium">{t(label(c.category))}</div><div className="truncate text-xs text-ink/55" dir="auto">{c.description}</div></td>
                  <td className="px-4 py-3">{t(c.area ?? '')}<div className="text-xs text-ink/50">{t(c.zone ?? '')}</div></td>
                  <td className="px-4 py-3"><PriorityBadge value={c.priority} /></td>
                  <td className="px-4 py-3"><StatusBadge value={c.status} /></td>
                  <td className="px-4 py-3 text-ink/70">{c.assigned_team_name ? t(c.assigned_team_name) : '—'}{c.retry_count > 0 && <div className="text-xs text-high">{c.retry_count} {t(c.retry_count > 1 ? 'retries' : 'retry')}</div>}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-ink/60">{fmtDate(c.submitted_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pages > 1 && (
        <div className="mt-4 flex items-center justify-end gap-3 text-sm">
          <span className="text-ink/60">{t('Page {n} of {m}', { n: cur + 1, m: pages })}</span>
          <button className="btn-ghost !py-1.5" disabled={cur === 0} onClick={() => setPage(cur - 1)}>{t('Previous')}</button>
          <button className="btn-ghost !py-1.5" disabled={cur >= pages - 1} onClick={() => setPage(cur + 1)}>{t('Next')}</button>
        </div>
      )}
    </>
  )
}
