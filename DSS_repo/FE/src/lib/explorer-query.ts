export type ExplorerForm = {
  userId: string;
  latitude: number;
  longitude: number;
  hour: number;
  dayOfWeek: number;
  radiusKm: number;
  maxPrice: string;
  category: string;
  preset: string;
  excludeVisited: boolean;
  customWeights: boolean;
  weightLevels: number[];
};

export const defaultForm: ExplorerForm = {
  userId: '', latitude: 16.0678, longitude: 108.2208, hour: 8, dayOfWeek: 0,
  radiusKm: 10, maxPrice: '', category: '', preset: 'balanced', excludeVisited: true,
  customWeights: false, weightLevels: [5, 4, 3, 6, 2],
};

export const criteria = [
  { label: 'Khoảng cách', hint: 'Ưu tiên nơi gần hơn' },
  { label: 'Đánh giá', hint: 'Ưu tiên rating cao hơn' },
  { label: 'Chi phí', hint: 'Ưu tiên giá thấp hơn' },
  { label: 'Hợp sở thích', hint: 'Ưu tiên điểm từ mô hình' },
  { label: 'Phổ biến', hint: 'Ưu tiên nơi được quan tâm' },
];

export function priorityMatrix(levels: number[]): number[][] {
  if (levels.length !== 5 || levels.some(value => !Number.isFinite(value) || value < 1 || value > 9)) {
    throw new Error('Mỗi mức ưu tiên cần nằm trong khoảng 1–9.');
  }
  // Ratios of positive priorities form a reciprocal, consistent AHP matrix.
  // Levels 1–9 keep every ratio inside the API's supported [1/9, 9] range.
  return levels.map(a => levels.map(b => a / b));
}

export function recommendationQuery(form: ExplorerForm) {
  return {
    latitude: form.latitude, longitude: form.longitude,
    hour: form.hour, dayOfWeek: form.dayOfWeek, radiusKm: form.radiusKm,
    preset: form.preset, excludeVisited: form.excludeVisited, topK: 10,
    ...(form.userId !== '' ? { userId: Number(form.userId) } : {}),
    ...(form.category ? { category: form.category } : {}),
    ...(form.maxPrice !== '' ? { maxPrice: Number(form.maxPrice) } : {}),
    ...(form.customWeights ? { matrix: priorityMatrix(form.weightLevels) } : {}),
  };
}

export function sameQuery(a: ExplorerForm, b: ExplorerForm): boolean {
  return JSON.stringify(recommendationQuery(a)) === JSON.stringify(recommendationQuery(b));
}

export function searchText(value: string): string {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[đĐ]/g, 'd').toLowerCase();
}
