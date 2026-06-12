export type Dog = {
  id: string
  name: string
  photo_url: string | null
  breed: string
  age: number | null
  personality: string | null
  notes: string | null
  owner_name: string
  owner_id: string | null
  created_at: string
}

export type ResourceCategory = "tienda" | "clinica" | "veterinario"

export type Resource = {
  id: string
  name: string
  category: ResourceCategory
  address: string | null
  website: string | null
  phone: string | null
  description: string | null
}

export type CommunityHighlight = {
  id: string
  title: string
  image_url: string | null
  text: string
}
