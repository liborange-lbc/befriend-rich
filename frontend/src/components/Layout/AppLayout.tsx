import {
  AlertOutlined,
  AppstoreOutlined,
  BankOutlined,
  BarChartOutlined,
  DashboardOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  FundOutlined,
  SettingOutlined,
  SmileOutlined,
} from '@ant-design/icons';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import '../../App.css';
import Assistant from '../Assistant';
import AssistantDrawer from '../AssistantDrawer';

type AppMode = 'asset' | 'market';

const assetMenuItems = [
  { key: '/portfolio', icon: <FundOutlined />, label: '资金大盘' },
  { key: '/asset-records', icon: <FileTextOutlined />, label: '资产记录' },
  { key: '/funds', icon: <BankOutlined />, label: '资产标的' },
  { key: '/classification', icon: <AppstoreOutlined />, label: '标的分类' },
];

const marketMenuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '大盘看板' },
  { key: '/analysis', icon: <BarChartOutlined />, label: '基金分析' },
  { key: '/backtest', icon: <ExperimentOutlined />, label: '回测' },
  { key: '/strategy', icon: <AlertOutlined />, label: '策略管理' },
];

const assetPaths = new Set(assetMenuItems.map((i) => i.key));
const marketPaths = new Set(marketMenuItems.map((i) => i.key));

function detectMode(pathname: string): AppMode {
  if (assetPaths.has(pathname)) return 'asset';
  if (marketPaths.has(pathname)) return 'market';
  for (const p of assetPaths) { if (pathname.startsWith(p)) return 'asset'; }
  for (const p of marketPaths) { if (pathname.startsWith(p)) return 'market'; }
  return 'market';
}

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState<AppMode>(() => detectMode(location.pathname));
  const [navKey, setNavKey] = useState(0);
  const [isFlipping, setIsFlipping] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const flipTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (location.pathname !== '/settings') {
      setMode(detectMode(location.pathname));
    }
  }, [location.pathname]);

  const menuItems = mode === 'asset' ? assetMenuItems : marketMenuItems;
  const isActive = (key: string) => location.pathname === key || location.pathname.startsWith(key + '/');

  const handleLogoClick = useCallback(() => {
    if (isFlipping) return;
    setIsFlipping(true);
    if (flipTimer.current) clearTimeout(flipTimer.current);

    // Switch mode at animation midpoint (character swap happens during flip)
    flipTimer.current = setTimeout(() => {
      const newMode = mode === 'market' ? 'asset' : 'market';
      setMode(newMode);
      setNavKey((k) => k + 1);
      navigate(newMode === 'asset' ? '/portfolio' : '/dashboard');
    }, 300);

    // Reset flipping state after animation completes
    setTimeout(() => setIsFlipping(false), 700);
  }, [isFlipping, mode, navigate]);

  useEffect(() => {
    return () => { if (flipTimer.current) clearTimeout(flipTimer.current); };
  }, []);

  const isCyan = mode === 'market';

  return (
    <div className="app-layout">
      <aside className="app-sidebar">
        {/* ── Logo 区：点击六边形切换模式 ── */}
        <div
          className={`logo-scene ${isFlipping ? 'flipping' : ''}`}
          data-mode={mode}
          onClick={handleLogoClick}
        >
          {/* 脉冲光环 */}
          <div className={`hex-pulse ${isFlipping ? 'active' : ''}`} />

          {/* 六边形容器 */}
          <div className={`hex-container ${isFlipping ? 'flip' : ''}`}>
            {/* 六边形 SVG */}
            <svg className="hex-shape" viewBox="0 0 52 60" fill="none">
              <path
                d="M26 2 L49 16 L49 44 L26 58 L3 44 L3 16 Z"
                className="hex-fill"
              />
              <path
                d="M26 2 L49 16 L49 44 L26 58 L3 44 L3 16 Z"
                className="hex-stroke"
              />
            </svg>

            {/* 装饰线条 */}
            <div className={`hex-deco ${isFlipping ? 'spin' : ''}`}>
              <span className="hex-line hex-line-t" />
              <span className="hex-line hex-line-b" />
            </div>

            {/* 中心字符 */}
            <span className={`hex-char ${isFlipping ? 'swap' : ''}`}>
              {isCyan ? '知' : '行'}
            </span>
          </div>

          {/* 标题与副标题 */}
          <div className="logo-text">
            <div className={`logo-title ${isFlipping ? 'out' : ''}`}>
              {isCyan ? '有知' : '有行'}
            </div>
            <div className={`logo-subtitle ${isFlipping ? 'out' : ''}`}>
              {isCyan ? '知是行之始' : '行是知之成'}
            </div>
          </div>
        </div>

        {/* ── 导航 ── */}
        <nav className="nav-section" key={navKey}>
          {menuItems.map((item) => (
            <div
              key={item.key}
              className={`nav-item ${isActive(item.key) ? 'active' : ''}`}
              onClick={() => navigate(item.key)}
            >
              <span className="nav-item-icon">{item.icon}</span>
              <span>{item.label}</span>
            </div>
          ))}
        </nav>

        {/* ── 底部：助手 + 设置 ── */}
        <div className="sidebar-bottom">
          <div
            className={`nav-item ${assistantOpen ? 'active' : ''}`}
            onClick={() => setAssistantOpen((v) => !v)}
          >
            <span className="nav-item-icon"><SmileOutlined /></span>
            <span>萌可助手</span>
          </div>
          <div
            className={`nav-item ${location.pathname === '/settings' ? 'active' : ''}`}
            onClick={() => navigate('/settings')}
          >
            <span className="nav-item-icon"><SettingOutlined /></span>
            <span>设置</span>
          </div>
        </div>
      </aside>

      <main className="app-main">
        <div className="app-content">
          <Outlet />
        </div>
      </main>

      <AssistantDrawer open={assistantOpen} onClose={() => setAssistantOpen(false)} />
      <Assistant />
    </div>
  );
}
