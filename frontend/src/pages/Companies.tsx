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
  Tag,
  TreeSelect,
} from 'antd'
import { ImportOutlined, PlusOutlined } from '@ant-design/icons'
import { companiesApi, themesApi, relationsApi, industryApi } from '../api/client'
import ImportCompaniesModal from '../components/ImportCompaniesModal'
import type {
  Company,
  CompanyIn,
  IndustryCategoryNode,
  RelationIn,
  Theme,
} from '../types'
import { INDUSTRY_LEVEL_COLORS, relationTypeLabel } from '../types'

export default function CompaniesPage() {
  const [data, setData] = useState<Company[]>([])
  const [themes, setThemes] = useState<Theme[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [filterTheme, setFilterTheme] = useState<string | undefined>()
  const [filterIndustry, setFilterIndustry] = useState<string | undefined>()
  const [industryTree, setIndustryTree] = useState<IndustryCategoryNode[]>([])

  const [editing, setEditing] = useState<Company | null>(null)
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm<CompanyIn>()

  const [relOpen, setRelOpen] = useState(false)
  const [relForm] = Form.useForm<RelationIn>()
  const [relTypes, setRelTypes] = useState<string[]>([])

  const [importOpen, setImportOpen] = useState(false)

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
          theme_slug: filterTheme,
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
    themesApi.list().then(setThemes).catch(() => {})
    relationsApi.types().then(setRelTypes).catch(() => {})
    // 行业分类未初始化时返回空数组，不阻塞页面
    industryApi.tree().then(setIndustryTree).catch(() => {})
  }, [])

  useEffect(() => {
    load()
  }, [keyword, filterTheme, filterIndustry])

  const onCreate = () => {
    setEditing(null)
    form.resetFields()
    setOpen(true)
  }

  const onEdit = (c: Company) => {
    setEditing(c)
    form.setFieldsValue({
      name: c.name,
      theme_slugs: c.themes.map((t) => t.slug),
      industry_codes: c.industries.map((i) => i.code),
    })
    setOpen(true)
  }

  const onSubmit = async () => {
    let values: CompanyIn
    try {
      values = await form.validateFields()
    } catch {
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

  // 主题选项（按主题色渲染）
  const themeOptions = useMemo(
    () =>
      themes.map((t) => ({
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
        searchLabel: t.slug + ' ' + t.name,
      })),
    [themes],
  )

  // 国标行业分类树（TreeSelect 用），标题格式：`131 谷物磨制`
  const industryTreeData = useMemo(() => {
    const build = (nodes: IndustryCategoryNode[]): any[] =>
      nodes.map((n) => ({
        value: n.code,
        title: `${n.code} ${n.name}`,
        key: n.code,
        children: n.children?.length ? build(n.children) : undefined,
      }))
    return build(industryTree)
  }, [industryTree])

  return (
    <Card>
      <Space style={{ marginBottom: 16 }} wrap>
        <Typography.Title level={3} style={{ margin: 0 }}>企业管理</Typography.Title>
        <Input.Search
          placeholder="按名称搜索"
          allowClear
          onSearch={setKeyword}
          style={{ width: 240 }}
        />
        <Select
          placeholder="按主题筛选"
          allowClear
          style={{ width: 220 }}
          options={themeOptions.map((o) => ({ value: o.value, label: o.label }))}
          onChange={(v) => setFilterTheme(v)}
          value={filterTheme}
        />
        <TreeSelect
          placeholder="按行业分类筛选（含子类）"
          allowClear
          showSearch
          style={{ width: 260 }}
          value={filterIndustry}
          treeData={industryTreeData}
          onChange={(v) => setFilterIndustry(v)}
          treeNodeFilterProp="title"
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={onCreate}>
          新增企业
        </Button>
        <Button icon={<ImportOutlined />} onClick={() => setImportOpen(true)}>
          批量导入
        </Button>
        <Button
          onClick={() => {
            relForm.resetFields()
            setRelOpen(true)
          }}
        >
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
            title: '所属主题',
            dataIndex: 'themes',
            render: (ts: Company['themes']) =>
              ts && ts.length > 0 ? (
                <Space wrap>
                  {ts.map((t) => (
                    <Tag
                      key={t.slug}
                      color={t.color}
                      style={{ borderRadius: 12 }}
                    >
                      {t.icon ? `${t.icon} ` : ''}
                      {t.name}
                    </Tag>
                  ))}
                </Space>
              ) : (
                <Tag>未分类</Tag>
              ),
          },
          {
            title: '行业分类（国标）',
            dataIndex: 'industries',
            width: 320,
            render: (is: Company['industries']) =>
              is && is.length > 0 ? (
                <Space wrap size={[4, 4]}>
                  {is.map((i) => (
                    <Tag key={i.code} color={INDUSTRY_LEVEL_COLORS[i.level]}>
                      {i.code} {i.name}
                    </Tag>
                  ))}
                </Space>
              ) : (
                <Tag>未分类</Tag>
              ),
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

      {/* 创建 / 编辑企业：名称 + 多选主题 */}
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
          <Form.Item
            label="所属产业主题"
            name="theme_slugs"
            rules={[{ required: true, message: '请至少选择 1 个主题', type: 'array', min: 1 }]}
          >
            <Select
              mode="multiple"
              placeholder="选择 1~N 个主题"
              options={themeOptions}
              optionFilterProp="searchLabel"
              filterOption={(input, option: any) =>
                (option?.searchLabel ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </Form.Item>
          <Form.Item
            label="国标行业分类"
            name="industry_codes"
            extra="可选。依据 GB/T 4754-2017《国民经济行业分类》，通常选到小类；可多选。"
          >
            <TreeSelect
              multiple
              treeCheckable
              showSearch
              allowClear
              maxTagCount="responsive"
              treeNodeFilterProp="title"
              placeholder="选择行业分类（可多选）"
              treeData={industryTreeData}
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

      {/* 批量导入：上传 → 自检 → 确认 */}
      <ImportCompaniesModal
        open={importOpen}
        themes={themes}
        onClose={() => setImportOpen(false)}
        onImported={load}
      />
    </Card>
  )
}