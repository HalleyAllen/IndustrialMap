import { useEffect, useState } from 'react'
import {
  Card,
  Select,
  Space,
  Typography,
  Statistic,
  Row,
  Col,
  Button,
  Empty,
  Spin,
  message,
  Modal,
  Descriptions,
  Tag,
} from 'antd'
import { ReloadOutlined, AimOutlined } from '@ant-design/icons'
import GraphCanvas from '../components/GraphCanvas'
import { graphApi, industriesApi } from '../api/client'
import type { GraphData, GraphNode, GraphStats, Industry } from '../types'

export default function GraphPage() {
  const [stats, setStats] = useState<GraphStats | null>(null)
  const [industries, setIndustries] = useState<Industry[]>([])
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [] })
  const [loading, setLoading] = useState(false)
  const [industryCode, setIndustryCode] = useState<string | undefined>()
  const [selected, setSelected] = useState<GraphNode | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [s, g] = await Promise.all([
        graphApi.stats(),
        graphApi.full({ industry_code: industryCode, limit: 500 }),
      ])
      setStats(s)
      setGraph(g)
    } catch (e: any) {
      message.error(e?.message ?? '加载图谱失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    industriesApi.list().then(setIndustries).catch(() => {})
  }, [])

  useEffect(() => {
    load()
  }, [industryCode])

  return (
    <Spin spinning={loading}>
      <Space style={{ marginBottom: 16 }} wrap>
        <Typography.Title level={3} style={{ margin: 0 }}>图谱可视化</Typography.Title>
        <Select
          placeholder="按行业筛选（显示行业内企业及关系）"
          allowClear
          style={{ minWidth: 280 }}
          options={industries.map((i) => ({ value: i.code, label: i.name }))}
          onChange={(v) => setIndustryCode(v)}
          value={industryCode}
        />
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
      </Space>

      {stats && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={8}><Card><Statistic title="企业数" value={stats.company_count} /></Card></Col>
          <Col span={8}><Card><Statistic title="行业数" value={stats.industry_count} /></Card></Col>
          <Col span={8}><Card><Statistic title="关系数" value={stats.relation_count} /></Card></Col>
        </Row>
      )}

      <Card>
        {graph.nodes.length === 0 ? (
          <Empty description={loading ? '加载中...' : '暂无数据，请先在「企业管理」「行业管理」中添加数据'} />
        ) : (
          <GraphCanvas data={graph} onNodeClick={setSelected} height={620} />
        )}
      </Card>

      <Modal
        open={!!selected}
        title={selected ? `企业：${selected.name}` : ''}
        footer={<Button onClick={() => setSelected(null)}>关闭</Button>}
        onCancel={() => setSelected(null)}
      >
        {selected && (
          <Descriptions column={1} size="small">
            <Descriptions.Item label="名称">{selected.name}</Descriptions.Item>
            <Descriptions.Item label="行业">
              {selected.industry_name
                ? <Tag color="blue">{selected.industry_name}</Tag>
                : <Tag>未分类</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="节点 ID">
              <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{selected.id}</span>
            </Descriptions.Item>
          </Descriptions>
        )}
        <div style={{ marginTop: 12, color: '#999' }}>
          <AimOutlined /> 后续可在企业管理中编辑该企业的详细信息，并接入 AI 自动补全。
        </div>
      </Modal>
    </Spin>
  )
}