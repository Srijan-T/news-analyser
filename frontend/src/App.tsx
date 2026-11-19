import { NavLink, Route, Routes } from 'react-router'
import { ApiStatus } from './components/ApiStatus.tsx'
import { SignOutButton } from './components/AuthGate.tsx'
import { ThemeToggle } from './components/ThemeToggle.tsx'
import { HistoryPage } from './pages/HistoryPage.tsx'
import { SearchPage } from './pages/SearchPage.tsx'

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm font-medium ${
    isActive ? 'bg-accent text-accent-fg' : 'text-soft hover:bg-subtle'
  }`

export default function App() {
  return (
    <div className="min-h-screen bg-canvas text-fg">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-6 py-3">
          <span className="text-lg font-semibold">News Analyser</span>
          <nav className="flex gap-1">
            <NavLink to="/" end className={navClass}>
              Search
            </NavLink>
            <NavLink to="/history" className={navClass}>
              History
            </NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-4">
            <ApiStatus />
            <ThemeToggle />
            <SignOutButton />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </main>
    </div>
  )
}
