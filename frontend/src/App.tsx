import { useEffect, useState } from 'react'
import { Layout, Menu, Tag, Space, Typography, Alert } from 'antd'
import {
  AppstoreOutlined,
  ApartmentOutlined,
  BankOutlined,
  SettingOutlined,
  PartitionOutlined,
  ClusterOutlined,
} from '@ant-design/icons'
import { Link, Route, Routes, useLocation, Navigate } from 'react-router-dom'
import { settingsApi } from './api/client'

import SettingsPage from './pages/Settings'
import ThemesPage from './pages/Themes'
import CompaniesPage from './pages/Companies'
import GraphPage from './pages/GraphView'
import ChainView from './pages/ChainView'

const { Header, Sider, Content } = Layout

export default function App() {
  const location = useLocation()
  const [configured, setConfigured] = useState<boolean | null>(null)
  const [connected, setConnected] = useState<boolean | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const checkStatus = async () => {
    try {
      const s = await settingsApi.status()
      setConfigured(s.configured)
      setConnected(s.connected)
      setErrorMsg(s.error ?? null)
    } catch {
      // 后端没起，先当未配置
      setConfigured(false)
      setConnected(false)
    }
  }

  useEffect(() => {
    checkStatus()
    // 路由变化时再检查一次（保存配置后状态会刷新）
  }, [location.pathname])

  const items = [
    { key: '/graph', icon: <PartitionOutlined />, label: <Link to="/graph">图谱可视化</Link> },
    { key: '/chains', icon: <ClusterOutlined />, label: <Link to="/chains">产业链</Link> },
    { key: '/companies', icon: <BankOutlined />, label: <Link to="/companies">企业管理</Link> },
    { key: '/themes', icon: <AppstoreOutlined />, label: <Link to="/themes">主题管理</Link> },
    { key: '/settings', icon: <SettingOutlined />, label: <Link to="/settings">数据库配置</Link> },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider width={220} theme="dark" breakpoint="lg" collapsedWidth={0}>
        <div style={{ color: '#fff', padding: 16, fontSize: 16, fontWeight: 600 }}>
          <ApartmentOutlined style={{ marginRight: 8 }} />
          IndustrialMap
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname.startsWith('/') ? '/' + location.pathname.split('/')[1] : '/graph']}
          items={items}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', paddingInline: 24, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography.Title level={4} style={{ margin: 0 }}>企业产业图谱</Typography.Title>
          <Space>
            {configured === false && <Tag color="orange">未配置数据库</Tag>}
            {configured && connected && <Tag color="green">已连接</Tag>}
            {configured && connected === false && <Tag color="red">连接失败</Tag>}
          </Space>
        </Header>
        <Content style={{ margin: 24 }}>
          {configured === false && location.pathname !== '/settings' && (
            <Alert
              style={{ marginBottom: 16 }}
              type="warning"
              showIcon
              message="尚未配置 Neo4j 数据库连接"
              description={
                <span>
                  请先到 <Link to="/settings">数据库配置</Link> 填写 Bolt 地址、账号和密码。
                </span>
              }
            />
          )}
          {configured && connected === false && (
            <Alert
              style={{ marginBottom: 16 }}
              type="error"
              showIcon
              message="Neo4j 连接失败"
              description={errorMsg ?? '请检查配置或服务是否启动'}
            />
          )}
          <Routes>
            <Route path="/" element={<Navigate to="/graph" replace />} />
            <Route path="/graph" element={<GraphPage />} />
            <Route path="/chains" element={<ChainView />} />
            <Route path="/companies" element={<CompaniesPage />} />
            <Route path="/themes" element={<ThemesPage />} />
            <Route path="/settings" element={<SettingsPage onConfigured={checkStatus} />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}