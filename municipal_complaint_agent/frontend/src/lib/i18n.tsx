import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { UR } from './ur'

export type Lang = 'en' | 'ur'
type Vars = Record<string, string | number>

let current: Lang = 'en'
/** Locale for dates, usable outside React components. */
export const currentLocale = () => (current === 'ur' ? 'ur-PK' : 'en-GB')

const fill = (s: string, vars?: Vars) => (vars ? s.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? '')) : s)

function lookup(s: string): string | undefined {
  return UR[s] ?? UR[s.toLowerCase()]
}

/**
 * English text is the key. Urdu comes from the dictionary; backend-generated strings
 * (team names, "retry 1 of 3", "Canal Town (Zone A)") are matched by pattern.
 * Anything unknown is shown as-is.
 */
export function translate(s: string, lang: Lang, vars?: Vars): string {
  if (lang === 'en' || !s) return fill(s, vars)
  const hit = lookup(s)
  if (hit) return fill(hit, vars)

  let m = s.match(/^(.+) \((Zone [A-D])\)$/)
  if (m) return `${translate(m[1], lang)} (${translate(m[2], lang)})`
  m = s.match(/^Zone ([A-D])$/)
  if (m) return `${UR['zone']} ${m[1]}`
  m = s.match(/^retry (\d+) of (\d+)$/i)
  if (m) return fill(UR['retry {a} of {b}'], { a: m[1], b: m[2] })
  m = s.match(/^(.+) Rapid Response Team$/)
  if (m) return `${translate(m[1], lang)} ${UR['Rapid Response Team']}`
  m = s.match(/^(.+) Team ([A-D])$/)
  if (m) return `${translate(m[1], lang)} ${UR['Team']} ${m[2]}`
  return fill(s, vars)
}

interface Ctx { lang: Lang; setLang: (l: Lang) => void; t: (s: string, vars?: Vars) => string }
const I18nCtx = createContext<Ctx>({ lang: 'en', setLang: () => {}, t: (s) => s })

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => (document.documentElement.lang === 'ur' ? 'ur' : 'en'))
  current = lang

  useEffect(() => {
    current = lang
    const el = document.documentElement
    el.lang = lang
    el.dir = lang === 'ur' ? 'rtl' : 'ltr'
    try { localStorage.setItem('sl-lang', lang) } catch { /* storage blocked */ }
  }, [lang])

  const setLang = useCallback((l: Lang) => setLangState(l), [])
  const t = useCallback((s: string, vars?: Vars) => translate(s, lang, vars), [lang])
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t])
  return <I18nCtx.Provider value={value}>{children}</I18nCtx.Provider>
}

export const useI18n = () => useContext(I18nCtx)
