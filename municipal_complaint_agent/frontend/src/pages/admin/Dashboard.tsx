import { AlertTriangle, CheckCircle2, Clock, Inbox } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { PageTitle, PriorityBadge, StatCard, StatusBadge, fmtDate } from '../../components/ui'
import { dailyCounts } from '../../data/dummy'
import { ZONES, label } from '../../lib/constants'
import { currentLocale, useI18n } from '../../lib/i18n'
import { useChartTheme } from '../../lib/theme'
import { useComplaints } from '../../lib/useComplaints'

const PRIO_COLOR = { CRITICAL: '#B3261E', HIGH: '#D9771A', MEDIUM: '#C9A227' } as const

export default function Dashboard() {
  const { t } = useI18n()
  const ct = useChartTheme()
  const { complaints: all, liveCount } = useComplaints()
  const closed = all.filter((c) => c.status === 'CLOSED').length
  const escalated = all.filter((c) => c.status === 'ESCALATED')
  const open = all.length - closed - escalated.length
  const replanning = all.filter((c) => c.status === 'REPLANNING').length

  const byCategory = Object.entries(
    all.reduce<Record<string, number>>((m, c) => ((m[c.category ?? 'other'] = (m[c.category ?? 'other'] ?? 0) + 1), m), {}),
  ).map(([name, value]) => ({ name: t(label(name)), value }))

  const byPriority = (['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((p) => ({
    key: p, name: t(p), count: all.filter((c) => c.priority === p).length,
  }))
  const byZone = ZONES.map((z) => ({
    zone: t(z),
    [t('Open')]: all.filter((c) => c.zone === z && c.status !== 'CLOSED' && c.status !== 'ESCALATED').length,
    [t('Closed')]: all.filter((c) => c.zone === z && c.status === 'CLOSED').length,
    [t('Escalated')]: all.filter((c) => c.zone === z && c.status === 'ESCALATED').length,
  }))
  const daily = dailyCounts(all).map((d) => ({ ...d, day: d.date.toLocaleDateString(currentLocale(), { day: '2-digit', month: 'short' }) }))
  const axis = { fontSize: 11, fill: ct.axis }

  return (
    <>
      <PageTitle title={t('Dashboard')} subtitle={liveCount ? `${t('Last 14 days · sample data for presentation')} · ${liveCount} ${t('live')}` : t('Last 14 days · sample data for presentation')} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard tone="dark" icon={<Inbox className="h-5 w-5" />} label={t('Total complaints')} value={all.length} hint={t('Last 14 days')} />
        <StatCard icon={<Clock className="h-5 w-5" />} label={t('In progress')} value={open} hint={`${replanning} ${t('being replanned')}`} />
        <StatCard icon={<CheckCircle2 className="h-5 w-5" />} label={t('Closed & verified')} value={closed} hint={`${Math.round((closed / all.length) * 100)}% ${t('resolution rate')}`} />
        <StatCard tone="danger" icon={<AlertTriangle className="h-5 w-5" />} label={t('Escalated')} value={escalated.length} hint={t('Need a supervisor')} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="card p-5 lg:col-span-2">
          <h3 className="mb-4 font-bold">{t('Complaints per day')}</h3>
          <div className="h-64" dir="ltr">
            <ResponsiveContainer>
              <AreaChart data={daily} margin={{ left: -20, right: 8 }}>
                <defs>
                  <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={ct.line} stopOpacity={0.35} /><stop offset="100%" stopColor={ct.line} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={ct.grid} vertical={false} />
                <XAxis dataKey="day" tick={axis} tickLine={false} interval={1} />
                <YAxis allowDecimals={false} tick={axis} tickLine={false} axisLine={false} />
                <Tooltip {...ct.tooltip} />
                <Legend iconType="circle" />
                <Area type="monotone" dataKey="received" name={t('Received')} stroke={ct.line} strokeWidth={2} fill="url(#g1)" />
                <Area type="monotone" dataKey="closed" name={t('Closed')} stroke={ct.lineStrong} strokeWidth={2} fill="none" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5">
          <h3 className="mb-4 font-bold">{t('By category')}</h3>
          <div className="h-64" dir="ltr">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={byCategory} dataKey="value" nameKey="name" innerRadius={48} outerRadius={80} paddingAngle={2} stroke="none">
                  {byCategory.map((_, i) => <Cell key={i} fill={ct.greens[i % ct.greens.length]} />)}
                </Pie>
                <Tooltip {...ct.tooltip} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5">
          <h3 className="mb-4 font-bold">{t('By priority')}</h3>
          <div className="h-56" dir="ltr">
            <ResponsiveContainer>
              <BarChart data={byPriority} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={ct.grid} vertical={false} />
                <XAxis dataKey="name" tick={axis} tickLine={false} interval={0} />
                <YAxis allowDecimals={false} tick={axis} tickLine={false} axisLine={false} />
                <Tooltip {...ct.tooltip} cursor={{ fill: ct.cursor, opacity: 0.4 }} />
                <Bar dataKey="count" name={t('Complaints')} radius={[6, 6, 0, 0]}>
                  {byPriority.map((p) => <Cell key={p.key} fill={p.key === 'LOW' ? ct.low : PRIO_COLOR[p.key]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5 lg:col-span-2">
          <h3 className="mb-4 font-bold">{t('By zone')}</h3>
          <div className="h-56" dir="ltr">
            <ResponsiveContainer>
              <BarChart data={byZone} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={ct.grid} vertical={false} />
                <XAxis dataKey="zone" tick={axis} tickLine={false} />
                <YAxis allowDecimals={false} tick={axis} tickLine={false} axisLine={false} />
                <Tooltip {...ct.tooltip} cursor={{ fill: ct.cursor, opacity: 0.4 }} />
                <Legend iconType="circle" />
                <Bar dataKey={t('Closed')} stackId="a" fill={ct.lineStrong} />
                <Bar dataKey={t('Open')} stackId="a" fill={ct.open} />
                <Bar dataKey={t('Escalated')} stackId="a" fill="#B3261E" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="card mt-6 p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-bold">{t('Needs attention')}</h3>
          <Link to="/admin/escalations" className="text-sm font-semibold text-leaf hover:underline">{t('View all')}</Link>
        </div>
        <ul className="divide-y divide-sand">
          {escalated.slice(0, 4).map((c) => (
            <li key={c.complaint_id}>
              <Link to={`/admin/complaints/${c.complaint_id}`} className="flex flex-wrap items-center justify-between gap-2 py-3 hover:bg-sand/30">
                <div className="min-w-0">
                  <span className="font-semibold text-forest">{c.complaint_id}</span>
                  <span className="ms-2 text-sm text-ink/60">{t(label(c.category))} · {t(c.area ?? '')}</span>
                </div>
                <div className="flex items-center gap-2">
                  <PriorityBadge value={c.priority} /><StatusBadge value={c.status} />
                  <span className="hidden text-xs text-ink/45 sm:inline">{fmtDate(c.submitted_at)}</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </>
  )
}
