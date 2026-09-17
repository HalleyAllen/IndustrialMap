import { useEffect, useMemo, useState } from 'react'
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Popconfirm,
  Typography,
  message,
  Card,
  Tabs,
  Tag,
  Alert,
  Spin,
} from 'antd'
import { PlusOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { companiesApi, industriesApi, relationsApi } from '../api/client'
import type { Company, CompanyEnrichOut, CompanyIn, Industry, RelationIn } from '../types'

export default function CompaniesPage() {
  const [data, setData] = useState<Company[]>([])
  const [industries, setIndustries] = useState<Industry[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [filterIndustry, setFilterIndustry] = useState<string | undefined>()

  const [editing, setEditing] = useState<Company | null>(null)
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm<CompanyIn>()

  const [relOpen, setRelOpen] = useState(false)
  const [relForm] = Form.useForm<RelationIn>()
  const [relTypes, setRelTypes] = useState<string[]>([])

  // AI 补全状态
  const [enrichTarget, setEnrichTarget] = useState<Company | null>(null)
  const [enrichLoading, setEnrichLoading] = useState(false)
  const [enrichResult, setEnrichResult] = useState<CompanyEnrichOut | null>(null)
  const [enrichForm] = Form.useForm<{
    description?: string
    website?: string
    founded_year?: number | null
    address?: string
    scale?: string
  }>()
  const [enrichHint, setEnrichHint] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      setData(
        await companiesApi.list({
          keyword: keyword || undefined,
          industry_code: filterIndustry,
        }),
      )
    } catch (e: any) {
      message.error(e?.message ?? '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    industriesApi.list().then(setIndustries).catch(() => {})
    relationsApi.types().then(setRelTypes).catch(() => {})
  }, [])

  useEffect(() => {
    load()
  }, [keyword, filterIndustry])

  const onCreate = () => {
    setEditing(null)
    form.resetFields()
    setOpen(true)
  }

  const onEdit = (c: Company) => {
    setEditing(c)
    form.setFieldsValue({
      name: c.name,
      industry_code: c.industry_code ?? undefined,
      description: c.description ?? undefined,
      address: c.address ?? undefined,
      founded_year: c.founded_year ?? undefined,
      scale: c.scale ?? undefined,
      website: c.website ?? undefined,
    })
    setOpen(true)
  }

  const onSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (editing) {
        await companiesApi.update(editing.id, values)
        message.success('已更新')
      } else {
        await companiesApi.create(values)
        message.success('已创建')
      }
      setOpen(false)
      load()
    } catch (e: any) {
      if (e?.errorFields) return
      message.error(e?.message ?? '保存失败')
    }
  }

  const onDelete = async (id: string) => {
    try {
      const r = await companiesApi.remove(id)
      message.success(`已删除 ${r.deleted} 个企业`)
      load()
    } catch (e: any) {
      message.error(e?.message ?? '删除失败')
    }
  }

  const onCreateRelation = async () => {
    try {
      const values = await relForm.validateFields()
      if (values.from_id === values.to_id) {
        message.warning('不能给自己建立关系')
        return
      }
      await relationsApi.create(values)
      message.success('关系已创建')
      setRelOpen(false)
      relForm.resetFields()
    } catch (e: any) {
      if (e?.errorFields) return
      message.error(e?.message ?? '创建失败')
    }
  }

  // ===== AI 补全 =====
  const onOpenEnrich = (c: Company) => {
    setEnrichTarget(c)
    setEnrichResult(null)
    setEnrichHint('')
    enrichForm.setFieldsValue({
      description: c.description ?? '',
      website: c.website ?? '',
      founded_year: c.founded_year ?? null,
      address: c.address ?? '',
      scale: c.scale ?? '',
    })
  }

  const onRunEnrich = async () => {
    if (!enrichTarget) return
    setEnrichLoading(true)
    try {
      const r = await companiesApi.enrich(enrichTarget.id, {
        user_hint: enrichHint || undefined,
      })
      setEnrichResult(r)
      // 把建议值合并进表单（仅当现有为空时填充；保留人工数据）
      enrichForm.setFieldsValue({
        description: r.suggestions.description || enrichTarget.description || '',
        website: r.suggestions.website || enrichTarget.website || '',
        founded_year: r.suggestions.founded_year ?? enrichTarget.founded_year ?? null,
        address: r.suggestions.address || enrichTarget.address || '',
        scale: r.suggestions.scale || enrichTarget.scale || '',
      })
      message.success('AI 补全完成，请确认后再写入')
    } catch (e: any) {
      message.error(e?.message ?? 'AI 补全失败')
    } finally {
      setEnrichLoading(false)
    }
  }

  const onApplyEnrich = async () => {
    if (!enrichTarget) return
    try {
      const values = await enrichForm.validateFields()
      // 仅传非空字段
      const payload: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(values)) {
        if (v !== '' && v !== null && v !== undefined) payload[k] = v
      }
      if (Object.keys(payload).length === 0) {
        message.warning('没有可写入的字段')
        return
      }
      const r = await companiesApi.applyEnrichment(enrichTarget.id, payload)
      message.success(`已写入 ${r.written} 个字段`)
      setEnrichTarget(null)
      load()
    } catch (e: any) {
      if (e?.errorFields) return
      message.error(e?.message ?? '写入失败')
    }
  }

  const companyOptions = useMemo(
    () => data.map((c) => ({ value: c.id, label: c.name })),
    [data],
  )

  return (
    <Card>
      <Tabs
        defaultActiveKey="list"
        items={[
          {
            key: 'list',
            label: '企业列表',
            children: (
              <>
                <Space style={{ marginBottom: 16 }} wrap>
                  <Typography.Title level={3} style={{ margin: 0 }}>企业管理</Typography.Title>
                  <Input.Search
                    placeholder="按名称搜索"
                    allowClear
                    onSearch={setKeyword}
                    style={{ width: 240 }}
                  />
                  <Select
                    placeholder="按行业筛选"
                    allowClear
                    style={{ width: 200 }}
                    options={industries.map((i) => ({ value: i.code, label: i.name }))}
                    onChange={(v) => setFilterIndustry(v)}
                    value={filterIndustry}
                  />
                  <Button type="primary" icon={<PlusOutlined />} onClick={onCreate}>
                    新增企业
                  </Button>
                  <Button onClick={() => { relForm.resetFields(); setRelOpen(true) }}>
                    建立企业关系
                  </Button>
                </Space>
                <Table
                  loading={loading}
                  rowKey="id"
                  dataSource={data}
                  pagination={{ pageSize: 20, showSizeChanger: true }}
                  columns={[
                    { title: '名称', dataIndex: 'name', width: 220 },
                    {
                      title: '行业',
                      dataIndex: 'industry_name',
                      width: 160,
                      render: (v, r) => v ? <Tag color="blue">{v}</Tag> : <Tag>未分类</Tag>,
                    },
                    { title: '地址', dataIndex: 'address', ellipsis: true },
                    { title: '成立年份', dataIndex: 'founded_year', width: 100 },
                    {
                      title: '规模',
                      dataIndex: 'scale',
                      width: 100,
                      render: (v) => v ? <Tag>{v}</Tag> : '-',
                    },
                    { title: '描述', dataIndex: 'description', ellipsis: true },
                    {
                      title: '操作',
                      width: 240,
                      render: (_, r) => (
                        <Space>
                          <Button type="link" icon={<ThunderboltOutlined />} onClick={() => onOpenEnrich(r)}>
                            AI 补全
                          </Button>
                          <Button type="link" onClick={() => onEdit(r)}>编辑</Button>
                          <Popconfirm title="确定删除？会同时删除其所有关系" onConfirm={() => onDelete(r.id)}>
                            <Button type="link" danger>删除</Button>
                          </Popconfirm>
                        </Space>
                      ),
                    },
                  ]}
                />
              </>
            ),
          },
        ]}
      />

      {/* 创建/编辑企业 */}
      <Modal
        open={open}
        title={editing ? '编辑企业' : '新增企业'}
        onCancel={() => setOpen(false)}
        onOk={onSubmit}
        okText="保存"
        cancelText="取消"
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item label="企业名称" name="name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="所属行业" name="industry_code">
            <Select
              allowClear
              placeholder="选择行业"
              options={industries.map((i) => ({ value: i.code, label: i.name }))}
            />
          </Form.Item>
          <Form.Item label="成立年份" name="founded_year">
            <InputNumber min={1800} max={2100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="规模" name="scale">
            <Select
              allowClear
              options={[
                { value: 'small', label: '小型' },
                { value: 'medium', label: '中型' },
                { value: 'large', label: '大型' },
              ]}
            />
          </Form.Item>
          <Form.Item label="地址" name="address">
            <Input />
          </Form.Item>
          <Form.Item label="官网" name="website">
            <Input placeholder="https://" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 建立关系 */}
      <Modal
        open={relOpen}
        title="建立企业关系"
        onCancel={() => setRelOpen(false)}
        onOk={onCreateRelation}
        okText="创建"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={relForm} layout="vertical">
          <Form.Item label="关系类型" name="type" rules={[{ required: true }]}>
            <Select
              placeholder="选择关系类型"
              options={relTypes.map((t) => ({ value: t, label: t }))}
            />
          </Form.Item>
          <Form.Item label="起点企业" name="from_id" rules={[{ required: true }]}>
            <Select
              showSearch
              placeholder="选择起点"
              options={companyOptions}
              filterOption={(input, option) =>
                (option?.label ?? '').toString().toLowerCase().includes(input.toLowerCase())
              }
            />
          </Form.Item>
          <Form.Item label="终点企业" name="to_id" rules={[{ required: true }]}>
            <Select
              showSearch
              placeholder="选择终点"
              options={companyOptions}
              filterOption={(input, option) =>
                (option?.label ?? '').toString().toLowerCase().includes(input.toLowerCase())
              }
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* AI 补全 Modal */}
      <Modal
        open={!!enrichTarget}
        title={enrichTarget ? `AI 补全：${enrichTarget.name}` : ''}
        onCancel={() => setEnrichTarget(null)}
        onOk={onApplyEnrich}
        okText="应用建议并写入"
        cancelText="关闭"
        width={720}
        destroyOnClose
        confirmLoading={enrichLoading}
      >
        <Spin spinning={enrichLoading}>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message="AI 将根据企业名称与已知字段推断缺失信息，可在下方补充提示"
          />
          <Input.TextArea
            placeholder="可选：补充提示，例如「请补充该公司的工商注册信息和主营业务」"
            rows={2}
            value={enrichHint}
            onChange={(e) => setEnrichHint(e.target.value)}
            style={{ marginBottom: 12 }}
          />
          <Space style={{ marginBottom: 16 }}>
            <Button type="primary" icon={<ThunderboltOutlined />} onClick={onRunEnrich}>
              调用 AI 生成建议
            </Button>
            {enrichResult && (
              <span style={{ color: '#999' }}>已生成建议，可在下方编辑后应用</span>
            )}
          </Space>

          <Form form={enrichForm} layout="vertical">
            <Form.Item label="简介" name="description">
              <Input.TextArea rows={3} />
            </Form.Item>
            <Form.Item label="官网" name="website">
              <Input placeholder="https://..." />
            </Form.Item>
            <Form.Item label="成立年份" name="founded_year">
              <InputNumber min={1700} max={2100} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="地址" name="address">
              <Input />
            </Form.Item>
            <Form.Item label="规模" name="scale">
              <Select
                allowClear
                options={[
                  { value: 'small', label: '小型' },
                  { value: 'medium', label: '中型' },
                  { value: 'large', label: '大型' },
                ]}
              />
            </Form.Item>
          </Form>
        </Spin>
      </Modal>
    </Card>
  )
}