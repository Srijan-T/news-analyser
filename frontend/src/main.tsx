import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { SESSION_KEY, isUnauthenticated } from './api/client.ts'
import App from './App.tsx'
import { AuthGate } from './components/AuthGate.tsx'
import { ToastProvider } from './components/ToastProvider.tsx'
import './index.css'
import { noteSessionExpired } from './lib/session.ts'

// If any request finds the session gone (expired or signed out elsewhere), re-check the
// session so AuthGate swaps back to the sign-in page.
const onError = (error: unknown) => {
  if (isUnauthenticated(error)) {
    noteSessionExpired()
    queryClient.invalidateQueries({ queryKey: SESSION_KEY })
  }
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError }),
  mutationCache: new MutationCache({ onError }),
  defaultOptions: {
    // One retry is enough; repeated retries would burn news-API quota on real failures.
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ToastProvider>
          <AuthGate>
            <App />
          </AuthGate>
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
