import { useEffect, useState } from 'react'
import {
  Card,
  Form,
  Input,
  InputNumber,
  Button,
  Space,
  Typography,
  Alert,
  Descriptions,
  message,
  Spin,
  Tabs,
  Select,
} from 'antd'
import { settingsApi } from '../api/client'
import type {
  AISettingsIn,
  AISettingsOut,
  AITestResult,
  Neo4jSettingsIn,
  Neo4jSettingsOut,
  Neo4jTestResult,
} from '../types'

interface Props {
  onConfigured?: () => void
}

// 常见 LLM provider 预设（兼容 OpenAI /chat/completions 协议）
const PROVIDER_PRESETS: Record<string, { base_url: string; model: string }> = {
  openai: { base_url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  deepseek: { base_url: 'https://api.deepseek.com', model: 'deepseek-chat' },
  qwen: { base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-turbo' },
  zhipu: { base_url: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' },
  ollama: { base_url: 'http://localhost:11434/v1', model: 'llama3.2' },
  custom: { base_url: '', model: '' },
}

export default function SettingsPage({ onConfigured }: Props) {
  return (
    <>
      <Typography.Title level={3}>系统配置</Typography.Title>
      <Typography.Paragraph type="secondary">
        配置数据库连接与 AI 服务。所有用户共享同一份。
      </Typography.Paragraph>
      <Tabs
        defaultActiveKey="neo4j"
        items={[
          {
            key: 'neo4j',
            label: 'Neo4j 数据库',
            children: <Neo4jPanel onConfigured={onConfigured} />,
          },
          {
            key: 'ai',
            label: 'AI 服务',
            children: <AIPanel />,
          },
        ]}
      />
    </>
  )
}

// ============================================================
// Neo4j 配置
// ============================================================
function Neo4jPanel({ onConfigured }: { onConfigured?: () => void }) {
  const [form] = Form.useForm<Neo4jSettingsIn>()
  const [current, setCurrent] = useState<Neo4jSettingsOut | null>(null)
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<Neo4jTestResult | null>(null)

  const loadCurrent = async () => {
    setLoading(true)
    try {
      const cfg = await settingsApi.get()
      setCurrent(cfg)
      form.setFieldsValue({
        uri: cfg.uri,
        user: cfg.user,
        database: cfg.database,
        password: '',
      })
    } catch {
      setCurrent(null)
      form.setFieldsValue({
        uri: 'bolt://localhost:7687',
        user: 'neo4j',
        password: '',
        database: 'neo4j',
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCurrent()
  }, [])

  const onTest = async () => {
    try {
      const values = await form.validateFields()
      setTesting(true)
      setTestResult(null)
      const r = await settingsApi.test(values)
      setTestResult(r)
      r.ok ? message.success('连接成功') : message.error(r.error ?? '连接失败')
    } catch {
      /* form error */
    } finally {
      setTesting(false)
    }
  }

  const onSave = async () => {
    try {
      const values = await form.validateFields()
      if (!values.password) {
        message.warning('保存配置需要填写密码')
        return
      }
      const saved = await settingsApi.save(values)
      setCurrent(saved)
      message.success('配置已保存，Neo4j 客户端已重载')
      onConfigured?.()
    } catch (e: any) {
      message.error(e?.message ?? '保存失败')
    }
  }

  return (
    <Spin spinning={loading}>
      <Card>
        <Form form={form} layout="vertical">
          <Form.Item
            label="Bolt URI"
            name="uri"
            rules={[{ required: true, message: '请填写 Bolt 地址' }]}
            extra="如 bolt://localhost:7687 或 neo4j+s://xxx.databases.neo4j.io:7687"
          >
            <Input placeholder="bolt://localhost:7687" />
          </Form.Item>
          <Form.Item label="用户名" name="user" rules={[{ required: true }]}>
            <Input placeholder="neo4j" />
          </Form.Item>
          <Form.Item
            label="密码"
            name="password"
            rules={[{ required: true, message: '请填写密码' }]}
            extra={current?.password_set ? '已设置密码，保存时如留空将不被允许' : undefined}
          >
            <Input.Password placeholder="neo4j" />
          </Form.Item>
          <Form.Item
            label="默认数据库"
            name="database"
            rules={[{ required: true }]}
            extra="默认 neo4j；若使用多库可填具体库名"
          >
            <Input placeholder="neo4j" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button onClick={onTest} loading={testing}>测试连接</Button>
              <Button type="primary" onClick={onSave}>保存配置</Button>
            </Space>
          </Form.Item>
        </Form>

        {testResult && (
          <Alert
            style={{ marginTop: 16 }}
            type={testResult.ok ? 'success' : 'error'}
            showIcon
            message={testResult.ok ? '连接成功' : '连接失败'}
            description={
              testResult.ok ? (
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="组件">{testResult.name}</Descriptions.Item>
                  <Descriptions.Item label="版本">{testResult.versions?.join(', ')}</Descriptions.Item>
                  <Descriptions.Item label="版本类型">{testResult.edition}</Descriptions.Item>
                </Descriptions>
              ) : (
                testResult.error
              )
            }
          />
        )}
      </Card>

      {current && (
        <Card style={{ marginTop: 16 }} title="当前生效配置">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="URI">{current.uri}</Descriptions.Item>
            <Descriptions.Item label="用户">{current.user}</Descriptions.Item>
            <Descriptions.Item label="数据库">{current.database}</Descriptions.Item>
            <Descriptions.Item label="密码">{'●'.repeat(8)}（已设置）</Descriptions.Item>
            <Descriptions.Item label="更新时间">{current.updated_at}</Descriptions.Item>
          </Descriptions>
        </Card>
      )}
    </Spin>
  )
}

// ============================================================
// AI 配置
// ============================================================
function AIPanel() {
  const [form] = Form.useForm<AISettingsIn>()
  const [current, setCurrent] = useState<AISettingsOut | null>(null)
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<AITestResult | null>(null)

  const loadCurrent = async () => {
    setLoading(true)
    try {
      const cfg = await settingsApi.aiGet()
      setCurrent(cfg)
      form.setFieldsValue({
        provider: cfg.provider,
        base_url: cfg.base_url,
        api_key: '',
        model: cfg.model,
        temperature: cfg.temperature,
        extra: cfg.extra ?? {},
      })
    } catch {
      setCurrent(null)
      form.setFieldsValue({
        provider: 'openai',
        base_url: PROVIDER_PRESETS.openai.base_url,
        api_key: '',
        model: PROVIDER_PRESETS.openai.model,
        temperature: 0.3,
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCurrent()
  }, [])

  // 切换 provider 时自动填充 base_url / model
  const onProviderChange = (p: string) => {
    const preset = PROVIDER_PRESETS[p]
    if (preset) {
      form.setFieldsValue({ base_url: preset.base_url, model: preset.model })
    }
  }

  const onTest = async () => {
    try {
      const values = await form.validateFields()
      setTesting(true)
      setTestResult(null)
      const r = await settingsApi.aiTest(values)
      setTestResult(r)
      r.ok ? message.success('连通成功') : message.error(r.error ?? '连通失败')
    } catch {
      /* form error */
    } finally {
      setTesting(false)
    }
  }

  const onSave = async () => {
    try {
      const values = await form.validateFields()
      if (!values.api_key) {
        message.warning('保存配置需要填写 API Key')
        return
      }
      const saved = await settingsApi.aiSave(values)
      setCurrent(saved)
      message.success('AI 配置已保存')
    } catch (e: any) {
      message.error(e?.message ?? '保存失败')
    }
  }

  return (
    <Spin spinning={loading}>
      <Card>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="兼容 OpenAI Chat Completions 协议的 LLM 都可使用"
          description="支持 OpenAI / DeepSeek / 通义千问 / 智谱 / Ollama / 自建网关等。本地 Ollama 时 api_key 可填占位符（如 ollama）。"
        />
        <Form form={form} layout="vertical" onValuesChange={(changed) => {
          if (changed.provider) onProviderChange(changed.provider)
        }}>
          <Form.Item label="服务商" name="provider" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'openai', label: 'OpenAI' },
                { value: 'deepseek', label: 'DeepSeek' },
                { value: 'qwen', label: '通义千问（DashScope）' },
                { value: 'zhipu', label: '智谱 AI' },
                { value: 'ollama', label: 'Ollama（本地）' },
                { value: 'custom', label: '自定义 / 自建网关' },
              ]}
            />
          </Form.Item>
          <Form.Item
            label="Base URL"
            name="base_url"
            rules={[{ required: true, message: '请填写 Base URL' }]}
            extra="形如 https://api.openai.com/v1，拼接 /chat/completions 后访问"
          >
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item label="模型" name="model" rules={[{ required: true }]}>
            <Input placeholder="gpt-4o-mini" />
          </Form.Item>
          <Form.Item
            label="API Key"
            name="api_key"
            rules={[{ required: true, message: '请填写 API Key' }]}
            extra={current?.api_key_set ? '已设置 Key，保存时如留空将不被允许' : undefined}
          >
            <Input.Password placeholder="sk-..." />
          </Form.Item>
          <Form.Item label="Temperature" extra="0 = 精确，1 = 发散；默认 0.3">
            <Form.Item name="temperature" noStyle>
              <InputNumber min={0} max={2} step={0.1} style={{ width: 120 }} />
            </Form.Item>
          </Form.Item>
          <Form.Item>
            <Space>
              <Button onClick={onTest} loading={testing}>测试连通</Button>
              <Button type="primary" onClick={onSave}>保存配置</Button>
            </Space>
          </Form.Item>
        </Form>

        {testResult && (
          <Alert
            style={{ marginTop: 16 }}
            type={testResult.ok ? 'success' : 'error'}
            showIcon
            message={testResult.ok ? '连通成功' : '连通失败'}
            description={testResult.ok ? `模型回复：${testResult.reply}` : testResult.error}
          />
        )}
      </Card>

      {current && (
        <Card style={{ marginTop: 16 }} title="当前生效 AI 配置">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="服务商">{current.provider}</Descriptions.Item>
            <Descriptions.Item label="Base URL">{current.base_url}</Descriptions.Item>
            <Descriptions.Item label="模型">{current.model}</Descriptions.Item>
            <Descriptions.Item label="Temperature">{current.temperature}</Descriptions.Item>
            <Descriptions.Item label="API Key">{'●'.repeat(8)}（已设置）</Descriptions.Item>
            <Descriptions.Item label="更新时间">{current.updated_at}</Descriptions.Item>
          </Descriptions>
        </Card>
      )}
    </Spin>
  )
}