export type PhotoCategory = 'city' | 'mountains' | 'ocean' | 'desert' | 'fields' | 'lakes'

export const PHOTO_CATEGORIES: { value: PhotoCategory; label: string }[] = [
  { value: 'city', label: 'City skyline' },
  { value: 'mountains', label: 'Mountains' },
  { value: 'ocean', label: 'Ocean & beach' },
  { value: 'desert', label: 'Desert' },
  { value: 'fields', label: 'Fields & countryside' },
  { value: 'lakes', label: 'Lakes' },
]
