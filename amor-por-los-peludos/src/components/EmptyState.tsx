import type { ReactNode } from "react"
import { PawPrint } from "lucide-react"

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-card border border-dashed border-cream-dark bg-white/60 px-6 py-12 text-center">
      <span className="flex size-14 items-center justify-center rounded-full bg-gold/30 text-gold-dark">
        <PawPrint className="size-7" />
      </span>
      <h3 className="text-lg font-bold text-ink">{title}</h3>
      <p className="max-w-sm text-sm text-ink-light">{description}</p>
      {action}
    </div>
  )
}
