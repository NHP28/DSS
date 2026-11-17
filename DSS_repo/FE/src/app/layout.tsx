import type { Metadata } from 'next';
import './globals.css';
import 'leaflet/dist/leaflet.css';

export const metadata:Metadata = {title:'Đà Nẵng Explore · Gợi ý địa điểm',description:'Khám phá Đà Nẵng theo vị trí, thời gian và ưu tiên của bạn. Hệ hỗ trợ quyết định TAS-GNN, AHP và TOPSIS.'};
export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="vi"><body>{children}</body></html>;
}
