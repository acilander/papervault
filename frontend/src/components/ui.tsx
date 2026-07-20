import { createContext, useCallback, useContext, useRef, useState, type ButtonHTMLAttributes, type PropsWithChildren, type ReactNode } from 'react'

type ButtonVariant = 'primary' | 'secondary' | 'success' | 'danger' | 'ghost'
type ButtonSize = 'sm' | 'md'
type BadgeVariant = 'info' | 'success' | 'warning' | 'danger' | 'neutral' | 'purple'
type ToastVariant = 'success' | 'error' | 'info'

const buttonStyles: Record<ButtonVariant, string> = {
  primary: 'bg-blue-600 text-white hover:bg-blue-700',
  secondary: 'border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800',
  success: 'bg-green-600 text-white hover:bg-green-700',
  danger: 'bg-red-600 text-white hover:bg-red-700',
  ghost: 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800',
}

const buttonSizes: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
}

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${buttonStyles[variant]} ${buttonSizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

const badgeStyles: Record<BadgeVariant, string> = {
  info: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  success: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  warning: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
  danger: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  neutral: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300',
  purple: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
}

export function Badge({ variant = 'neutral', className = '', children }: { variant?: BadgeVariant; className?: string; children: ReactNode }) {
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${badgeStyles[variant]} ${className}`}>{children}</span>
}

type Toast = { id: number; message: string; variant: ToastVariant }
type ToastContextValue = { toast: (message: string, variant?: ToastVariant) => void }

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: PropsWithChildren) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)

  const toast = useCallback((message: string, variant: ToastVariant = 'info') => {
    const id = nextId.current++
    setToasts(current => [...current, { id, message, variant }])
    window.setTimeout(() => setToasts(current => current.filter(item => item.id !== id)), 4500)
  }, [])

  const colors: Record<ToastVariant, string> = {
    success: 'border-green-200 bg-green-50 text-green-800 dark:border-green-900 dark:bg-green-950/80 dark:text-green-200',
    error: 'border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/80 dark:text-red-200',
    info: 'border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-900 dark:bg-blue-950/80 dark:text-blue-200',
  }

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed right-4 top-4 z-[100] flex w-96 max-w-[calc(100vw-2rem)] flex-col gap-2" aria-live="polite">
        {toasts.map(item => (
          <div key={item.id} className={`rounded-xl border px-4 py-3 text-sm shadow-lg ${colors[item.variant]}`}>
            {item.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used within ToastProvider')
  return context
}

type ConfirmOptions = { title: string; description?: string; confirmLabel?: string; variant?: 'danger' | 'primary' }
type ConfirmContextValue = { confirm: (options: ConfirmOptions) => Promise<boolean> }

const ConfirmContext = createContext<ConfirmContextValue | null>(null)

export function ConfirmProvider({ children }: PropsWithChildren) {
  const [pending, setPending] = useState<(ConfirmOptions & { resolve: (approved: boolean) => void }) | null>(null)

  const confirm = useCallback((options: ConfirmOptions) => new Promise<boolean>(resolve => {
    setPending({ ...options, resolve })
  }), [])

  const close = (approved: boolean) => {
    if (!pending) return
    pending.resolve(approved)
    setPending(null)
  }

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      {pending && (
        <div className="fixed inset-0 z-[101] flex items-center justify-center bg-black/45 p-4" role="presentation" onMouseDown={() => close(false)}>
          <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-gray-700 dark:bg-gray-900" role="dialog" aria-modal="true" aria-labelledby="confirm-title" onMouseDown={event => event.stopPropagation()}>
            <h2 id="confirm-title" className="text-base font-semibold text-gray-900 dark:text-gray-100">{pending.title}</h2>
            {pending.description && <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{pending.description}</p>}
            <div className="mt-6 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => close(false)}>Abbrechen</Button>
              <Button variant={pending.variant ?? 'primary'} onClick={() => close(true)}>{pending.confirmLabel ?? 'Bestätigen'}</Button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  )
}

export function useConfirm() {
  const context = useContext(ConfirmContext)
  if (!context) throw new Error('useConfirm must be used within ConfirmProvider')
  return context
}
