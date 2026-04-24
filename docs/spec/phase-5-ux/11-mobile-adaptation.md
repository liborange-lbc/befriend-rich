# #11 移动端适配

## 概述
响应式布局 + PWA 支持，让移动端可以快速查看关键指标。

## 设计

### CSS 响应式
- 侧边栏在 < 768px 时收起为底部 tab bar
- 内容区域全宽
- 表格水平滚动
- 卡片自适应网格

### PWA
- 添加 manifest.json
- 添加 viewport meta tag
- 支持 Add to Home Screen

### 技术决策
- 不引入新 UI 框架（继续使用 AntD，其组件已有响应式支持）
- 通过 CSS media query 实现，不拆分移动端和桌面端组件
- 侧边栏变为底部 tab bar 仅在宽度 < 768px 时触发
