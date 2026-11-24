'use client';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useRef } from 'react';
import { BarChart3, ChevronDown, Compass, Database, Heart, Home, LayoutGrid, LogIn, LogOut, Network, Settings2 } from 'lucide-react';
import { useAuth } from './auth-context';

const main = [
  { href: '/', label: 'Trang chủ', icon: Home },
  { href: '/explore', label: 'Khám phá', icon: Compass },
  { href: '/themes/an-uong', match: '/themes', label: 'Chủ đề', icon: LayoutGrid },
  { href: '/saved', label: 'Đã lưu', icon: Heart },
];
const research = [
  { href: '/model', label: 'Mô hình TAS-GNN', icon: Network },
  { href: '/evaluation', label: 'Đánh giá & so sánh', icon: BarChart3 },
  { href: '/data', label: 'Dữ liệu & đồ thị tri thức', icon: Database },
];

export default function SiteHeader() {
  const pathname = usePathname(), router = useRouter();
  const { account, loading, logout } = useAuth();
  const menus = useRef<HTMLElement>(null);
  const current = (item: { href: string; match?: string }) => (item.match ? pathname.startsWith(item.match) : pathname === item.href) ? 'page' as const : undefined;
  // Close open dropdowns after navigating.
  useEffect(() => { menus.current?.querySelectorAll('details[open]').forEach(node => node.removeAttribute('open')); }, [pathname]);
  return <>
    <header className="site-header">
      <div className="wrap">
        <Link href="/" className="brand"><span className="brand-mark"><Compass size={21} /></span><span>Đà Nẵng <i>Explore</i></span></Link>
        <nav className="nav" aria-label="Điều hướng chính" ref={menus}>
          {main.map(item => <Link key={item.href} href={item.href} aria-current={current(item)}>{item.label}</Link>)}
          <details className="menu">
            <summary aria-current={research.some(item => pathname === item.href) ? 'page' : undefined}>Nghiên cứu <ChevronDown size={15} /></summary>
            <div className="menu-panel">{research.map(item => <Link key={item.href} href={item.href}><item.icon size={17} />{item.label}</Link>)}</div>
          </details>
          {loading ? <span className="skeleton" style={{ width: 96, height: 38, borderRadius: 999 }} /> : account ? <details className="menu">
            <summary aria-label={`Tài khoản ${account.displayName}`}><span className="avatar">{account.displayName.trim().charAt(0).toUpperCase()}</span><ChevronDown size={15} /></summary>
            <div className="menu-panel">
              <small>{account.displayName}<br />@{account.username}{account.datasetUserId !== null && ' · tài khoản demo'}</small>
              <Link href="/saved"><Heart size={17} />Địa điểm đã lưu</Link>
              <Link href="/settings"><Settings2 size={17} />Cài đặt mô hình</Link>
              <button onClick={async () => { await logout(); router.push('/'); }}><LogOut size={17} />Đăng xuất</button>
            </div>
          </details> : <Link href="/login" className="btn sm" style={{ color: 'var(--paper)', marginLeft: '.4rem' }}><LogIn size={16} />Đăng nhập</Link>}
        </nav>
      </div>
    </header>
    <nav className="mobile-nav" aria-label="Điều hướng nhanh">
      {main.map(item => <Link key={item.href} href={item.href} aria-current={current(item)}><item.icon size={20} />{item.label}</Link>)}
      <Link href={account ? '/settings' : '/login'} aria-current={pathname === '/settings' || pathname === '/login' ? 'page' : undefined}>{account ? <Settings2 size={20} /> : <LogIn size={20} />}{account ? 'Cài đặt' : 'Đăng nhập'}</Link>
    </nav>
  </>;
}
