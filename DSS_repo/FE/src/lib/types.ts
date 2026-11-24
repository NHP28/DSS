export interface Place {
  id: number; name: string; category: string; district: string; latitude: number; longitude: number;
  rating: number; price_avg: number; popularity: number; distanceKm: number; preference: number;
  topsisScore: number; rank: number; explanation: string; saved?: boolean; visited?: boolean;
}
export interface Recommendation {
  source: string; warning: string | null; model: string; useTime: boolean; models: string[];
  personalization: 'trained_user' | 'foldin' | 'cold_start'; historyCount: number; minHistory: number;
  artifact?: { runId?: string; trainedUsers?: number; pois?: number } | null;
  weights: number[]; consistencyRatio: number;
  groups: { category: string; total: number; items: Place[] }[]; totalCandidates: number; elapsedMs: number;
  query: { hour: number; dayOfWeek: number; latitude: number; longitude: number; radiusKm: number; maxPrice: number | null; topK: number; candidatePool: number };
  theme?: Theme;
}
export interface Theme {
  slug: string; title: string; tagline: string; symbol: string; categories: string[]; count?: number;
  hour: number | 'now'; preset: string; note?: string;
}
export interface Account { id: number; username: string; displayName: string; datasetUserId: number | null; interests: string[] }
export interface ModelSettings {
  model: 'tas_gnn' | 'lightgcn' | 'hourly_popularity' | 'popularity'; useTime: boolean; candidatePool: number; topK: number;
  excludeVisited: boolean; radiusKm: number; maxPrice: number | null;
  preset: 'balanced' | 'proximity' | 'budget' | 'ai_centric' | 'custom'; weightLevels: number[];
}
export interface SystemStatus {
  database: boolean; graph: boolean; places?: boolean;
  ai: { ready: boolean; models?: string[]; origin?: string; info?: { embeddingDim?: number; timeDim?: number; layers?: number; parameters?: number; lightgcnParameters?: number; users?: number; pois?: number; trainEvents?: number; blocks?: Record<string, number> } };
}

export const categories: Record<string, { label: string; symbol: string }> = {
  cafe: { label: 'Cà phê', symbol: '☕' },
  restaurant: { label: 'Ăn uống', symbol: '🍜' },
  tourist_spot: { label: 'Tham quan & giải trí', symbol: '🏞️' },
  hotel: { label: 'Lưu trú', symbol: '🏨' },
};
export const categoryOrder = ['restaurant', 'cafe', 'tourist_spot', 'hotel'];
export const weekdays = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ nhật'];
export const presets: Record<string, string> = { balanced: 'Cân bằng', proximity: 'Gần tôi nhất', budget: 'Tiết kiệm', ai_centric: 'Hợp sở thích', custom: 'Tự chỉnh' };
export const criteria = ['Khoảng cách', 'Đánh giá', 'Chi phí', 'Hợp sở thích', 'Phổ biến'];
export const modelNames: Record<string, string> = {
  tas_gnn: 'TAS-GNN', lightgcn: 'LightGCN', hourly_popularity: 'Phổ biến theo giờ', popularity: 'Phổ biến chung',
  tas_gnn_foldin: 'TAS-GNN', lightgcn_foldin: 'LightGCN',
};
export const DANANG = { latitude: 16.0678, longitude: 108.2208 };

export const money = (value: number) => value > 0 ? `${new Intl.NumberFormat('vi-VN').format(Math.round(value))} đ` : 'Miễn phí';
export const count = (value: number) => new Intl.NumberFormat('vi-VN').format(value);
export const percent = (value: number, digits = 2) => `${(value * 100).toFixed(digits).replace('.', ',')}%`;
export const dayPart = (hour: number) => hour < 5 ? 'đêm khuya' : hour < 11 ? 'buổi sáng' : hour < 14 ? 'buổi trưa' : hour < 18 ? 'buổi chiều' : hour < 23 ? 'buổi tối' : 'đêm khuya';
/** Current hour and weekday (Monday = 0) in Đà Nẵng, whatever the browser's timezone is. */
export function vietnamNow() {
  const now = new Date(Date.now() + 7 * 3600 * 1000);
  return { hour: now.getUTCHours(), dayOfWeek: (now.getUTCDay() + 6) % 7 };
}
