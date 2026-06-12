import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { PawPrint, Search, HeartHandshake } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { supabase } from "@/lib/supabase"
import type { CommunityHighlight } from "@/lib/types"

export function Home() {
  const [highlights, setHighlights] = useState<CommunityHighlight[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    supabase
      .from("community_highlights")
      .select("*")
      .limit(3)
      .then(({ data }) => {
        if (active) {
          setHighlights(data ?? [])
          setLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <div>
      <section className="mx-auto flex max-w-5xl flex-col items-center gap-8 px-4 py-12 text-center md:py-20">
        <div
          className="flex size-40 items-center justify-center rounded-full bg-gradient-to-br from-gold/40 via-sage/30 to-sky/30 text-7xl shadow-lg md:size-56 md:text-8xl"
          role="img"
          aria-label="Perros felices en un parque al atardecer"
        >
          🐶🐾
        </div>
        <div className="space-y-3">
          <h1 className="text-3xl font-bold text-ink md:text-5xl">
            Presenta a tu mejor amigo
          </h1>
          <p className="mx-auto max-w-xl text-ink-light md:text-lg">
            Una comunidad cálida para dueños de perros, especialmente Golden
            Retrievers, donde compartir el perfil de tu peludo y descubrir
            recursos de confianza cerca de ti.
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Button asChild size="lg" className="bg-gold text-ink hover:bg-gold-dark">
            <Link to="/perritos">
              <Search className="mr-1" /> Explora nuestra comunidad
            </Link>
          </Button>
          <Button
            asChild
            size="lg"
            variant="outline"
            className="border-sage text-sage-dark hover:bg-sage/10"
          >
            <Link to="/anadir">
              <PawPrint className="mr-1" /> Añadir perro
            </Link>
          </Button>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 py-10">
        <div className="flex items-center gap-2">
          <HeartHandshake className="size-6 text-sage-dark" />
          <h2 className="text-2xl font-bold text-ink">
            Destacados de la comunidad
          </h2>
        </div>

        {loading ? (
          <div className="mt-6 grid gap-4 sm:grid-cols-2 md:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-48 animate-pulse rounded-card bg-cream-dark"
              />
            ))}
          </div>
        ) : highlights.length === 0 ? (
          <div className="mt-6 rounded-card border border-dashed border-cream-dark bg-white/60 p-8 text-center text-ink-light">
            Pronto compartiremos historias y momentos especiales de la
            comunidad. ¡Vuelve más tarde!
          </div>
        ) : (
          <div className="mt-6 grid gap-4 sm:grid-cols-2 md:grid-cols-3">
            {highlights.map((h) => (
              <Card key={h.id} className="overflow-hidden border-cream-dark">
                {h.image_url && (
                  <img
                    src={h.image_url}
                    alt={h.title}
                    className="aspect-video w-full object-cover"
                  />
                )}
                <CardContent className="space-y-1 p-4">
                  <h3 className="font-bold text-ink">{h.title}</h3>
                  <p className="text-sm text-ink-light">{h.text}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section className="mx-auto max-w-5xl px-4 py-10">
        <Card className="border-cream-dark bg-sky/20">
          <CardContent className="flex flex-col items-center gap-3 p-8 text-center">
            <h2 className="text-2xl font-bold text-ink">
              Encuentra ayuda cuando la necesites
            </h2>
            <p className="max-w-md text-ink-light">
              Tiendas recomendadas, clínicas de emergencia y veterinarios de
              confianza, todo en un solo lugar.
            </p>
            <Button asChild className="bg-sky-dark text-white hover:bg-sky-dark/90">
              <Link to="/recursos">Ver recursos</Link>
            </Button>
          </CardContent>
        </Card>
      </section>
    </div>
  )
}
