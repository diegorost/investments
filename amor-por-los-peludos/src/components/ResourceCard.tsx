import { MapPin, Phone, Globe } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import type { Resource } from "@/lib/types"

export function ResourceCard({ resource }: { resource: Resource }) {
  return (
    <Card className="border-cream-dark">
      <CardContent className="space-y-2 p-4">
        <h3 className="text-base font-bold text-ink">{resource.name}</h3>
        {resource.description && (
          <p className="text-sm text-ink-light">{resource.description}</p>
        )}
        <div className="space-y-1 text-sm text-ink-light">
          {resource.address && (
            <p className="flex items-center gap-2">
              <MapPin className="size-4 text-sage-dark" />
              {resource.address}
            </p>
          )}
          {resource.phone && (
            <p className="flex items-center gap-2">
              <Phone className="size-4 text-sage-dark" />
              {resource.phone}
            </p>
          )}
          {resource.website && (
            <a
              href={resource.website}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 text-sky-dark hover:underline"
            >
              <Globe className="size-4" />
              Sitio web
            </a>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
