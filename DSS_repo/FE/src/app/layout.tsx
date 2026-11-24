import type { Metadata } from 'next';
import Link from 'next/link';
import { Be_Vietnam_Pro, Fraunces } from 'next/font/google';
import './globals.css';
import 'leaflet/dist/leaflet.css';
import { AuthProvider } from '@/components/auth-context';
import SiteHeader from '@/components/site-header';

const display = Fraunces({ subsets: ['latin', 'vietnamese'], variable: '--font-display', display: 'swap' });
const body = Be_Vietnam_Pro({ subsets: ['latin', 'vietnamese'], weight: ['400', '500', '600', '700'], variable: '--font-body', display: 'swap' });

export const metadata: Metadata = {
  title: { default: 'Đà Nẵng Explore · Gợi ý địa điểm theo thời gian', template: '%s · Đà Nẵng Explore' },
  description: 'Gợi ý địa điểm ăn uống, cà phê, tham quan và lưu trú tại Đà Nẵng bằng mạng nơ-ron đồ thị tích hợp thời gian (TAS-GNN) kết hợp AHP–TOPSIS.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="vi" className={`${display.variable} ${body.variable}`}><body>
    <AuthProvider>
      <SiteHeader />
      {children}
      <footer className="site-footer"><div className="wrap row between">
        <span>Đồ án: Ứng dụng mạng nơ-ron đồ thị động tích hợp thông tin thời gian trong hệ thống gợi ý địa điểm cá nhân hóa.</span>
        <span>Địa điểm từ OpenStreetMap · check-in, giá, đánh giá là dữ liệu mô phỏng · <Link className="link" href="/data">Xem dữ liệu</Link></span>
      </div></footer>
    </AuthProvider>
  </body></html>;
}
