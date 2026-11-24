// Presentation-only helpers. The CSV catalog is never edited: model artifacts check its hash.
const DISTRICTS: Record<string, string> = {
  'hai chau': 'Hải Châu', 'son tra': 'Sơn Trà', 'ngu hanh son': 'Ngũ Hành Sơn', 'lien chieu': 'Liên Chiểu',
  'thanh khe': 'Thanh Khê', 'hoa vang': 'Hòa Vang', 'cam le': 'Cẩm Lệ',
  // One POI is tagged with the city name only; it sits in the centre.
  'danang': 'Hải Châu', 'da nang': 'Hải Châu',
};
const plain = (value: string) => value.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[đĐ]/g, 'd').toLowerCase().trim();

export function normalizeDistrict(raw: string): string {
  const key = plain(raw).replace(/^quan\s+/, '');
  return DISTRICTS[key] || raw.replace(/^quận\s+/i, '').trim();
}

// OpenStreetMap contributors tagged many trail notes as tourist spots ("End of the Road?").
const NOTE_WORDS = /\b(view|views|viewpoint|path|road|option|dead end|ends here|trekking)\b/i;
export function isJunkPoiName(name: string, category: string): boolean {
  if (category !== 'tourist_spot') return false;
  const value = name.trim();
  return /[?!]/.test(value) || NOTE_WORDS.test(value) || /^[a-z]/.test(value) || value.length > 45;
}
