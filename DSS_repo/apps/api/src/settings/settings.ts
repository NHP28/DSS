export const MODELS = ['tas_gnn', 'lightgcn', 'hourly_popularity', 'popularity'] as const;
export const PRESET_KEYS = ['balanced', 'proximity', 'budget', 'ai_centric', 'custom'] as const;
export const CANDIDATE_POOLS = [0, 20, 50, 100] as const;

export interface ModelSettings {
  model: typeof MODELS[number];
  useTime: boolean;
  /** GNN candidates kept per category before TOPSIS; 0 keeps all. */
  candidatePool: number;
  topK: number;
  excludeVisited: boolean;
  radiusKm: number;
  maxPrice: number | null;
  preset: typeof PRESET_KEYS[number];
  weightLevels: number[];
}

export const DEFAULT_SETTINGS: ModelSettings = {
  model: 'tas_gnn', useTime: true, candidatePool: 0, topK: 10, excludeVisited: true,
  radiusKm: 10, maxPrice: null, preset: 'balanced', weightLevels: [5, 4, 3, 6, 2],
};

/** Returns a clean settings object or throws an Error naming the first invalid field. */
export function parseSettings(input: unknown): ModelSettings {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('Cài đặt không hợp lệ');
  const raw = input as Record<string, unknown>;
  const unknown = Object.keys(raw).filter(key => !(key in DEFAULT_SETTINGS));
  if (unknown.length) throw new Error(`Cài đặt không hỗ trợ: ${unknown.join(', ')}`);
  const value = { ...DEFAULT_SETTINGS, ...raw } as ModelSettings;
  const fail = (field: string) => { throw new Error(`Giá trị ${field} không hợp lệ`); };
  if (!MODELS.includes(value.model)) fail('model');
  if (typeof value.useTime !== 'boolean') fail('useTime');
  if (!(CANDIDATE_POOLS as readonly number[]).includes(value.candidatePool)) fail('candidatePool');
  if (!Number.isInteger(value.topK) || value.topK < 5 || value.topK > 20) fail('topK');
  if (typeof value.excludeVisited !== 'boolean') fail('excludeVisited');
  if (typeof value.radiusKm !== 'number' || !(value.radiusKm >= 0.5 && value.radiusKm <= 50)) fail('radiusKm');
  if (value.maxPrice !== null && (typeof value.maxPrice !== 'number' || !(value.maxPrice >= 0 && value.maxPrice <= 100000000))) fail('maxPrice');
  if (!PRESET_KEYS.includes(value.preset)) fail('preset');
  if (!Array.isArray(value.weightLevels) || value.weightLevels.length !== 5
    || value.weightLevels.some(level => !Number.isInteger(level) || level < 1 || level > 9)) fail('weightLevels');
  return { ...value, weightLevels: [...value.weightLevels] };
}
