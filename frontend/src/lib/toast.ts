import { createContext, useContext } from 'react'

export type ToastTone = 'info' | 'success'
export type ShowToast = (message: string, tone?: ToastTone) => void

export const ToastContext = createContext<ShowToast>(() => {})

/** Show a short, auto-dismissing notice: `toast('Analysis saved', 'success')`. */
export function useToast(): ShowToast {
  return useContext(ToastContext)
}
