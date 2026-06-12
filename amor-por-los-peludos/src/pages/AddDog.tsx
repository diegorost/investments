import { useState, type FormEvent } from "react"
import { Link } from "react-router-dom"
import { CheckCircle2, LogIn, PawPrint } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent } from "@/components/ui/card"
import { supabase } from "@/lib/supabase"
import { useSession } from "@/hooks/useSession"

type FormState = {
  name: string
  breed: string
  age: string
  personality: string
  notes: string
  owner_name: string
}

const initialState: FormState = {
  name: "",
  breed: "",
  age: "",
  personality: "",
  notes: "",
  owner_name: "",
}

export function AddDog() {
  const { session, loading } = useSession()
  const [form, setForm] = useState<FormState>(initialState)
  const [errors, setErrors] = useState<Partial<FormState>>({})
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [email, setEmail] = useState("")
  const [magicLinkSent, setMagicLinkSent] = useState(false)

  const handleChange = (field: keyof FormState, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const validate = () => {
    const next: Partial<FormState> = {}
    if (!form.name.trim()) next.name = "Cuéntanos el nombre de tu perro."
    if (!form.breed.trim()) next.breed = "Indica la raza de tu perro."
    if (!form.owner_name.trim()) next.owner_name = "Indica tu nombre."
    if (form.age && (Number(form.age) < 0 || Number(form.age) > 30)) {
      next.age = "Ingresa una edad válida."
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!validate()) return

    setSubmitting(true)
    const { error } = await supabase.from("dogs").insert({
      name: form.name.trim(),
      breed: form.breed.trim(),
      age: form.age ? Number(form.age) : null,
      personality: form.personality.trim() || null,
      notes: form.notes.trim() || null,
      owner_name: form.owner_name.trim(),
      owner_id: session?.user.id ?? null,
    })
    setSubmitting(false)

    if (!error) {
      setSuccess(true)
      setForm(initialState)
    }
  }

  const handleMagicLink = async (e: FormEvent) => {
    e.preventDefault()
    if (!email.trim()) return
    await supabase.auth.signInWithOtp({ email: email.trim() })
    setMagicLinkSent(true)
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center text-ink-light">
        Cargando...
      </div>
    )
  }

  if (!session) {
    return (
      <div className="mx-auto max-w-md px-4 py-16">
        <Card className="border-cream-dark">
          <CardContent className="space-y-4 p-6 text-center">
            <span className="mx-auto flex size-12 items-center justify-center rounded-full bg-sky/30 text-sky-dark">
              <LogIn className="size-6" />
            </span>
            <h1 className="text-2xl font-bold text-ink">Inicia sesión</h1>
            <p className="text-ink-light">
              Para añadir el perfil de tu perro, primero inicia sesión con tu
              correo. Te enviaremos un enlace mágico.
            </p>
            {magicLinkSent ? (
              <p className="rounded-card bg-sage/20 p-3 text-sage-dark">
                Revisa tu correo y haz clic en el enlace para continuar.
              </p>
            ) : (
              <form onSubmit={handleMagicLink} className="space-y-3">
                <Input
                  type="email"
                  required
                  placeholder="tu@correo.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="border-cream-dark"
                />
                <Button type="submit" className="w-full bg-gold text-ink hover:bg-gold-dark">
                  Enviar enlace mágico
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  if (success) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center">
        <span className="mx-auto flex size-14 items-center justify-center rounded-full bg-sage/20 text-sage-dark">
          <CheckCircle2 className="size-8" />
        </span>
        <h1 className="mt-4 text-2xl font-bold text-ink">
          ¡Tu perro fue añadido con éxito!
        </h1>
        <p className="mt-2 text-ink-light">
          Gracias por presentar a tu mejor amigo a la comunidad.
        </p>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Button asChild className="bg-gold text-ink hover:bg-gold-dark">
            <Link to="/perritos">Ver comunidad</Link>
          </Button>
          <Button variant="outline" onClick={() => setSuccess(false)}>
            Añadir otro perro
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <div className="space-y-2 text-center">
        <span className="mx-auto flex size-12 items-center justify-center rounded-full bg-gold/30 text-gold-dark">
          <PawPrint className="size-6" />
        </span>
        <h1 className="text-3xl font-bold text-ink">Añadir perro</h1>
        <p className="text-ink-light">
          Cuéntanos sobre tu peludo para presentarlo a la comunidad.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="mt-8 space-y-5">
        <div className="space-y-1.5">
          <Label htmlFor="name">Nombre del perro</Label>
          <Input
            id="name"
            value={form.name}
            onChange={(e) => handleChange("name", e.target.value)}
            className="border-cream-dark"
          />
          {errors.name && <p className="text-sm text-destructive">{errors.name}</p>}
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="breed">Raza</Label>
            <Input
              id="breed"
              value={form.breed}
              onChange={(e) => handleChange("breed", e.target.value)}
              className="border-cream-dark"
              placeholder="Golden Retriever"
            />
            {errors.breed && <p className="text-sm text-destructive">{errors.breed}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="age">Edad (años)</Label>
            <Input
              id="age"
              type="number"
              min={0}
              max={30}
              value={form.age}
              onChange={(e) => handleChange("age", e.target.value)}
              className="border-cream-dark"
            />
            {errors.age && <p className="text-sm text-destructive">{errors.age}</p>}
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="personality">Personalidad</Label>
          <Input
            id="personality"
            value={form.personality}
            onChange={(e) => handleChange("personality", e.target.value)}
            className="border-cream-dark"
            placeholder="Juguetón, cariñoso, tranquilo..."
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="notes">Notas</Label>
          <Textarea
            id="notes"
            value={form.notes}
            onChange={(e) => handleChange("notes", e.target.value)}
            className="border-cream-dark"
            placeholder="Cuéntanos algo especial sobre tu perro..."
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="owner_name">Tu nombre</Label>
          <Input
            id="owner_name"
            value={form.owner_name}
            onChange={(e) => handleChange("owner_name", e.target.value)}
            className="border-cream-dark"
          />
          {errors.owner_name && (
            <p className="text-sm text-destructive">{errors.owner_name}</p>
          )}
        </div>

        <Button
          type="submit"
          disabled={submitting}
          className="w-full bg-gold text-ink hover:bg-gold-dark"
        >
          {submitting ? "Guardando..." : "Añadir perro"}
        </Button>
      </form>
    </div>
  )
}
