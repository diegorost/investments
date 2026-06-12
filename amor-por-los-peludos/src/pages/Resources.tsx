import { useEffect, useState } from "react"
import { ShoppingBag, Stethoscope, HeartPulse } from "lucide-react"
import { ResourceCard } from "@/components/ResourceCard"
import { EmptyState } from "@/components/EmptyState"
import { supabase } from "@/lib/supabase"
import type { Resource, ResourceCategory } from "@/lib/types"

const sections: { category: ResourceCategory; title: string; icon: typeof ShoppingBag }[] = [
  { category: "tienda", title: "Tiendas Recomendadas", icon: ShoppingBag },
  { category: "clinica", title: "Clínicas de Emergencia", icon: HeartPulse },
  { category: "veterinario", title: "Veterinarios y Especialidades", icon: Stethoscope },
]

export function Resources() {
  const [resources, setResources] = useState<Resource[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    supabase
      .from("resources")
      .select("*")
      .then(({ data }) => {
        if (active) {
          setResources(data ?? [])
          setLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-bold text-ink">Recursos para tu peludo</h1>
        <p className="text-ink-light">
          Encuentra ayuda cuando la necesites: tiendas, clínicas y veterinarios
          de confianza recomendados por la comunidad.
        </p>
      </div>

      <div className="mt-8 space-y-10">
        {sections.map(({ category, title, icon: Icon }) => {
          const items = resources.filter((r) => r.category === category)
          return (
            <section key={category}>
              <div className="mb-4 flex items-center gap-2">
                <Icon className="size-6 text-sage-dark" />
                <h2 className="text-2xl font-bold text-ink">{title}</h2>
              </div>

              {loading ? (
                <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
                  {[1, 2].map((i) => (
                    <div
                      key={i}
                      className="h-32 animate-pulse rounded-card bg-cream-dark"
                    />
                  ))}
                </div>
              ) : items.length === 0 ? (
                <EmptyState
                  title="Aún no hay recomendaciones"
                  description="Pronto añadiremos opciones de confianza en esta categoría."
                />
              ) : (
                <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
                  {items.map((resource) => (
                    <ResourceCard key={resource.id} resource={resource} />
                  ))}
                </div>
              )}
            </section>
          )
        })}
      </div>
    </div>
  )
}
