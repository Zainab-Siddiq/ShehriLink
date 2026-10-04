import {
  ArrowRight, Building2, CheckCircle2, Copy, FileText, MapPin, RefreshCw, ShieldCheck, Siren, Tags, Users,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { DUMMY_COMPLAINTS } from '../data/dummy'
import { useI18n } from '../lib/i18n'

const AGENTS = [
  { icon: Tags, title: 'Understands', text: 'Reads your complaint and works out what kind of problem it is.' },
  { icon: MapPin, title: 'Locates', text: 'Finds your area and zone. It never guesses a place you did not mention.' },
  { icon: Copy, title: 'Checks duplicates', text: 'Spots if neighbours already reported the same issue.' },
  { icon: Siren, title: 'Sets priority', text: 'An open manhole near a school comes before a faded road sign.' },
  { icon: Building2, title: 'Picks the department', text: 'Routes it to the right department automatically.' },
  { icon: Users, title: 'Assigns a team', text: 'Chooses an available team by zone and workload.' },
]

const PREVIEW: [string, string][] = [
  ['Classified: streetlight', 'bg-leaf'],
  ['Priority: Medium · Electrical Dept.', 'bg-leaf'],
  ['Team ELEC-A assigned', 'bg-leaf'],
  ['Verification failed — still dark', 'bg-crit'],
  ['Replanned → Rapid Response Team', 'bg-med'],
  ['Verification passed · Closed', 'bg-leaf'],
]

const LOOP: [typeof FileText, string][] = [
  [FileText, 'Team reports the fix'],
  [CheckCircle2, 'Citizen feedback is checked'],
  [RefreshCw, 'Not fixed? Replan and reassign'],
  [Siren, 'Still failing? Escalate to a supervisor'],
]

export default function Landing() {
  const { t } = useI18n()
  const total = DUMMY_COMPLAINTS.length
  const closed = DUMMY_COMPLAINTS.filter((c) => c.status === 'CLOSED').length
  const rate = Math.round((closed / total) * 100)

  return (
    <>
      {/* hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-sand/60 to-cream" />
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-16 sm:py-24 lg:grid-cols-2">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full bg-forest/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-forest">
              <ShieldCheck className="h-3.5 w-3.5" /> {t('Closed only when it is truly fixed')}
            </span>
            <h1 className="mt-5 text-4xl font-extrabold leading-tight sm:text-5xl">
              {t("Your city's problems,")} <span className="text-leaf">{t('linked to real solutions.')}</span>
            </h1>
            <p className="mt-5 max-w-lg text-lg text-ink/70">
              {t('Report a broken streetlight, blocked drain or missed garbage pickup. AI agents route it to the right team — and a complaint is only closed after the fix is confirmed.')}
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/submit" className="btn-primary !px-6 !py-3 text-base">{t('Report a problem')} <ArrowRight className="h-4 w-4 rtl:rotate-180" /></Link>
              <Link to="/track" className="btn-ghost !px-6 !py-3 text-base">{t('Track a complaint')}</Link>
            </div>
            <p className="font-urdu mt-6 text-lg leading-loose text-forest" dir="rtl" lang="ur">آپ کی شکایت، ہماری ذمہ داری</p>
          </div>

          {/* preview card */}
          <div className="card p-5 sm:p-6" aria-hidden>
            <div className="mb-4 flex items-center justify-between">
              <span className="font-bold text-forest">{t('C-1004 · Streetlight, Canal Town')}</span>
              <span className="rounded-full bg-forest px-2.5 py-0.5 text-xs font-semibold text-cream">{t('Closed')}</span>
            </div>
            {PREVIEW.map(([text, color]) => (
              <div key={text} className="flex items-center gap-3 py-1.5 text-sm">
                <span className={`h-2.5 w-2.5 rounded-full ${color}`} /> {t(text)}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* stats */}
      <section className="mx-auto -mt-2 max-w-6xl px-4">
        <div className="card grid grid-cols-2 gap-6 p-6 text-center sm:grid-cols-4">
          {[
            [String(total), 'Complaints this fortnight'],
            [`${rate}%`, 'Resolved & verified'],
            ['12', 'Areas covered'],
            ['4', 'Zones'],
          ].map(([n, l]) => (
            <div key={l}>
              <div className="text-3xl font-extrabold text-forest">{n}</div>
              <div className="text-sm text-ink/60">{t(l)}</div>
            </div>
          ))}
        </div>
      </section>

      {/* how it works */}
      <section className="mx-auto max-w-6xl px-4 py-20">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-extrabold">{t('How your complaint is handled')}</h2>
          <p className="mt-2 text-ink/60">{t('Six AI agents work in sequence, in seconds. You can watch every step.')}</p>
        </div>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {AGENTS.map((a, i) => (
            <div key={a.title} className="card p-5">
              <div className="flex items-center gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-forest text-cream"><a.icon className="h-5 w-5" /></span>
                <span className="text-xs font-bold text-leaf">{t('STEP')} {i + 1}</span>
              </div>
              <h3 className="mt-3 text-lg font-bold">{t(a.title)}</h3>
              <p className="mt-1 text-sm text-ink/65">{t(a.text)}</p>
            </div>
          ))}
        </div>
      </section>

      {/* verification loop */}
      <section className="bg-deep text-paper">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-16 lg:grid-cols-2">
          <div>
            <h2 className="text-3xl font-extrabold !text-paper">{t('"Fixed" must be proven')}</h2>
            <p className="mt-3 text-sandc">
              {t('A team saying the job is done is not enough. We check with you. If it is still broken, the complaint is replanned and given to a different team. After repeated failures it goes to a human supervisor — it never just disappears.')}
            </p>
            <Link to="/submit" className="btn mt-6 bg-paper text-deep hover:bg-sandc">{t('Try it now')} <ArrowRight className="h-4 w-4 rtl:rotate-180" /></Link>
          </div>
          <div className="grid gap-3">
            {LOOP.map(([Icon, text]) => (
              <div key={text} className="flex items-center gap-4 rounded-2xl bg-paper/10 px-5 py-4">
                <Icon className="h-5 w-5 text-sandc" />
                <span className="font-semibold">{t(text)}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  )
}
