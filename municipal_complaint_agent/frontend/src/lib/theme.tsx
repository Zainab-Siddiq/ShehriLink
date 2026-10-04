import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

type Theme = 'light' | 'dark'
interface Ctx { theme: Theme; isDark: boolean; toggle: () => void }
const ThemeCtx = createContext<Ctx>({ theme: 'light', isDark: false, toggle: () => {} })

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.classList.contains('dark') ? 'dark' : 'light',
  )

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    try { localStorage.setItem('sl-theme', theme) } catch { /* storage blocked */ }
  }, [theme])

  const toggle = useCallback(() => setTheme((t) => (t === 'dark' ? 'light' : 'dark')), [])
  const value = useMemo(() => ({ theme, isDark: theme === 'dark', toggle }), [theme, toggle])
  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>
}

export const useTheme = () => useContext(ThemeCtx)

/** Recharts takes literal colors, so charts read their palette from here. */
export function useChartTheme() {
  const { isDark } = useTheme()
  return useMemo(
    () => ({
      grid: isDark ? '#2c4130' : '#E7E1B1',
      axis: isDark ? '#b9c7b4' : '#3d5a44',
      cursor: isDark ? '#2c4130' : '#E7E1B1',
      greens: isDark
        ? ['#A8D696', '#7FBF6E', '#5FA050', '#4a8a3f', '#c9d69a', '#8fae6a', '#6aa05a']
        : ['#0D530E', '#306D29', '#6E9A4A', '#A9BF6B', '#E7E1B1', '#8a8f5a', '#4d7f3c'],
      line: isDark ? '#7FBF6E' : '#306D29',
      lineStrong: isDark ? '#A8D696' : '#0D530E',
      open: isDark ? '#5FA050' : '#A9BF6B',
      low: isDark ? '#7FBF6E' : '#306D29',
      tooltip: {
        contentStyle: {
          background: isDark ? '#17221a' : '#ffffff',
          border: `1px solid ${isDark ? '#2c4130' : '#E7E1B1'}`,
          borderRadius: 12,
          color: isDark ? '#e4ece0' : '#12301A',
          fontSize: 12,
        },
      },
    }),
    [isDark],
  )
}
