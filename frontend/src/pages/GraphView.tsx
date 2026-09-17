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
import { graphApi, themesApi } from '../api/client'
import type { GraphData, GraphNode, GraphStats, Theme } from '../types'

export default function GraphPage() {
  const [stats, setStats] = useState<GraphStats | null>(null)
  const [themes, setThemes] = useState<Theme[]>([])
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [] })
  const [loading, setLoading] = useState(false)
  const [themeSlug, setThemeSlug] = useState<string | undefined>()
  const [selected, setSelected] = useState<GraphNode | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [s, g] = await Promise.all([
        graphApi.stats(),
        graphApi.full({ theme_slug: themeSlug, limit: 500 }),
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
    themesApi.list().then(setThemes).catch(() => {})
  }, [])

  useEffect(() => {
    load()
  }, [themeSlug])

  return (
    <Spin spinning={loading}>
      <Space style={{ marginBottom: 16 }} wrap>
        <Typography.Title level={3} style={{ margin: 0 }}>图谱可视化</Typography.Title>
        <Select
          placeholder="按主题筛选（仅显示属于该主题的企业及其关系）"
          allowClear
          style={{ minWidth: 320 }}
          options={themes.map((t) => ({
            value: t.slug,
            label: (
              <span>
                <span
                  style={{
                    display: 'inline-block',
                    width: 10,
                    height: 10,
                    background: t.color,
                    borderRadius: 2,
                    marginRight: 6,
                  }}
                />
                {t.icon ? `${t.icon} ` : ''}
                {t.name}
              </span>
            ),
          }))}
          onChange={(v) => setThemeSlug(v)}
          value={themeSlug}
        />
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
      </Space>

      {stats && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={8}>
            <Card>
              <Statistic title="企业数" value={stats.company_count} />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic title="主题数" value={stats.theme_count} />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic title="关系数" value={stats.relation_count} />
            </Card>
          </Col>
        </Row>
      )}

      <Card>
        {graph.nodes.length === 0 ? (
          <Empty
            description={
              loading
                ? '加载中...'
                : '暂无数据，请先在「企业管理」「主题管理」中添加数据'
            }
          />
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
            <Descriptions.Item label="所属主题">
              {selected.themes && selected.themes.length > 0 ? (
                <Space wrap>
                  {selected.themes.map((t) => (
                    <Tag key={t.slug} color={t.color}>
                      {t.icon ? `${t.icon} ` : ''}
                      {t.name}
                    </Tag>
                  ))}
                </Space>
              ) : (
                <Tag>未分类</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="节点 ID">
              <span style={{ fontFamily: 'monospace', fontSize: 12 }}>
                {selected.id}
              </span>
            </Descriptions.Item>
          </Descriptions>
        )}
        <div style={{ marginTop: 12, color: '#999' }}>
          <AimOutlined /> 后续可在企业管理中编辑该企业的主题归属，并接入 AI 自动补全。
        </div>
      </Modal>
    </Spin>
  )
}