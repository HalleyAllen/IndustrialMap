import { useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Descriptions,
  Modal,
  Radio,
  Result,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import { importApi } from '../api/client'
import type {
  ImportCommitResult,
  ImportIssueRow,
  ImportNewRow,
  ImportPreview,
  OnDuplicate,
  Theme,
} from '../types'
import { ON_DUPLICATE_LABELS } from '../types'

interface Props {
  open: boolean
  themes: Theme[]
  onClose: () => void
  /** 导入成功后通知父组件刷新列表 */
  onImported: () => void
}

const DELIMITER_LABELS: Record<string, string> = {
  ',': '逗号 ,',
  '\t': '制表符 Tab',
  ';': '分号 ;',
  '|': '竖线 |',
}

export default function ImportCompaniesModal({ open, themes, onClose, onImported }: Props) {
  // 0 = 上传与配置，1 = 自检报告，2 = 导入结果
  const [step, setStep] = useState(0)
  const [file, setFile] = useState<File | null>(null)
  const [defaultSlugs, setDefaultSlugs] = useState<string[]>([])
  const [onDuplicate, setOnDuplicate] = useState<OnDuplicate>('skip')
  const [readThemeColumn, setReadThemeColumn] = useState(true)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [result, setResult] = useState<ImportCommitResult | null>(null)
  const [loading, setLoading] = useState(false)

  const extractError = (e: any): string => {
    const detail = e?.response?.data?.detail
    if (detail) return typeof detail === 'string' ? detail : JSON.stringify(detail)
    return e?.message || '未知错误'
  }

  const reset = () => {
    setStep(0)
    setFile(null)
    setDefaultSlugs([])
    setOnDuplicate('skip')
    setReadThemeColumn(true)
    setPreview(null)
    setResult(null)
    setLoading(false)
  }

  const handleClose = () => {
    if (loading) return
    onClose()
    reset()
  }

  const handlePreview = async () => {
    if (!file) {
      message.warning('请先选择要导入的文件')
      return
    }
    setLoading(true)
    try {
      const p = await importApi.preview(file, defaultSlugs, onDuplicate, readThemeColumn)
      setPreview(p)
      setStep(1)
      if (p.total_rows === 0) {
        message.warning('未解析到任何数据行，请检查文件格式')
      }
    } catch (e: any) {
      message.error(`自检失败：${extractError(e)}`)
    } finally {
      setLoading(false)
    }
  }

  const handleCommit = async () => {
    if (!file) return
    setLoading(true)
    try {
      const r = await importApi.commit(file, defaultSlugs, onDuplicate, readThemeColumn)
      setResult(r)
      setStep(2)
      onImported()
      if (r.created || r.updated) {
        message.success(`导入完成：新增 ${r.created}，更新 ${r.updated}`)
      } else {
        message.info('没有需要写入的数据')
      }
    } catch (e: any) {
      message.error(`导入失败：${extractError(e)}`)
    } finally {
      setLoading(false)
    }
  }

  const themeOptions = themes.map((t) => ({
    value: t.slug,
    label: `${t.icon ? `${t.icon} ` : ''}${t.name}（${t.slug}）`,
  }))

  const renderThemeTags = (ts: { slug: string; name: string; color: string; icon: string }[]) =>
    ts && ts.length > 0 ? (
      <Space wrap size={[4, 4]}>
        {ts.map((t) => (
          <Tag key={t.slug} color={t.color} style={{ borderRadius: 10, margin: 0 }}>
            {t.icon ? `${t.icon} ` : ''}
            {t.name}
          </Tag>
        ))}
      </Space>
    ) : (
      <Typography.Text type="secondary">—</Typography.Text>
    )

  const newColumns = [
    { title: '行号', dataIndex: 'line', width: 70 },
    { title: '企业名称', dataIndex: 'name', ellipsis: true },
    {
      title: '将挂载主题',
      dataIndex: 'theme_slugs',
      width: 340,
      render: (slugs: string[], r: ImportNewRow) => {
        if (!slugs || slugs.length === 0) return <Tag>未分类</Tag>
        return (
          <Space wrap size={[4, 4]}>
            {slugs.map((s) => {
              const t = themes.find((x) => x.slug === s)
              return (
                <Tag key={s} color={t?.color} style={{ borderRadius: 10, margin: 0 }}>
                  {t ? `${t.icon ? `${t.icon} ` : ''}${t.name}` : s}
                </Tag>
              )
            })}
          </Space>
        )
      },
    },
  ]

  const conflictColumns = [
    { title: '行号', dataIndex: 'line', width: 70 },
    { title: '企业名称', dataIndex: 'name', ellipsis: true },
    {
      title: '现有主题',
      dataIndex: 'existing_themes',
      width: 320,
      render: (ts: ImportIssueRow['existing_themes']) => renderThemeTags(ts),
    },
    {
      title: '处理方式',
      width: 200,
      render: () => <Typography.Text type="secondary">{ON_DUPLICATE_LABELS[onDuplicate]}</Typography.Text>,
    },
  ]

  const fileDupColumns = [
    { title: '行号', dataIndex: 'line', width: 70 },
    { title: '企业名称', dataIndex: 'name', ellipsis: true },
    {
      title: '首次出现行',
      dataIndex: 'first_line',
      width: 110,
      render: (v: number | null) => (v ? `第 ${v} 行` : '—'),
    },
    { title: '说明', dataIndex: 'reason' },
  ]

  const invalidColumns = [
    { title: '行号', dataIndex: 'line', width: 70 },
    { title: '企业名称', dataIndex: 'name', ellipsis: true },
    { title: '原因', dataIndex: 'reason' },
  ]

  const tabItems = preview
    ? [
        {
          key: 'new',
          label: `可导入 ${preview.new_count}`,
          children: (
            <Table
              size="small"
              rowKey="line"
              dataSource={preview.new_rows}
              columns={newColumns as any}
              pagination={{ pageSize: 8, size: 'small', showSizeChanger: false }}
              locale={{ emptyText: '没有可导入的新企业' }}
            />
          ),
        },
        {
          key: 'conflict',
          label: `库内重复 ${preview.conflict_count}`,
          children: (
            <Table
              size="small"
              rowKey="line"
              dataSource={preview.conflicts}
              columns={conflictColumns as any}
              pagination={{ pageSize: 8, size: 'small', showSizeChanger: false }}
              locale={{ emptyText: '没有与库中重复的企业' }}
            />
          ),
        },
        {
          key: 'filedup',
          label: `文件内重复 ${preview.file_dup_count}`,
          children: (
            <Table
              size="small"
              rowKey="line"
              dataSource={preview.file_dups}
              columns={fileDupColumns as any}
              pagination={{ pageSize: 8, size: 'small', showSizeChanger: false }}
              locale={{ emptyText: '文件内没有重复行' }}
            />
          ),
        },
        {
          key: 'invalid',
          label: `无效行 ${preview.invalid_count}`,
          children: (
            <Table
              size="small"
              rowKey="line"
              dataSource={preview.invalid_rows}
              columns={invalidColumns as any}
              pagination={{ pageSize: 8, size: 'small', showSizeChanger: false }}
              locale={{ emptyText: '没有无效行' }}
            />
          ),
        },
      ]
    : []

  const footer =
    step === 0
      ? [
          <Button key="cancel" onClick={handleClose} disabled={loading}>
            取消
          </Button>,
          <Button key="preview" type="primary" loading={loading} onClick={handlePreview}>
            开始自检
          </Button>,
        ]
      : step === 1
        ? [
            <Button key="back" onClick={() => setStep(0)} disabled={loading}>
              返回修改
            </Button>,
            <Button
              key="commit"
              type="primary"
              loading={loading}
              disabled={!preview || preview.importable_count === 0}
              onClick={handleCommit}
            >
              确认导入 {preview?.importable_count ? `(${preview.importable_count} 条)` : ''}
            </Button>,
          ]
        : [
            <Button key="done" type="primary" onClick={handleClose}>
              完成
            </Button>,
          ]

  return (
    <Modal
      open={open}
      title="批量导入企业"
      width={980}
      onCancel={handleClose}
      footer={footer}
      maskClosable={false}
      destroyOnClose
    >
      {step === 0 && (
        <>
          <Upload.Dragger
            accept=".csv,.txt"
            maxCount={1}
            beforeUpload={(f) => {
              setFile(f)
              return false
            }}
            onRemove={() => {
              setFile(null)
              return true
            }}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽 CSV / TXT 文件到此处</p>
            <p className="ant-upload-hint">
              第 1 列为<b>企业名称</b>（必填）；第 2 列可选，填<b>主题</b>（slug 或中文名，
              多个用 <code>|</code> <code>;</code> <code>、</code> 分隔）。
              编码支持 UTF-8 / GB18030，分隔符自动识别。
            </p>
          </Upload.Dragger>

          <div style={{ marginTop: 16 }}>
            <Typography.Text strong>默认主题（可选，应用于所有行）</Typography.Text>
            <Select
              mode="multiple"
              allowClear
              style={{ width: '100%', marginTop: 6 }}
              placeholder="不选则只使用文件第 2 列中的主题"
              options={themeOptions}
              value={defaultSlugs}
              onChange={setDefaultSlugs}
            />
          </div>

          <div style={{ marginTop: 16 }}>
            <Checkbox checked={readThemeColumn} onChange={(e) => setReadThemeColumn(e.target.checked)}>
              读取第 2 列作为该企业的主题
            </Checkbox>
          </div>

          <div style={{ marginTop: 16 }}>
            <Typography.Text strong>遇到库中已存在的同名企业时</Typography.Text>
            <Radio.Group
              style={{ display: 'block', marginTop: 8 }}
              value={onDuplicate}
              onChange={(e) => setOnDuplicate(e.target.value)}
            >
              <Space direction="vertical">
                <Radio value="skip">{ON_DUPLICATE_LABELS.skip}</Radio>
                <Radio value="update">{ON_DUPLICATE_LABELS.update}</Radio>
                <Radio value="overwrite">{ON_DUPLICATE_LABELS.overwrite}</Radio>
              </Space>
            </Radio.Group>
          </div>

          <Alert
            style={{ marginTop: 16 }}
            type="info"
            showIcon
            message="点击「开始自检」只会做检查，不会写入数据库；确认报告无误后再点「确认导入」。"
          />
        </>
      )}

      {step === 1 && preview && (
        <>
          <Descriptions size="small" column={4} style={{ marginBottom: 12 }}>
            <Descriptions.Item label="文件">{preview.file_name || '—'}</Descriptions.Item>
            <Descriptions.Item label="编码">{preview.encoding}</Descriptions.Item>
            <Descriptions.Item label="分隔符">
              {DELIMITER_LABELS[preview.delimiter] ?? preview.delimiter}
            </Descriptions.Item>
            <Descriptions.Item label="表头">
              {preview.header_skipped ? '已识别并跳过' : '未检测到'}
            </Descriptions.Item>
          </Descriptions>

          <Row gutter={12} style={{ marginBottom: 12 }}>
            <Col span={4}>
              <Card size="small">
                <Statistic title="解析行数" value={preview.total_rows} />
              </Card>
            </Col>
            <Col span={4}>
              <Card size="small">
                <Statistic
                  title="将写入"
                  value={preview.importable_count}
                  valueStyle={{ color: '#3f8600' }}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card size="small">
                <Statistic
                  title="库内重复"
                  value={preview.conflict_count}
                  valueStyle={{ color: preview.conflict_count ? '#cf1322' : undefined }}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card size="small">
                <Statistic
                  title="文件内重复"
                  value={preview.file_dup_count}
                  valueStyle={{ color: preview.file_dup_count ? '#d46b08' : undefined }}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card size="small">
                <Statistic
                  title="无效行"
                  value={preview.invalid_count}
                  valueStyle={{ color: preview.invalid_count ? '#cf1322' : undefined }}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card size="small">
                <Statistic
                  title="库内重名组"
                  value={preview.db_dup_names}
                  valueStyle={{ color: preview.db_dup_names ? '#d46b08' : undefined }}
                />
              </Card>
            </Col>
          </Row>

          {preview.notes.length > 0 && (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 12 }}
              message="需要注意"
              description={
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {preview.notes.map((n, i) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              }
            />
          )}

          <Tabs items={tabItems} />
        </>
      )}

      {step === 2 && result && (
        <Result
          status={result.failed ? 'warning' : 'success'}
          title="导入完成"
          subTitle={`耗时 ${result.duration_ms} ms`}
          extra={
            <Space size="large">
              <Statistic title="新增企业" value={result.created} valueStyle={{ color: '#3f8600' }} />
              <Statistic title="更新企业" value={result.updated} />
              <Statistic title="跳过" value={result.skipped} />
              <Statistic
                title="失败"
                value={result.failed}
                valueStyle={{ color: result.failed ? '#cf1322' : undefined }}
              />
              <Statistic title="新增主题关联" value={result.themes_linked} />
            </Space>
          }
        />
      )}
    </Modal>
  )
}
