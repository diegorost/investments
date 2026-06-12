import { Link, NavLink, Outlet } from "react-router-dom"
import { PawPrint, Menu, X } from "lucide-react"
import { useState } from "react"
import { cn } from "@/lib/utils"

const navItems = [
  { to: "/", label: "Inicio" },
  { to: "/perritos", label: "Perritos" },
  { to: "/anadir", label: "Añadir Perro" },
  { to: "/recursos", label: "Recursos" },
]

export function Layout() {
  const [open, setOpen] = useState(false)

  return (
    <div className="flex min-h-screen flex-col bg-cream">
      <header className="sticky top-0 z-50 border-b border-cream-dark bg-cream/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2 font-bold text-ink">
            <span className="flex size-9 items-center justify-center rounded-full bg-gold text-ink">
              <PawPrint className="size-5" />
            </span>
            <span className="text-lg">Amor por los Peludos</span>
          </Link>

          <nav className="hidden items-center gap-1 md:flex">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "rounded-full px-4 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-gold text-ink"
                      : "text-ink-light hover:bg-cream-dark hover:text-ink"
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <button
            type="button"
            className="flex size-9 items-center justify-center rounded-full text-ink md:hidden"
            aria-label="Abrir menú"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>

        {open && (
          <nav className="flex flex-col gap-1 border-t border-cream-dark px-4 py-3 md:hidden">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "rounded-full px-4 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-gold text-ink"
                      : "text-ink-light hover:bg-cream-dark hover:text-ink"
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        )}
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-cream-dark py-6 text-center text-sm text-ink-light">
        <p>
          Hecho con <span aria-hidden>🐾</span> para la comunidad de amantes de perros.
        </p>
      </footer>
    </div>
  )
}
