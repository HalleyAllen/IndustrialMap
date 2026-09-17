import { useEffect, useState } from 'react'
import {
  Card,
  Select,
  Space,
  Typography,
  Spin,
  Button,
  Empty,
  message,
  Modal,
  Descriptions,
  Tag,
  Row,
  Col,
  Statistic,
  Tabs,
} from 'antd'
import { ReloadOutlined, ApartmentOutlined } from '@ant-design/icons'
import GraphCanvas from '../components/GraphCanvas'
import { chainsApi } from '../api/client'
import type {
  Chain,
  ChainGraphData,
  Stage,
  StageUpDownStream,
} from '../types'

const LEVEL_COLORS: Record<string, string> = {
  upstream: 'blue',
  middle: 'gold',
  downstream: 'green',
}

const LEVEL_LABELS: Record<string, string> = {
  upstream: '上游',
  middle: '中游',
  downstream: '下游',
}

export default function ChainView() {
  const [chains, setChains] = useState<Chain[]>([])
  const [selectedSlug, setSelectedSlug] = useState<string | undefined>()
  const [graphData, setGraphData] = useState<ChainGraphData | null>(null)
  const [loading, setLoading] = useState(false)
  const [selectedStage, setSelectedStage] = useState<Stage | null>(null)
  const [stageDetail, setStageDetail] = useState<StageUpDownStream | null>(null)
  const [loadingStage, setLoadingStage] = useState(false)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [selectedNodeName, setSelectedNodeName] = useState<string | null>(null)

  // 加载链列表
  useEffect(() => {
    chainsApi
      .list()
      .then((cs) => {
        setChains(cs)
        if (cs.length > 0 && !selectedSlug) {
          setSelectedSlug(cs[0].slug)
        }
      })
      .catch((e) => message.error(e?.message ?? '加载产业链失败'))
  }, [])

  // 加载当前链的图
  const loadGraph = async (slug: string) => {
    setLoading(true)
    try {
      const g = await chainsApi.graph(slug)
      setGraphData(g)
    } catch (e: any) {
      message.error(e?.message ?? '加载产业链图谱失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (selectedSlug) {
      loadGraph(selectedSlug)
      setSelectedStage(null)
      setStageDetail(null)
    }
  }, [selectedSlug])

  // 点击图谱节点
  const onNodeClick = (node: { id: string; label?: string; name?: string; stage_code?: string | null }) => {
    setSelectedNodeId(node.id)
    setSelectedNodeName(node.name || node.id)
    // 如果是 Stage 节点，加载环节详情
    if (node.stage_code && selectedSlug) {
      const stageCode = node.stage_code
      const stage = graphData?.nodes.find((n) => n.stage_code === stageCode && n.label === 'Stage')
      if (stage) {
        // 找到对应的完整 Stage（从 graphData 也可以补 order/level 等）
        const stageStub: Stage = {
          code: stageCode,
          name: stage.name,
          description: '',
          order: stage.level ?? 0,
          level: 'middle',
          upstream_codes: [],
          downstream_codes: [],
          company_count: 0,
        }
        setSelectedStage(stageStub)
        setLoadingStage(true)
        chainsApi
          .stageDetail(selectedSlug, stageCode)
          .then((d) => {
            setStageDetail(d)
            setSelectedStage(d.stage)
          })
          .catch((e) => message.error(e?.message ?? '加载环节详情失败'))
          .finally(() => setLoadingStage(false))
      }
    }
  }

  return (
    <Spin spinning={loading}>
      <Space style={{ marginBottom: 16 }} wrap>
        <Typography.Title level={3} style={{ margin: 0 }}>
          <ApartmentOutlined /> 产业链图谱
        </Typography.Title>
        <Typography.Text type="secondary">
          按"上下游价值流"展示企业所在环节与产业生态
        </Typography.Text>
        <Select
          placeholder="选择产业链"
          style={{ minWidth: 280 }}
          value={selectedSlug}
          onChange={(v) => setSelectedSlug(v)}
          options={chains.map((c) => ({
            value: c.slug,
            label: (
              <span>
                <span
                  style={{
                    display: 'inline-block',
                    width: 10,
                    height: 10,
                    background: c.color,
                    borderRadius: 2,
                    marginRight: 6,
                  }}
                />
                {c.icon} {c.name}（{c.stage_count} 环节 · {c.company_count} 企业）
              </span>
            ),
          }))}
        />
        <Button icon={<ReloadOutlined />} onClick={() => selectedSlug && loadGraph(selectedSlug)}>
          刷新
        </Button>
      </Space>

      {graphData && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card>
              <Statistic title="环节数" value={graphData.nodes.filter((n) => n.label === 'Stage').length} />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="已落位企业"
                value={graphData.nodes.filter((n) => n.label === 'Company').length}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="上下游关系"
                value={graphData.edges.filter((e) => e.type === 'UPSTREAM_OF').length}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic title="关系总数" value={graphData.edges.length} />
            </Card>
          </Col>
        </Row>
      )}

      <Row gutter={16}>
        <Col span={selectedStage ? 16 : 24}>
          <Card
            title={
              graphData ? (
                <Space>
                  <span style={{ color: graphData.chain.color }}>{graphData.chain.icon}</span>
                  <span>{graphData.chain.name}</span>
                  <Tag color="blue">{graphData.nodes.filter((n) => n.label === 'Stage').length} 环节</Tag>
                  <Tag color="green">{graphData.nodes.filter((n) => n.label === 'Company').length} 企业</Tag>
                </Space>
              ) : (
                '产业链'
              )
            }
          >
            {!graphData || graphData.nodes.length === 0 ? (
              <Empty description={loading ? '加载中...' : '请选择产业链，或先在 Neo4j 中灌入产业链'} />
            ) : (
              <GraphCanvas chainData={graphData} onNodeClick={onNodeClick} height={620} />
            )}
            {graphData && graphData.chain.description && (
              <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
                {graphData.chain.description}
              </Typography.Paragraph>
            )}
          </Card>
        </Col>

        {selectedStage && stageDetail && (
          <Col span={8}>
            <Card
              title={
                <Space>
                  <Tag color={LEVEL_COLORS[selectedStage.level] || 'gold'}>
                    {LEVEL_LABELS[selectedStage.level] || selectedStage.level}
                  </Tag>
                  <span>{selectedStage.name}</span>
                </Space>
              }
              extra={
                <Button
                  type="link"
                  size="small"
                  onClick={() => {
                    setSelectedStage(null)
                    setStageDetail(null)
                  }}
                >
                  关闭
                </Button>
              }
            >
              <Spin spinning={loadingStage}>
                <Descriptions column={1} size="small" bordered>
                  <Descriptions.Item label="环节码">{selectedStage.code}</Descriptions.Item>
                  <Descriptions.Item label="位置">第 {selectedStage.order} 层</Descriptions.Item>
                  <Descriptions.Item label="已落位企业">
                    <Tag color="blue">{stageDetail.stage.company_count}</Tag>
                  </Descriptions.Item>
                  {selectedStage.description && (
                    <Descriptions.Item label="简介">
                      <Typography.Text type="secondary">{selectedStage.description}</Typography.Text>
                    </Descriptions.Item>
                  )}
                </Descriptions>

                <Tabs
                  size="small"
                  style={{ marginTop: 16 }}
                  items={[
                    {
                      key: 'up',
                      label: (
                        <span>
                          上游 ({stageDetail.upstream_stages.length})
                        </span>
                      ),
                      children: (
                        <>
                          {stageDetail.upstream_stages.length === 0 ? (
                            <Typography.Text type="secondary">无直接上游环节</Typography.Text>
                          ) : (
                            <Space direction="vertical" style={{ width: '100%' }} size={8}>
                              {stageDetail.upstream_stages.map((s) => (
                                <Card key={s.code} size="small">
                                  <Space direction="vertical" size={2} style={{ width: '100%' }}>
                                    <Typography.Text strong>{s.name}</Typography.Text>
                                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                                      企业：
                                      {stageDetail.upstream_companies
                                        .filter((c) => true)
                                        .slice(0, 6)
                                        .map((c) => c.name)
                                        .join('、') || '—'}
                                    </Typography.Text>
                                  </Space>
                                </Card>
                              ))}
                            </Space>
                          )}
                        </>
                      ),
                    },
                    {
                      key: 'down',
                      label: (
                        <span>
                          下游 ({stageDetail.downstream_stages.length})
                        </span>
                      ),
                      children: (
                        <>
                          {stageDetail.downstream_stages.length === 0 ? (
                            <Typography.Text type="secondary">无直接下游环节</Typography.Text>
                          ) : (
                            <Space direction="vertical" style={{ width: '100%' }} size={8}>
                              {stageDetail.downstream_stages.map((s) => (
                                <Card key={s.code} size="small">
                                  <Space direction="vertical" size={2} style={{ width: '100%' }}>
                                    <Typography.Text strong>{s.name}</Typography.Text>
                                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                                      企业：
                                      {stageDetail.downstream_companies
                                        .slice(0, 6)
                                        .map((c) => c.name)
                                        .join('、') || '—'}
                                    </Typography.Text>
                                  </Space>
                                </Card>
                              ))}
                            </Space>
                          )}
                        </>
                      ),
                    },
                  ]}
                />
              </Spin>
            </Card>
          </Col>
        )}
      </Row>

      {/* 节点点击详情 Modal（兜底） */}
      <Modal
        open={!!selectedNodeId && !selectedStage}
        title={selectedNodeName}
        footer={<Button onClick={() => setSelectedNodeId(null)}>关闭</Button>}
        onCancel={() => setSelectedNodeId(null)}
      >
        <Typography.Text type="secondary">
          点击「阶段」节点（黄色方块）可查看上下游详情。
        </Typography.Text>
      </Modal>
    </Spin>
  )
}