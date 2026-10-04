import clsx from 'clsx'
import { Moon, Sun } from 'lucide-react'
import { useI18n } from '../lib/i18n'
import { useTheme } from '../lib/theme'

type Tone = 'light' | 'onDeep'

const base = 'grid h-9 place-items-center rounded-lg text-sm font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-leaf'
const tone = (t: Tone) => (t === 'onDeep' ? 'text-sandc hover:bg-paper/10' : 'text-forest hover:bg-sand/60')

export function ThemeToggle({ on = 'light' }: { on?: Tone }) {
  const { isDark, toggle } = useTheme()
  const { t } = useI18n()
  return (
    <button
      onClick={toggle}
      className={clsx(base, 'w-9', tone(on))}
      aria-label={isDark ? t('Switch to light mode') : t('Switch to dark mode')}
      title={isDark ? t('Switch to light mode') : t('Switch to dark mode')}
    >
      {isDark ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
    </button>
  )
}

export function LangToggle({ on = 'light' }: { on?: Tone }) {
  const { lang, setLang } = useI18n()
  const next = lang === 'en' ? 'ur' : 'en'
  return (
    <button
      onClick={() => setLang(next)}
      className={clsx(base, 'min-w-9 px-2.5', tone(on))}
      aria-label={lang === 'en' ? 'Switch to Urdu' : 'Switch to English'}
      title={lang === 'en' ? 'اردو' : 'English'}
      lang={next}
    >
      {lang === 'en' ? 'اردو' : 'EN'}
    </button>
  )
}
