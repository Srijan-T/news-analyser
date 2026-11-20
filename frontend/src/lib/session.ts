// Set when a request comes back 401 mid-session (see main.tsx), so the sign-in page can say
// why it appeared. A deliberate "Sign out" doesn't set it.
let expired = false

export function noteSessionExpired(): void {
  expired = true
}

export function sessionExpired(): boolean {
  return expired
}

export function clearSessionExpired(): void {
  expired = false
}
