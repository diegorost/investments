import { PawPrint } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { Dog } from "@/lib/types"

export function DogCard({ dog }: { dog: Dog }) {
  return (
    <Card className="overflow-hidden border-cream-dark transition-transform hover:-translate-y-1 hover:shadow-lg">
      <div className="aspect-square w-full bg-cream-dark">
        {dog.photo_url ? (
          <img
            src={dog.photo_url}
            alt={`Foto de ${dog.name}`}
            className="size-full object-cover"
          />
        ) : (
          <div className="flex size-full items-center justify-center text-sage">
            <PawPrint className="size-16" />
          </div>
        )}
      </div>
      <CardContent className="space-y-2 p-4">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-lg font-bold text-ink">{dog.name}</h3>
          {dog.age != null && (
            <span className="text-sm text-ink-light">{dog.age} años</span>
          )}
        </div>
        <Badge className="bg-sage text-white">{dog.breed}</Badge>
        {dog.personality && (
          <p className="text-sm text-ink-light">{dog.personality}</p>
        )}
        <p className="text-xs text-ink-light">Dueño/a: {dog.owner_name}</p>
      </CardContent>
    </Card>
  )
}
