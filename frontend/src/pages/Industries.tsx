import { useEffect, useState } from 'react'
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
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { industriesApi } from '../api/client'
import type { Industry } from '../types'

export default function IndustriesPage() {
  const [data, setData] = useState<Industry[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm<{ code: string; name: string; description?: string }>()

  const load = async () => {
    setLoading(true)
    try {
      setData(await industriesApi.list())
    } catch (e: any) {
      message.error(e?.message ?? '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const onCreate = async () => {
    try {
      const values = await form.validateFields()
      await industriesApi.create(values)
      message.success('已创建')
      setOpen(false)
      form.resetFields()
      load()
    } catch (e: any) {
      if (e?.errorFields) return
      message.error(e?.message ?? '创建失败')
    }
  }

  const onDelete = async (code: string) => {
    try {
      const r = await industriesApi.remove(code)
      message.success(`已删除 ${r.deleted} 个行业节点`)
      load()
    } catch (e: any) {
      message.error(e?.message ?? '删除失败')
    }
  }

  return (
    <Card>
      <Space style={{ marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>行业管理</Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          新增行业
        </Button>
      </Space>
      <Table
        loading={loading}
        rowKey="code"
        dataSource={data}
        pagination={false}
        columns={[
          { title: '编码', dataIndex: 'code', width: 160 },
          { title: '名称', dataIndex: 'name', width: 200 },
          { title: '描述', dataIndex: 'description', ellipsis: true },
          {
            title: '企业数',
            dataIndex: 'company_count',
            width: 120,
            render: (v: number) => <Tag color={v ? 'blue' : 'default'}>{v}</Tag>,
          },
          {
            title: '操作',
            width: 120,
            render: (_, r) => (
              <Popconfirm title="确定删除？会同时移除其与企业的关联" onConfirm={() => onDelete(r.code)}>
                <Button type="link" danger>删除</Button>
              </Popconfirm>
            ),
          },
        ]}
      />

      <Modal
        open={open}
        title="新增行业"
        onCancel={() => setOpen(false)}
        onOk={onCreate}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item label="行业编码" name="code" rules={[{ required: true, message: '请填写编码' }]}>
            <Input placeholder="如：IT / FIN / MFG" />
          </Form.Item>
          <Form.Item label="行业名称" name="name" rules={[{ required: true, message: '请填写名称' }]}>
            <Input placeholder="如：信息技术" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}