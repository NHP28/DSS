export interface Theme {
  slug: string; title: string; tagline: string; symbol: string;
  categories: string[];
  districts?: string[];
  maxPrice?: number;
  /** Keep only the cheapest share of each category (0–1). */
  cheapestShare?: number;
  hour: number | 'now';
  preset: 'balanced' | 'proximity' | 'budget' | 'ai_centric';
  note?: string;
}

export const ALL_CATEGORIES = ['cafe', 'restaurant', 'hotel', 'tourist_spot'];

export const THEMES: Theme[] = [
  { slug: 'an-uong', title: 'Ăn uống', tagline: 'Quán ăn, nhà hàng hợp giờ và hợp túi tiền', symbol: '🍜', categories: ['restaurant'], hour: 'now', preset: 'balanced' },
  { slug: 'ca-phe', title: 'Cà phê', tagline: 'Một chỗ ngồi gần bạn, đúng lúc cần', symbol: '☕', categories: ['cafe'], hour: 'now', preset: 'proximity' },
  { slug: 'tham-quan-giai-tri', title: 'Tham quan & giải trí', tagline: 'Cảnh đẹp, điểm vui chơi và khám phá', symbol: '🏞️', categories: ['tourist_spot'], hour: 16, preset: 'ai_centric',
    note: 'Dữ liệu OpenStreetMap chỉ có một nhãn chung cho điểm tham quan và giải trí.' },
  { slug: 'luu-tru', title: 'Lưu trú', tagline: 'Khách sạn theo vị trí, giá và đánh giá', symbol: '🏨', categories: ['hotel'], hour: 14, preset: 'budget',
    note: 'Khách sạn chưa có lượt check-in huấn luyện, nên thứ hạng dựa vào khoảng cách, giá và đánh giá.' },
  { slug: 'bua-sang', title: 'Bữa sáng Đà Nẵng', tagline: 'Ăn sáng và cà phê sớm dưới 60.000 đ', symbol: '🌅', categories: ['cafe', 'restaurant'], maxPrice: 60000, hour: 7, preset: 'proximity' },
  { slug: 've-dem', title: 'Đà Nẵng về đêm', tagline: 'Ăn tối, cà phê khuya và dạo phố', symbol: '🌙', categories: ['restaurant', 'cafe', 'tourist_spot'], hour: 20, preset: 'ai_centric' },
  { slug: 'ven-bien', title: 'Ven biển', tagline: 'Sơn Trà và Ngũ Hành Sơn, sát bãi biển', symbol: '🏖️', categories: ALL_CATEGORIES, districts: ['Sơn Trà', 'Ngũ Hành Sơn'], hour: 'now', preset: 'balanced' },
  { slug: 'tiet-kiem', title: 'Tiết kiệm', tagline: 'Nhóm giá thấp nhất của từng danh mục', symbol: '💸', categories: ALL_CATEGORIES, cheapestShare: 0.35, hour: 'now', preset: 'budget' },
];

export const themeBySlug = (slug: string) => THEMES.find(theme => theme.slug === slug);
