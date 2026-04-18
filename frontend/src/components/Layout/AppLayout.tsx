import {
  AlertOutlined,
  AppstoreOutlined,
  BankOutlined,
  BarChartOutlined,
  DashboardOutlined,
  ExperimentOutlined,
  FundOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useEffect, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import '../../App.css';

type AppMode = 'asset' | 'market';

const assetMenuItems = [
  { key: '/portfolio', icon: <FundOutlined />, label: '资产总览' },
  { key: '/funds', icon: <BankOutlined />, label: '基金管理' },
  { key: '/classification', icon: <AppstoreOutlined />, label: '分类管理' },
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

  useEffect(() => {
    if (location.pathname !== '/settings') {
      setMode(detectMode(location.pathname));
    }
  }, [location.pathname]);

  const menuItems = mode === 'asset' ? assetMenuItems : marketMenuItems;
  const isActive = (key: string) => location.pathname === key || location.pathname.startsWith(key + '/');

  const handleModeChange = (newMode: AppMode) => {
    if (newMode === mode) return;
    setMode(newMode);
    setNavKey((k) => k + 1);
    navigate(newMode === 'asset' ? '/portfolio' : '/dashboard');
  };

  return (
    <div className="app-layout">
      <aside className="app-sidebar">
        {/* ── Logo 区：有知=翻书 / 有行=悟空行走 ── */}
        <div className="logo-scene" key={`logo-${mode}`}>
          {mode === 'market' ? (
            <>
              <div className="book-anim">
                <div className="book-page-left" />
                <div className="book-page-right" />
                <div className="book-page-flip" />
                <div className="book-spine" />
                <div className="book-base" />
              </div>
              <div>
                <div className="logo-title">有知</div>
                <div className="logo-subtitle">洞察市场</div>
              </div>
            </>
          ) : (
            <>
              <div className="wukong-scene">
                <div className="wk-ground" />
                <div className="wk-path" />
                <div className="wk-figure">
                  <div className="wk-staff" />
                  <div className="wk-head" />
                  <div className="wk-arm-l" />
                  <div className="wk-arm-r" />
                  <div className="wk-body" />
                  <div className="wk-leg-l" />
                  <div className="wk-leg-r" />
                </div>
                <div className="wk-horizon">
                  <div className="wk-mountain" />
                  <div className="wk-mountain" />
                </div>
              </div>
              <div style={{ position: 'absolute', right: 16 }}>
                <div className="logo-title">有行</div>
                <div className="logo-subtitle">知行合一</div>
              </div>
            </>
          )}
        </div>

        {/* ── 有知 / 有行 切换 ── */}
        <div className="mode-tabs">
          <div
            className="mode-tabs-indicator"
            data-pos={mode === 'market' ? 'left' : 'right'}
          />
          <button
            className={`mode-tab ${mode === 'market' ? 'active' : ''}`}
            onClick={() => handleModeChange('market')}
          >
            有知
          </button>
          <button
            className={`mode-tab ${mode === 'asset' ? 'active' : ''}`}
            onClick={() => handleModeChange('asset')}
          >
            有行
          </button>
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

        {/* ── 设置 ── */}
        <div className="sidebar-bottom">
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
    </div>
  );
}
