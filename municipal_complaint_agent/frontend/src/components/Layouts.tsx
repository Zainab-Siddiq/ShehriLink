import clsx from 'clsx'
import { AlertTriangle, ExternalLink, LayoutDashboard, ListChecks, Menu, Users, X } from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useI18n } from '../lib/i18n'
import { LangToggle, ThemeToggle } from './Toggles'
import { Logo } from './ui'

const publicLinks = [
  { to: '/', label: 'Home', end: true },
  { to: '/submit', label: 'Report a problem' },
  { to: '/track', label: 'Track complaint' },
]

export function PublicLayout() {
  const [open, setOpen] = useState(false)
  const { t } = useI18n()
  const link = ({ isActive }: { isActive: boolean }) =>
    clsx('rounded-lg px-3 py-2 text-sm font-semibold transition', isActive ? 'bg-forest text-cream' : 'text-forest hover:bg-sand/60')
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-sand bg-cream/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-3">
          <Link to="/" aria-label="ShehriLink"><Logo /></Link>
          <nav className="hidden items-center gap-1 md:flex">
            {publicLinks.map((l) => <NavLink key={l.to} to={l.to} end={l.end} className={link}>{t(l.label)}</NavLink>)}
            <Link to="/admin" className="btn-ghost ms-2 !py-2">{t('Officer login')}</Link>
            <LangToggle /><ThemeToggle />
          </nav>
          <div className="flex items-center gap-1 md:hidden">
            <LangToggle /><ThemeToggle />
            <button className="grid h-9 w-9 place-items-center text-forest" onClick={() => setOpen(!open)} aria-label="Menu">
              {open ? <X /> : <Menu />}
            </button>
          </div>
        </div>
        {open && (
          <nav className="flex flex-col gap-1 border-t border-sand px-4 py-3 md:hidden" onClick={() => setOpen(false)}>
            {publicLinks.map((l) => <NavLink key={l.to} to={l.to} end={l.end} className={link}>{t(l.label)}</NavLink>)}
            <Link to="/admin" className="rounded-lg px-3 py-2 text-sm font-semibold text-forest">{t('Officer login')}</Link>
          </nav>
        )}
      </header>
      <main className="flex-1"><Outlet /></main>
      <footer className="bg-deep text-paper">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 px-4 py-8 sm:flex-row sm:items-center">
          <div>
            <Logo light />
            <p className="mt-2 text-sm text-sandc">{t('Aap ki shikayat, hamari zimmedari.')}</p>
          </div>
          <p className="text-xs text-sandc/80">{t('A complaint closes only when the problem is truly fixed and verified.')}</p>
        </div>
      </footer>
    </div>
  )
}

const adminLinks = [
  { to: '/admin', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/admin/complaints', label: 'Complaints', icon: ListChecks },
  { to: '/admin/escalations', label: 'Escalations', icon: AlertTriangle },
  { to: '/admin/teams', label: 'Teams', icon: Users },
]

export function AdminLayout() {
  const { t } = useI18n()
  const link = ({ isActive }: { isActive: boolean }) =>
    clsx(
      'flex items-center gap-3 whitespace-nowrap rounded-xl px-3.5 py-2.5 text-sm font-semibold transition',
      isActive ? 'bg-paper text-deep' : 'text-sandc hover:bg-paper/10',
    )
  return (
    <div className="min-h-screen lg:flex">
      <aside className="bg-deep lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-60 lg:shrink-0 lg:flex-col">
        <div className="flex items-center justify-between px-4 py-4 lg:block lg:px-5 lg:py-6">
          <div>
            <Link to="/admin"><Logo light /></Link>
            <span className="rounded-full bg-paper/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-sandc lg:mt-3 lg:inline-block">
              {t('Officer console')}
            </span>
          </div>
          <div className="flex gap-1 lg:mt-4"><LangToggle on="onDeep" /><ThemeToggle on="onDeep" /></div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-col lg:pb-0">
          {adminLinks.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} className={link}>
              <l.icon className="h-4 w-4" /> {t(l.label)}
            </NavLink>
          ))}
        </nav>
        <div className="hidden px-3 pb-5 lg:mt-auto lg:block">
          <Link to="/" className="flex items-center gap-2 rounded-xl px-3.5 py-2.5 text-sm text-sandc hover:bg-paper/10">
            <ExternalLink className="h-4 w-4" /> {t('Citizen site')}
          </Link>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 sm:px-8 sm:py-8">
        <Outlet />
      </main>
    </div>
  )
}
