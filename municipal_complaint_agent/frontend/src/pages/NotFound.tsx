import { Link } from 'react-router-dom'
import { useI18n } from '../lib/i18n'

export default function NotFound() {
  const { t } = useI18n()
  return (
    <section className="mx-auto max-w-md px-4 py-24 text-center">
      <p className="text-6xl font-extrabold text-leaf">404</p>
      <h1 className="mt-2 text-2xl font-extrabold">{t('Page not found')}</h1>
      <p className="mt-2 text-ink/60">{t('The page you are looking for does not exist.')}</p>
      <Link to="/" className="btn-primary mt-6">{t('Back to home')}</Link>
    </section>
  )
}
