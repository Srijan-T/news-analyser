import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { ApiError, SESSION_KEY, api } from '../api/client.ts'

/** Shows the sign-in page until the user has a session (when the server requires one). */
export function AuthGate({ children }: { children: ReactNode }) {
  const session = useQuery({ queryKey: SESSION_KEY, queryFn: api.session })

  if (session.isPending) return null
  // If the session check itself fails (e.g. server down), show the app; its own error
  // states explain the problem better than a sign-in form would.
  if (session.isSuccess && session.data.auth_required && !session.data.authenticated) {
    return <SignInPage />
  }
  return <>{children}</>
}

function SignInPage() {
  const queryClient = useQueryClient()
  const [password, setPassword] = useState('')
  const login = useMutation({
    mutationFn: api.login,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: SESSION_KEY }),
  })

  const error =
    login.error instanceof ApiError && login.error.code === 'invalid_password'
      ? "That password isn't right."
      : login.error
        ? 'Could not sign in. Try again.'
        : null

  return (
    <main className="flex min-h-screen items-center justify-center bg-canvas px-6">
      <form
        className="w-full max-w-sm space-y-4 rounded-lg border border-line bg-surface p-6"
        onSubmit={(e) => {
          e.preventDefault()
          if (password) login.mutate(password)
        }}
      >
        <div>
          <h1 className="text-xl font-semibold">News Analyser</h1>
          <p className="mt-1 text-sm text-soft">Enter the access password to continue.</p>
        </div>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-label="Password"
          placeholder="Password"
          autoComplete="current-password"
          autoFocus
          className="w-full rounded-md border border-line-strong px-3 py-2 focus:border-muted focus:outline-none"
        />
        {error && (
          <p role="alert" className="text-sm text-danger-fg">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={!password || login.isPending}
          className="w-full rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-fg disabled:opacity-40"
        >
          {login.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  )
}

/** "Sign out" link for the header; hidden when the server doesn't require sign-in. */
export function SignOutButton() {
  const queryClient = useQueryClient()
  const session = useQuery({ queryKey: SESSION_KEY, queryFn: api.session })
  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: SESSION_KEY }),
  })

  if (!session.data?.auth_required) return null
  return (
    <button
      onClick={() => logout.mutate()}
      className="text-xs text-muted hover:text-fg hover:underline"
    >
      Sign out
    </button>
  )
}
