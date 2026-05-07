import {
  AlertOutlined,
  AppstoreOutlined,
  BankOutlined,
  BarChartOutlined,
  CrownOutlined,
  DashboardOutlined,
  LineChartOutlined,
  ExperimentOutlined,
  EyeOutlined,
  NodeIndexOutlined,
  SwapOutlined,
  EditOutlined,
  FileTextOutlined,
  FundOutlined,
  HeartOutlined,
  PieChartOutlined,
  ScheduleOutlined,
  SettingOutlined,
  SmileOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import '../../App.css';
import Assistant from '../Assistant';
import type { AssistantHandle } from '../Assistant';
import { CopilotProvider } from '../Assistant/CopilotContext';
import AssistantDrawer from '../AssistantDrawer';
import AssistantFloat from '../AssistantFloat';

const fmtTz = (tz: string) => {
  const now = new Date();
  return now.toLocaleString('zh-CN', {
    timeZone: tz,
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  });
};

function useDualClock() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((v) => v + 1), 1000);
    return () => clearInterval(t);
  }, []);
  return {
    shanghai: fmtTz('Asia/Shanghai'),
    ashburn: fmtTz('America/New_York'),
  };
}

type AppMode = 'asset' | 'market';

const assetMenuItems = [
  { key: '/portfolio', icon: <FundOutlined />, label: '资金大盘' },
  { key: '/attribution', icon: <PieChartOutlined />, label: '收益归因' },
  { key: '/allocation', icon: <PieChartOutlined />, label: '良田配比' },
  { key: '/asset-records', icon: <FileTextOutlined />, label: '资产记录' },
  { key: '/funds', icon: <BankOutlined />, label: '资产标的' },
  { key: '/classification', icon: <AppstoreOutlined />, label: '标的分类' },
  { key: '/nanny-salary', icon: <TeamOutlined />, label: '月嫂发薪' },
];

const marketMenuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '大盘看板' },
  { key: '/market-insight', icon: <AppstoreOutlined />, label: '大盘洞察' },
  { key: '/fund-xray', icon: <EyeOutlined />, label: '基金透视' },
  { key: '/fund-compare', icon: <SwapOutlined />, label: '基金比较' },
  { key: '/correlation', icon: <NodeIndexOutlined />, label: '相关性' },
  { key: '/analysis', icon: <BarChartOutlined />, label: '基金分析' },
  { key: '/valuation', icon: <DashboardOutlined />, label: '估值指标' },
  { key: '/backtest', icon: <ExperimentOutlined />, label: '回测' },
  { key: '/strategy', icon: <AlertOutlined />, label: '策略管理' },
  { key: '/guru-focus', icon: <CrownOutlined />, label: '价值大师' },
  { key: '/ma-timing', icon: <LineChartOutlined />, label: '均线择时' },
  { key: '/ic-option', icon: <LineChartOutlined />, label: 'IC期权' },
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
  const assistantRef = useRef<AssistantHandle>(null);

  const clock = useDualClock();

  const copilotOpen = useCallback((sectionName: string, contextData: unknown) => {
    assistantRef.current?.openWithContext(sectionName, contextData);
  }, []);

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

        {/* ── 双时区时钟 ── */}
        <div style={{ padding: '8px 12px', fontSize: 11, color: 'rgba(255,255,255,0.55)', lineHeight: 1.6, borderTop: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'rgba(255,255,255,0.35)' }}>UTC+8</span>
            <span style={{ fontFamily: 'monospace', color: 'rgba(255,255,255,0.7)' }}>{clock.shanghai}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'rgba(255,255,255,0.35)' }}>ASH</span>
            <span style={{ fontFamily: 'monospace', color: 'rgba(255,255,255,0.7)' }}>{clock.ashburn}</span>
          </div>
        </div>

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
            className={`nav-item ${location.pathname === '/scheduler' ? 'active' : ''}`}
            onClick={() => navigate('/scheduler')}
          >
            <span className="nav-item-icon"><ScheduleOutlined /></span>
            <span>定时任务</span>
          </div>
          <div
            className={`nav-item ${location.pathname === '/data-health' ? 'active' : ''}`}
            onClick={() => navigate('/data-health')}
          >
            <span className="nav-item-icon"><HeartOutlined /></span>
            <span>数据健康</span>
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
          <CopilotProvider value={copilotOpen}>
            <Outlet />
          </CopilotProvider>
        </div>
      </main>

      <AssistantDrawer open={assistantOpen} onClose={() => setAssistantOpen(false)} />
      <Assistant ref={assistantRef} />
      <AssistantFloat currentPath={location.pathname} />
    </div>
  );
}
