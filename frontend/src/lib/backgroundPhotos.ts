// Generated from Wikimedia Commons metadata. See public/backgrounds/photos/CREDITS.md.
import type { PhotoCategory } from './backgroundCategories'
export type { PhotoCategory } from './backgroundCategories'

export interface BackgroundPhoto {
  id: string
  /** 1920px-wide file for 1x screens and thumbnails. */
  src: string
  /** 3840px-wide file for high-DPI / large screens. */
  src2x: string
  category: PhotoCategory
  title: string
  author: string
  license: string
  licenseUrl: string
  source: string
  position: string
  /** Height of the horizon in the photo, 0 = top, 1 = bottom (measured). Used to keep ~75% sky above it on any screen shape. */
  horizon: number
}

export const BACKGROUND_PHOTOS: BackgroundPhoto[] = [
  {"id": "fields-1", "src": "/backgrounds/photos/fields-1.jpg", "src2x": "/backgrounds/photos/fields-1@2x.jpg", "category": "fields", "title": "Open field under a cloudless sky, Virginia", "author": "Famartin", "license": "CC BY-SA 4.0", "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0", "source": "https://commons.wikimedia.org/wiki/File:2021-06-28_10_44_34_Blue_sky_over_a_field_during_a_sunny_morning_in_the_Dulles_section_of_Sterling,_Loudoun_County,_Virginia.jpg", "position": "center bottom", "horizon": 0.767},
  {"id": "fields-2", "src": "/backgrounds/photos/fields-2.jpg", "src2x": "/backgrounds/photos/fields-2@2x.jpg", "category": "fields", "title": "Walnut tree and wind turbine", "author": "Achim Lammerts (Syntaxys)", "license": "CC BY-SA 4.0", "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0", "source": "https://commons.wikimedia.org/wiki/File:2026-03-07_D500-2006_Achim-Lammerts_Juglans-regia.jpg", "position": "center bottom", "horizon": 0.755},
  {"id": "fields-3", "src": "/backgrounds/photos/fields-3.jpg", "src2x": "/backgrounds/photos/fields-3@2x.jpg", "category": "fields", "title": "Lone tree in the Shan Hills, Myanmar", "author": "Vyacheslav Argenberg", "license": "CC BY 4.0", "licenseUrl": "https://creativecommons.org/licenses/by/4.0", "source": "https://commons.wikimedia.org/wiki/File:Pangetkon,_Shan_Hills,_Myanmar,_Single_tree_in_the_field,_blue_sky,_landscape_in_remote_Myanmar.jpg", "position": "center bottom", "horizon": 0.663},
  {"id": "ocean-1", "src": "/backgrounds/photos/ocean-1.jpg", "src2x": "/backgrounds/photos/ocean-1@2x.jpg", "category": "ocean", "title": "Calm sea off Zaozerne, Crimea", "author": "sashiv", "license": "CC BY-SA 3.0", "licenseUrl": "https://creativecommons.org/licenses/by-sa/3.0", "source": "https://commons.wikimedia.org/wiki/File:Ukraine,_Krym,_Zaozerne_-_%D0%A2%D0%B5%D1%80%D1%80%D0%B8%D1%82%D0%BE%D1%80%D0%B8%D1%8F_%D0%95%D0%B2%D0%BF%D0%B0%D1%82%D0%BE%D1%80%D0%B8%D0%B9%D1%81%D0%BA%D0%BE%D0%B3%D0%BE_%D0%BC%D0%B0%D1%8F%D0%BA%D0%B0_(%D0%95%D0%B2%D0%BF%D0%B0%D1%82%D0%BE%D1%80%D0%B8%D1%8F)_WMID8955404.jpg", "position": "center bottom", "horizon": 0.79},
  {"id": "ocean-2", "src": "/backgrounds/photos/ocean-2.jpg", "src2x": "/backgrounds/photos/ocean-2@2x.jpg", "category": "ocean", "title": "Covelong Beach, India", "author": "Kritzolina", "license": "CC BY-SA 4.0", "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0", "source": "https://commons.wikimedia.org/wiki/File:Clouds_over_a_Covelong_Beach_07.jpg", "position": "center bottom", "horizon": 0.736},
  {"id": "lakes-1", "src": "/backgrounds/photos/lakes-1.jpg", "src2x": "/backgrounds/photos/lakes-1@2x.jpg", "category": "lakes", "title": "Lake Geneva seen from Chillon", "author": "Glorandal", "license": "CC BY-SA 4.0", "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0", "source": "https://commons.wikimedia.org/wiki/File:Lake_Geneva_seen_from_Chillon.jpg", "position": "center bottom", "horizon": 0.82},
  {"id": "mountains-1", "src": "/backgrounds/photos/mountains-1.jpg", "src2x": "/backgrounds/photos/mountains-1@2x.jpg", "category": "mountains", "title": "Beenoskee, Dingle Peninsula, Ireland", "author": "Maoileann", "license": "CC BY-SA 4.0", "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0", "source": "https://commons.wikimedia.org/wiki/File:Beenoskee-3343,_Dingle_Peninsula,_Co._Kerry,_Ireland.jpg", "position": "center bottom", "horizon": 0.84},
  {"id": "mountains-2", "src": "/backgrounds/photos/mountains-2.jpg", "src2x": "/backgrounds/photos/mountains-2@2x.jpg", "category": "mountains", "title": "Laugarvalladalur highlands, Iceland", "author": "Rémih", "license": "CC BY-SA 4.0", "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0", "source": "https://commons.wikimedia.org/wiki/File:Laugarvalladalur_@_Sk%C3%B3gah%C3%A1ls.jpg", "position": "center bottom", "horizon": 0.658},
  {"id": "desert-1", "src": "/backgrounds/photos/desert-1.jpg", "src2x": "/backgrounds/photos/desert-1@2x.jpg", "category": "desert", "title": "Vikursandur lava desert, Iceland", "author": "Rémih", "license": "CC BY-SA 4.0", "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0", "source": "https://commons.wikimedia.org/wiki/File:Va%C3%B0alda_@_Vikursandur.jpg", "position": "center bottom", "horizon": 0.633},
  {"id": "desert-2", "src": "/backgrounds/photos/desert-2.jpg", "src2x": "/backgrounds/photos/desert-2@2x.jpg", "category": "desert", "title": "Fitjahnjúkur, Icelandic highlands", "author": "Rémih", "license": "CC BY-SA 4.0", "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0", "source": "https://commons.wikimedia.org/wiki/File:Fitjahnj%C3%BAkur_@_Langihnj%C3%BAkur.jpg", "position": "center bottom", "horizon": 0.583},
  {"id": "city-1", "src": "/backgrounds/photos/city-1.jpg", "src2x": "/backgrounds/photos/city-1@2x.jpg", "category": "city", "title": "Beitou skyline, Taipei", "author": "迷惘的人生", "license": "CC BY-SA 2.0", "licenseUrl": "https://creativecommons.org/licenses/by-sa/2.0", "source": "https://commons.wikimedia.org/wiki/File:Beitou,_Taipei_Skyline_20230517.jpg", "position": "center bottom", "horizon": 0.774},
  {"id": "city-2", "src": "/backgrounds/photos/city-2.jpg", "src2x": "/backgrounds/photos/city-2@2x.jpg", "category": "city", "title": "Las Vegas from the STRAT", "author": "Robert Conforti", "license": "CC BY 4.0", "licenseUrl": "https://creativecommons.org/licenses/by/4.0", "source": "https://commons.wikimedia.org/wiki/File:Las_Vegas_Strip_Skyline_Panoramic_View_The_STRAT_Hotel_Observation_Deck.jpg", "position": "center bottom", "horizon": 0.683},
]
