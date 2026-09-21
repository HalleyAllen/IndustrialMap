import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  Alert,
  Breadcrumb,
  Card,
  Col,
  Descriptions,
  Empty,
  Input,
  List,
  Row,
  Space,
  Spin,
  Statistic,
  Tag,
  Tree,
  Typography,
  message,
} from 'antd'
import {
  ApartmentOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import { industryApi } from '../api/client'
import type {
  IndustryCategoryDetail,
  IndustryCategoryNode,
  IndustryStats,
} from '../types'
import { INDUSTRY_LEVEL_COLORS, industryLevelLabel } from '../types'

interface TreeNodeData {
  key: string
  title: ReactNode
  children?: TreeNodeData[]
  isLeaf?: boolean
}

/** 分类树 → antd Tree 数据 */
function toTreeData(nodes: IndustryCategoryNode[]): TreeNodeData[] {
  return nodes.map((n) => ({
    key: n.code,
    title: (
      <Space size={6}>
        <Typography.Text type="secondary" style={{ fontSize: 12, fontFamily: 'monospace' }}>
          {n.code}
        </Typography.Text>
        <span>{n.name}</span>
        {n.company_count_total > 0 && (
          <Tag color="blue" style={{ marginInlineStart: 2 }}>
            {n.company_count_total}
          </Tag>
        )}
      </Space>
    ),
    children: n.children?.length ? toTreeData(n.children) : undefined,
    isLeaf: !n.children?.length,
  }))
}

/** 关键词过滤：命中节点或其任一后代命中则保留（保住层级路径） */
function filterTree(nodes: IndustryCategoryNode[], kw: string): IndustryCategoryNode[] {
  if (!kw) return nodes
  const needle = kw.trim().toLowerCase()
  if (!needle) return nodes

  const out: IndustryCategoryNode[] = []
  for (const n of nodes) {
    const selfHit =
      n.code.toLowerCase().includes(needle) || n.name.toLowerCase().includes(needle)
    const kids = filterTree(n.children ?? [], kw)
    if (selfHit || kids.length > 0) {
      out.push({ ...n, children: kids })
    }
  }
  return out
}

function DetailPanel({ detail }: { detail: IndustryCategoryDetail }) {
  return (
    <Card
      size="small"
      title={
        <Breadcrumb
          items={detail.path.map((p) => ({ title: `${p.code} ${p.name}` }))}
        />
      }
    >
      <Descriptions size="small" column={2} bordered>
        <Descriptions.Item label="分类编码">{detail.code}</Descriptions.Item>
        <Descriptions.Item label="分类名称">{detail.name}</Descriptions.Item>
        <Descriptions.Item label="层级">
          <Tag color={INDUSTRY_LEVEL_COLORS[detail.level]}>
            {industryLevelLabel(detail.level)}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="上级分类">{detail.parent_code ?? '—'}</Descriptions.Item>
        <Descriptions.Item label="直接企业数">{detail.company_count}</Descriptions.Item>
        <Descriptions.Item label="含子级企业数">{detail.company_count_total}</Descriptions.Item>
      </Descriptions>

      {detail.children.length > 0 && (
        <>
          <Typography.Title level={5} style={{ marginTop: 16 }}>
            下级分类（{detail.children.length}）
          </Typography.Title>
          <Space wrap size={[6, 6]}>
            {detail.children.map((c) => (
              <Tag key={c.code} color={INDUSTRY_LEVEL_COLORS[c.level]}>
                {c.code} {c.name}
                {c.company_count_total > 0 ? ` · ${c.company_count_total}` : ''}
              </Tag>
            ))}
          </Space>
        </>
      )}

      <Typography.Title level={5} style={{ marginTop: 16 }}>
        关联企业（{detail.companies.length}）
      </Typography.Title>
      {detail.companies.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="该分类下暂无企业" />
      ) : (
        <List
          size="small"
          dataSource={detail.companies}
          style={{ maxHeight: 260, overflow: 'auto' }}
          renderItem={(c) => <List.Item>{c.name}</List.Item>}
        />
      )}
    </Card>
  )
}

export default function IndustriesPage() {
  const [stats, setStats] = useState<IndustryStats | null>(null)
  const [tree, setTree] = useState<IndustryCategoryNode[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [expandedKeys, setExpandedKeys] = useState<string[]>([])
  const [selectedCode, setSelectedCode] = useState<string | null>(null)
  const [detail, setDetail] = useState<IndustryCategoryDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const loadTree = useCallback(async () => {
    setLoading(true)
    try {
      const [s, t] = await Promise.all([industryApi.stats(), industryApi.tree()])
      setStats(s)
      setTree(t)
    } catch (e) {
      message.error((e as Error).message || '加载行业分类失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadTree()
  }, [loadTree])

  const openDetail = useCallback(async (code: string) => {
    setSelectedCode(code)
    setDetailLoading(true)
    try {
      setDetail(await industryApi.get(code))
    } catch (e) {
      message.error((e as Error).message || '加载分类详情失败')
      setDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const filteredTree = useMemo(() => filterTree(tree, keyword), [tree, keyword])
  const treeData = useMemo(() => toTreeData(filteredTree), [filteredTree])

  // 搜索时自动展开命中分支
  useEffect(() => {
    if (!keyword.trim()) return
    const keys: string[] = []
    const walk = (nodes: IndustryCategoryNode[]) => {
      nodes.forEach((n) => {
        if (n.children?.length) {
          keys.push(n.code)
          walk(n.children)
        }
      })
    }
    walk(filteredTree)
    setExpandedKeys(keys)
  }, [keyword, filteredTree])

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card
        title={
          <Space>
            <ApartmentOutlined />
            行业分类
            <Typography.Text type="secondary" style={{ fontWeight: 400, fontSize: 13 }}>
              {stats ? `${stats.standard}《${stats.standard_name}》· ${stats.scope_name}` : ''}
            </Typography.Text>
          </Space>
        }
      >
        <Row gutter={[16, 16]}>
          <Col xs={12} md={4}>
            <Statistic title="大类（2位）" value={stats?.level1 ?? 0} />
          </Col>
          <Col xs={12} md={4}>
            <Statistic title="中类（3位）" value={stats?.level2 ?? 0} />
          </Col>
          <Col xs={12} md={4}>
            <Statistic title="小类（4位）" value={stats?.level3 ?? 0} />
          </Col>
          <Col xs={12} md={4}>
            <Statistic
              title="已挂分类企业"
              value={stats?.linked_company_count ?? 0}
              valueStyle={{ color: '#1677ff' }}
            />
          </Col>
          <Col xs={12} md={4}>
            <Statistic title="关联关系" value={stats?.relation_count ?? 0} />
          </Col>
        </Row>

        {stats && !stats.seeded && (
          <Alert
            style={{ marginTop: 16 }}
            type="info"
            showIcon
            message="数据库中还没有行业分类数据"
            description={
              <span>
                数据库中暂无行业分类节点（预期 {stats.expected_total} 个，
                大类 {stats.expected_counts.level1 ?? 31} + 中类{' '}
                {stats.expected_counts.level2 ?? 179} + 小类 {stats.expected_counts.level3 ?? 609}）。
                需通过后端接口 <code>POST /api/industries/seed</code> 初始化。
              </span>
            }
          />
        )}
      </Card>

      <Row gutter={16}>
        <Col span={9}>
          <Card size="small" title="分类树" bodyStyle={{ padding: 12 }}>
            <Input
              allowClear
              prefix={<SearchOutlined />}
              placeholder="搜索编码或名称，如 131 / 谷物磨制"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              style={{ marginBottom: 12 }}
            />
            {loading ? (
              <Spin />
            ) : treeData.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={stats?.seeded ? '暂无分类数据' : '数据库中暂无分类节点，请通过后端 API 初始化'}
              />
            ) : (
              <Tree
                treeData={treeData}
                expandedKeys={expandedKeys}
                onExpand={(keys) => setExpandedKeys(keys as string[])}
                selectedKeys={selectedCode ? [selectedCode] : []}
                onSelect={(keys) => {
                  const code = keys[0] as string | undefined
                  if (code) openDetail(code)
                }}
                style={{ maxHeight: 620, overflow: 'auto' }}
              />
            )}
          </Card>
        </Col>
        <Col span={15}>
          {detailLoading ? (
            <Card size="small">
              <Spin tip="加载中…">
                <div style={{ height: 80 }} />
              </Spin>
            </Card>
          ) : detail ? (
            <DetailPanel detail={detail} />
          ) : (
            <Card size="small">
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="从左侧选择一个分类查看详情与企业"
              />
            </Card>
          )}
        </Col>
      </Row>
    </Space>
  )
}
