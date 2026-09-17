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
  const [connStatus, setConnStatus] = useState<{
    configured: boolean
    connected: boolean
    error?: string
  } | null>(null)

  const refreshStatus = async () => {
    try {
      setConnStatus(await settingsApi.status())
    } catch {
      setConnStatus(null)
    }
  }

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
      refreshStatus()
    }
  }

  useEffect(() => {
    loadCurrent()
    // 定期刷新状态（数据库可能因外部原因掉线）
    const timer = setInterval(refreshStatus, 15000)
    return () => clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /** 提取后端错误信息（axios 抛错时通常在 e.response.data.detail）。 */
  const extractError = (e: any): string => {
    const detail = e?.response?.data?.detail
    if (detail) return typeof detail === 'string' ? detail : JSON.stringify(detail)
    return e?.message || '未知错误'
  }

  const onTest = async () => {
    // 仅校验 uri/user/database 三项；密码对"测试连接"是可选的
    const requiredKeys = ['uri', 'user', 'database'] as const
    let values: Partial<Neo4jSettingsIn> = {}
    try {
      values = await form.validateFields(requiredKeys as unknown as [])
    } catch {
      message.error('请先补全带 * 号的必填项')
      return
    }
    if (!values.password) {
      if (current?.password_set) {
        // 已存在保存的密码，使用后端已存储的密码（接口允许空密码做"用旧密码"测试）
        values.password = ''
      } else {
        message.warning('尚未保存任何密码，请先填写密码再测试')
        return
      }
    }
    setTesting(true)
    setTestResult(null)
    try {
      const r = await settingsApi.test(values as Neo4jSettingsIn)
      setTestResult(r)
      if (r.ok) {
        message.success('连接成功')
      } else {
        message.error(`连接失败：${r.error ?? '请检查地址、端口、账号密码'}`)
      }
    } catch (e: any) {
      const msg = extractError(e)
      setTestResult({ ok: false, error: msg })
      message.error(`测试请求失败：${msg}`)
    } finally {
      setTesting(false)
      refreshStatus()
    }
  }

  const onSave = async () => {
    let values: Neo4jSettingsIn
    try {
      values = await form.validateFields()
    } catch {
      message.error('请先补全带 * 号的必填项')
      return
    }
    if (!values.password) {
      message.warning('保存配置必须填写密码（即使数据库本身没设密码）')
      return
    }
    try {
      const saved = await settingsApi.save(values)
      setCurrent(saved)
      message.success('配置已保存，Neo4j 客户端已重载')
      onConfigured?.()
      refreshStatus()
    } catch (e: any) {
      message.error(`保存失败：${extractError(e)}`)
    }
  }

  /** 渲染顶部"实时连接状态"卡片 */
  const renderStatusAlert = () => {
    if (connStatus === null) return null
    if (!connStatus.configured) {
      return (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="尚未配置 Neo4j"
          description="请填写下方的连接信息并保存"
        />
      )
    }
    if (connStatus.connected) {
      return (
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 16 }}
          message="数据库已连接"
          description="当前保存的 Neo4j 配置可用，无需重新连接"
        />
      )
    }
    return (
      <Alert
        type="error"
        showIcon
        style={{ marginBottom: 16 }}
        message="数据库不可达"
        description={
          connStatus.error ||
          '后端尝试连接已保存的 Neo4j 配置失败，请检查地址/账号密码/数据库是否启动'
        }
      />
    )
  }

  return (
    <Spin spinning={loading}>
      {renderStatusAlert()}

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
          <Form.Item
            label="用户名"
            name="user"
            rules={[{ required: true, message: '请填写用户名' }]}
          >
            <Input placeholder="neo4j" />
          </Form.Item>
          <Form.Item
            label="密码"
            name="password"
            extra={
              current?.password_set
                ? '已设置密码。留空可使用已保存的密码进行测试，但保存必填'
                : '测试连接和保存都需要填写'
            }
          >
            <Input.Password placeholder="neo4j" />
          </Form.Item>
          <Form.Item
            label="默认数据库"
            name="database"
            rules={[{ required: true, message: '请填写数据库名' }]}
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
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {testResult.error || '未知错误'}
                </pre>
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
  const [aiStatus, setAiStatus] = useState<{
    configured: boolean
    provider?: string
    model?: string
  } | null>(null)

  const refreshStatus = async () => {
    try {
      setAiStatus(await settingsApi.aiStatus())
    } catch {
      setAiStatus(null)
    }
  }

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
        extra: (cfg.extra ?? {}) as any,
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
      refreshStatus()
    }
  }

  useEffect(() => {
    loadCurrent()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 切换 provider 时自动填充 base_url / model
  const onProviderChange = (p: string) => {
    const preset = PROVIDER_PRESETS[p]
    if (preset) {
      form.setFieldsValue({ base_url: preset.base_url, model: preset.model })
    }
  }

  const extractError = (e: any): string => {
    const detail = e?.response?.data?.detail
    if (detail) return typeof detail === 'string' ? detail : JSON.stringify(detail)
    return e?.message || '未知错误'
  }

  const onTest = async () => {
    const requiredKeys = ['provider', 'base_url', 'model'] as const
    let values: Partial<AISettingsIn> = {}
    try {
      values = await form.validateFields(requiredKeys as unknown as [])
    } catch {
      message.error('请先补全带 * 号的必填项')
      return
    }
    if (!values.api_key) {
      if (current?.api_key_set) {
        values.api_key = ''
      } else {
        message.warning('尚未保存任何 API Key，请先填写再测试（本地 Ollama 可填占位符）')
        return
      }
    }
    setTesting(true)
    setTestResult(null)
    try {
      const r = await settingsApi.aiTest(values as AISettingsIn)
      setTestResult(r)
      if (r.ok) {
        message.success(`连通成功，模型回复：${r.reply ?? ''}`)
      } else {
        message.error(`连通失败：${r.error ?? '请检查 Base URL / API Key / 模型名'}`)
      }
    } catch (e: any) {
      const msg = extractError(e)
      setTestResult({ ok: false, error: msg })
      message.error(`测试请求失败：${msg}`)
    } finally {
      setTesting(false)
    }
  }

  const onSave = async () => {
    let values: AISettingsIn
    try {
      values = await form.validateFields()
    } catch {
      message.error('请先补全带 * 号的必填项')
      return
    }
    if (!values.api_key) {
      message.warning('保存配置必须填写 API Key')
      return
    }
    try {
      const saved = await settingsApi.aiSave(values)
      setCurrent(saved)
      message.success('AI 配置已保存')
      refreshStatus()
    } catch (e: any) {
      message.error(`保存失败：${extractError(e)}`)
    }
  }

  const renderStatusAlert = () => {
    if (aiStatus === null) return null
    if (!aiStatus.configured) {
      return (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="尚未配置 AI 服务"
          description="未配置时，企业 AI 补全按钮将不可用"
        />
      )
    }
    return (
      <Alert
        type="success"
        showIcon
        style={{ marginBottom: 16 }}
        message={`AI 服务已配置：${aiStatus.provider ?? ''} / ${aiStatus.model ?? ''}`}
      />
    )
  }

  return (
    <Spin spinning={loading}>
      {renderStatusAlert()}

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
          <Form.Item
            label="服务商"
            name="provider"
            rules={[{ required: true, message: '请选择服务商' }]}
          >
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
          <Form.Item
            label="模型"
            name="model"
            rules={[{ required: true, message: '请填写模型名' }]}
          >
            <Input placeholder="gpt-4o-mini" />
          </Form.Item>
          <Form.Item
            label="API Key"
            name="api_key"
            extra={
              current?.api_key_set
                ? '已设置 Key。留空可使用已保存的 Key 进行测试，但保存必填'
                : '测试连通和保存都需要填写'
            }
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
            description={
              testResult.ok ? (
                <>模型回复：<code>{testResult.reply}</code></>
              ) : (
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {testResult.error || '未知错误'}
                </pre>
              )
            }
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