import { useEffect, useMemo, useState } from 'react'
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  Space,
  Popconfirm,
  Typography,
  Tag,
  message,
  Card,
  ColorPicker,
  Select,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { themesApi } from '../api/client'
import type { Theme } from '../types'
import { THEME_CATEGORY_LABELS } from '../types'

interface FormValues {
  slug: string
  name: string
  icon?: string
  color?: string
  category: 'emerging' | 'traditional' | 'service'
  description?: string
}

const CATEGORY_OPTIONS: Array<{ value: 'emerging' | 'traditional' | 'service'; label: string }> = [
  { value: 'emerging', label: '战略性新兴产业' },
  { value: 'traditional', label: '传统产业' },
  { value: 'service', label: '现代服务业' },
]

const CATEGORY_COLORS: Record<string, string> = {
  emerging: 'blue',
  traditional: 'orange',
  service: 'purple',
}

export default function ThemesPage() {
  const [data, setData] = useState<Theme[]>([])
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState<Theme | null>(null)
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm<FormValues>()

  const load = async () => {
    setLoading(true)
    try {
      setData(await themesApi.list())
    } catch (e: any) {
      message.error(e?.message ?? '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const onCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ color: '#3b82f6', category: 'emerging' })
    setOpen(true)
  }

  const onEdit = (t: Theme) => {
    setEditing(t)
    form.setFieldsValue({
      slug: t.slug,
      name: t.name,
      icon: t.icon,
      color: t.color,
      category: t.category || 'emerging',
      description: t.description,
    })
    setOpen(true)
  }

  const onSubmit = async () => {
    let values: FormValues
    try {
      values = await form.validateFields()
    } catch {
      return
    }
    // ColorPicker 的值可能是对象，转 hex
    const colorHex =
      typeof values.color === 'string'
        ? values.color
        : ((values.color as any)?.toHexString?.() ?? '#3b82f6')
    const payload = { ...values, color: colorHex }
    try {
      if (editing) {
        await themesApi.update(editing.slug, payload)
        message.success('已更新')
      } else {
        await themesApi.create(payload)
        message.success('已创建')
      }
      setOpen(false)
      form.resetFields()
      load()
    } catch (e: any) {
      message.error(e?.message ?? '保存失败')
    }
  }

  const onDelete = async (slug: string) => {
    try {
      const r = await themesApi.remove(slug)
      message.success(`已删除 ${r.deleted_nodes} 个主题节点、${r.deleted_relations} 条关联`)
      load()
    } catch (e: any) {
      message.error(e?.message ?? '删除失败')
    }
  }

  return (
    <Card>
      <Space style={{ marginBottom: 16 }} wrap>
        <Typography.Title level={3} style={{ margin: 0 }}>产业主题管理</Typography.Title>
        <Typography.Text type="secondary">
          主题是企业分类的唯一维度。一个企业可属于 1~N 个主题。
        </Typography.Text>
        <Button type="primary" icon={<PlusOutlined />} onClick={onCreate}>
          新增主题
        </Button>
      </Space>
      <Table
        loading={loading}
        rowKey="slug"
        dataSource={data}
        pagination={false}
        columns={[
          {
            title: '分类',
            dataIndex: 'category',
            width: 120,
            render: (v: string) => (
              <Tag color={CATEGORY_COLORS[v] || 'default'}>
                {THEME_CATEGORY_LABELS[v] || v}
              </Tag>
            ),
          },
          {
            title: '图标',
            dataIndex: 'icon',
            width: 80,
            render: (v: string) => <span style={{ fontSize: 18 }}>{v || '—'}</span>,
          },
          {
            title: 'slug',
            dataIndex: 'slug',
            width: 200,
            render: (v: string) => <Tag>{v}</Tag>,
          },
          {
            title: '名称',
            dataIndex: 'name',
            width: 200,
            render: (v: string, r: Theme) => (
              <span>
                <span
                  style={{
                    display: 'inline-block',
                    width: 12,
                    height: 12,
                    background: r.color,
                    borderRadius: 2,
                    marginRight: 6,
                    verticalAlign: 'middle',
                  }}
                />
                {v}
              </span>
            ),
          },
          { title: '简介', dataIndex: 'description', ellipsis: true },
          {
            title: '企业数',
            dataIndex: 'company_count',
            width: 100,
            render: (v: number) => <Tag color={v ? 'blue' : 'default'}>{v ?? 0}</Tag>,
          },
          {
            title: '操作',
            width: 160,
            render: (_, r) => (
              <Space>
                <Button type="link" onClick={() => onEdit(r)}>编辑</Button>
                <Popconfirm
                  title="确定删除？会同时移除该主题下所有企业的关联"
                  onConfirm={() => onDelete(r.slug)}
                >
                  <Button type="link" danger>删除</Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        open={open}
        title={editing ? '编辑主题' : '新增主题'}
        onCancel={() => setOpen(false)}
        onOk={onSubmit}
        okText="保存"
        cancelText="取消"
        destroyOnClose
        width={560}
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item
            label="slug（英文短码，唯一）"
            name="slug"
            rules={[
              { required: true, message: '请填写 slug' },
              { pattern: /^[a-z0-9-]+$/, message: '只能包含小写字母、数字、短横线' },
            ]}
            extra={editing ? 'slug 是主键，编辑时不可修改' : '建议使用英文短语，如 new-energy / nev / semiconductor'}
          >
            <Input placeholder="如：new-energy" disabled={!!editing} />
          </Form.Item>
          <Form.Item
            label="名称"
            name="name"
            rules={[{ required: true, message: '请填写名称' }]}
          >
            <Input placeholder="如：新能源" />
          </Form.Item>
          <Form.Item label="图标（emoji）" name="icon">
            <Input placeholder="如：⚡" maxLength={4} />
          </Form.Item>
          <Form.Item label="主题色" name="color" rules={[{ required: true }]}>
            <ColorPicker format="hex" showText />
          </Form.Item>
          <Form.Item
            label="分类"
            name="category"
            rules={[{ required: true, message: '请选择分类' }]}
          >
            <Select
              options={CATEGORY_OPTIONS}
              placeholder="选择主题所属分类"
            />
          </Form.Item>
          <Form.Item label="简介" name="description">
            <Input.TextArea rows={3} placeholder="一句话说明主题包含什么产业" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}