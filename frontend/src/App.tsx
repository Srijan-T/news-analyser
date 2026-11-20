import { Link, NavLink, Route, Routes } from 'react-router'
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
        {/* Phones: title and controls on the first row, the nav on its own row below. */}
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-6 py-3">
          <span className="text-lg font-semibold whitespace-nowrap">News Analyser</span>
          <nav className="order-last flex w-full gap-1 sm:order-none sm:w-auto">
            <NavLink to="/" end className={navClass}>
              Search
            </NavLink>
            <NavLink to="/history" className={navClass}>
              History
            </NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-3 sm:gap-4">
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
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  )
}

function NotFound() {
  return (
    <div className="mx-auto max-w-md space-y-3 py-16 text-center">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="text-soft">There's nothing at this address.</p>
      <Link to="/" className="inline-block font-medium underline">
        Go to Search
      </Link>
    </div>
  )
}
