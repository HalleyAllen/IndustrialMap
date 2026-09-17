import { useEffect, useMemo, useState } from 'react'
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Space,
  Popconfirm,
  Typography,
  message,
  Card,
  Tabs,
  Tag,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { companiesApi, industriesApi, relationsApi } from '../api/client'
import type { Company, CompanyIn, Industry, RelationIn } from '../types'
import { relationTypeLabel } from '../types'

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

  const extractError = (e: any): string => {
    const detail = e?.response?.data?.detail
    if (detail) return typeof detail === 'string' ? detail : JSON.stringify(detail)
    return e?.message || '未知错误'
  }

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
      message.error(`加载失败：${extractError(e)}`)
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
    })
    setOpen(true)
  }

  const onSubmit = async () => {
    let values: CompanyIn
    try {
      values = await form.validateFields()
    } catch {
      message.error('请先填写企业名称')
      return
    }
    try {
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
      message.error(`保存失败：${extractError(e)}`)
    }
  }

  const onDelete = async (id: string) => {
    try {
      const r = await companiesApi.remove(id)
      message.success(`已删除 ${r.deleted} 个企业`)
      load()
    } catch (e: any) {
      message.error(`删除失败：${extractError(e)}`)
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
      message.error(`创建失败：${extractError(e)}`)
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
                  locale={{ emptyText: '暂无企业，点击右上角「新增企业」开始添加' }}
                  columns={[
                    { title: '企业名称', dataIndex: 'name', width: 320 },
                    {
                      title: '所属行业',
                      dataIndex: 'industry_name',
                      width: 200,
                      render: (v) => v ? <Tag color="blue">{v}</Tag> : <Tag>未分类</Tag>,
                    },
                    {
                      title: '操作',
                      width: 200,
                      render: (_, r) => (
                        <Space>
                          <Button type="link" onClick={() => onEdit(r)}>编辑</Button>
                          <Popconfirm
                            title="确定删除？会同时删除其所有关系"
                            onConfirm={() => onDelete(r.id)}
                          >
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

      {/* 创建 / 编辑企业：只保留名称 + 所属行业 */}
      <Modal
        open={open}
        title={editing ? '编辑企业' : '新增企业'}
        onCancel={() => setOpen(false)}
        onOk={onSubmit}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="企业名称"
            name="name"
            rules={[{ required: true, message: '请填写企业名称' }]}
          >
            <Input placeholder="如：华为技术有限公司" autoFocus />
          </Form.Item>
          <Form.Item label="所属行业" name="industry_code">
            <Select
              allowClear
              placeholder="选择行业（可留空）"
              options={industries.map((i) => ({ value: i.code, label: i.name }))}
              showSearch
              optionFilterProp="label"
            />
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
              options={relTypes.map((t) => ({
                value: t,
                label: `${relationTypeLabel(t)}（${t}）`,
              }))}
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
    </Card>
  )
}