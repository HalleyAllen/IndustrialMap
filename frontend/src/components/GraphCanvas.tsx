import { useEffect, useRef } from 'react'
import cytoscape from 'cytoscape'
import coseBilkent from 'cytoscape-cose-bilkent'
import type {
  ChainGraphData,
  ChainGraphNode,
  GraphData,
  GraphNode,
  ThemeRef,
} from '../types'
import { relationTypeLabel } from '../types'

// 注册 cose-bilkent 布局（适合企业关系图，力导向 + 避免重叠）
cytoscape.use(coseBilkent)

interface Props {
  /** 关系图数据（默认模式） */
  data?: GraphData
  /** 产业链分层图数据（chain 模式） */
  chainData?: ChainGraphData
  height?: number | string
  onNodeClick?: (node: GraphNode | ChainGraphNode) => null | undefined | void
}

const RELATION_COLORS: Record<string, string> = {
  SUPPLIES: '#1677ff',
  PURCHASES_FROM: '#13c2c2',
  COMPETES_WITH: '#f5222d',
  PARTNER_OF: '#52c41a',
  SUBSIDIARY_OF: '#722ed1',
  INVESTED_BY: '#fa8c16',
  CUSTOMER_OF: '#eb2f96',
  HAS_STAGE: '#94a3b8',
  UPSTREAM_OF: '#0ea5e9',
  IN_STAGE: '#64748b',
}

// 没有主题时的默认色
const DEFAULT_NODE_COLOR = '#8c8c8c'

// 节点配色：用「第一个主题」的颜色作为填充色，没有则用灰色
// 同时把其他主题色作为边框的彩色环（最多 3 个），便于一眼看出"多主题"企业。
function pickColors(themes: ThemeRef[]): { fill: string; borders: string[] } {
  if (!themes || themes.length === 0) {
    return { fill: DEFAULT_NODE_COLOR, borders: [] }
  }
  return {
    fill: themes[0].color || DEFAULT_NODE_COLOR,
    borders: themes.slice(1, 3).map((t) => t.color || DEFAULT_NODE_COLOR),
  }
}

export default function GraphCanvas({
  data,
  chainData,
  height = 'calc(100vh - 200px)',
  onNodeClick,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)

  // 判断模式
  const isChainMode = !!chainData

  useEffect(() => {
    if (!containerRef.current) return
    const cy = cytoscape({
      container: containerRef.current,
      elements: isChainMode
        ? buildChainElements(chainData!)
        : buildGraphElements(data!),
      style: buildStyle(),
      layout: isChainMode
        ? ({
            name: 'breadthfirst',
            directed: true,
            spacingFactor: 1.5,
            padding: 30,
            avoidOverlap: true,
            grid: false,
            // 按 node.data('level') 分层
            transform: (node: any, position: any) => {
              // 强制按 level 分层
              const lvl = node.data('level') ?? 0
              return { x: position.x, y: lvl * 140 + 80 }
            },
          } as any)
        : ({ name: 'cose-bilkent', animate: false } as any),
      minZoom: 0.2,
      maxZoom: 3,
      wheelSensitivity: 0.2,
    })
    cyRef.current = cy

    cy.on('tap', 'node', (evt) => {
      const node = evt.target
      if (!onNodeClick) return
      if (isChainMode) {
        const label = node.data('label')
        const isCompany = label === 'Company'
        onNodeClick({
          id: node.id(),
          label,
          name: node.data('labelText') || node.id(),
          stage_code: node.data('stage_code') ?? null,
          themes: node.data('themes') ?? [],
          level: node.data('level') ?? null,
          // GraphNode 兼容字段：company 节点用 name 当 name；其他节点也用 labelText
        } as any)
        // 简化：只透 company 节点时把 name 设成显示名
        if (isCompany) {
          ;(onNodeClick as any)({
            id: node.id(),
            name: node.data('displayName') || node.id(),
            themes: node.data('themes') ?? [],
          })
        } else {
          ;(onNodeClick as any)({
            id: node.id(),
            label,
            name: node.data('displayName') || node.id(),
            stage_code: node.data('stage_code') ?? null,
            themes: [],
          })
        }
      } else {
        onNodeClick({
          id: node.id(),
          name: node.data('label'),
          themes: node.data('themes') ?? [],
        })
      }
    })

    return () => {
      cy.destroy()
      cyRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, chainData, isChainMode])

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height,
        border: '1px solid #f0f0f0',
        borderRadius: 6,
        background: '#fafafa',
      }}
    />
  )
}

// ============== 元素构造（默认模式） ==============

function buildGraphElements(data: GraphData): cytoscape.ElementDefinition[] {
  return [
    ...data.nodes.map((n) => {
      const colors = pickColors(n.themes ?? [])
      return {
        data: {
          id: n.id,
          label: n.name,
          themes: n.themes ?? [],
          fillColor: colors.fill,
          borderColors: colors.borders,
          borderWidth: Math.min(8, 2 + colors.borders.length * 2),
        },
      }
    }),
    ...data.edges.map((e) => ({
      data: {
        id: e.id,
        source: e.source,
        target: e.target,
        label: relationTypeLabel(e.type),
        color: RELATION_COLORS[e.type] ?? '#8c8c8c',
      },
    })),
  ]
}

// ============== 元素构造（产业链分层模式） ==============

function buildChainElements(
  data: ChainGraphData,
): cytoscape.ElementDefinition[] {
  const chainColor = data.chain.color || '#0ea5e9'
  return [
    ...data.nodes.map((n) => {
      const isChain = n.label === 'Chain'
      const isStage = n.label === 'Stage'
      const isCompany = n.label === 'Company'

      // 配色规则
      let fill = DEFAULT_NODE_COLOR
      let border = '#fff'
      let textColor = '#fff'
      if (isChain) {
        fill = chainColor
        border = '#fff'
        textColor = '#fff'
      } else if (isStage) {
        fill = '#fbbf24' // 阶段用琥珀色高亮
        border = '#fff'
        textColor = '#1f2937'
      } else if (isCompany) {
        const colors = pickColors(n.themes)
        fill = colors.fill
        border = '#fff'
        textColor = '#fff'
      }

      return {
        data: {
          id: n.id,
          label: n.label,
          displayName: n.name,
          level: n.level ?? 0,
          stage_code: n.stage_code ?? null,
          themes: n.themes ?? [],
          fillColor: fill,
          borderColor: border,
          textColor,
          isChain,
          isStage,
          isCompany,
          borderWidth: isCompany ? Math.min(8, 2 + n.themes.length * 2) : 3,
        },
      }
    }),
    ...data.edges.map((e) => ({
      data: {
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.label || e.type,
        color: RELATION_COLORS[e.type] ?? '#94a3b8',
      },
    })),
  ]
}

// ============== Cytoscape 样式 ==============

function buildStyle(): cytoscape.Stylesheet[] {
  return [
    {
      selector: 'node',
      style: {
        'background-color': 'data(fillColor)',
        'border-color': 'data(borderColor)',
        'border-width': 'data(borderWidth)',
        'color': 'data(textColor)',
        'label': 'data(displayName)',
        'font-size': 12,
        'text-valign': 'center',
        'text-halign': 'center',
        'text-outline-color': '#000',
        'text-outline-width': 2,
        'text-wrap': 'wrap',
        'text-max-width': '120px',
        'width': '70px',
        'height': '70px',
      } as any,
    },
    {
      selector: 'node[label = "Chain"]',
      style: {
        'shape': 'round-rectangle',
        'width': '120px',
        'height': '50px',
        'font-size': 14,
        'font-weight': 600,
      } as any,
    },
    {
      selector: 'node[label = "Stage"]',
      style: {
        'shape': 'round-rectangle',
        'width': '130px',
        'height': '46px',
        'font-size': 13,
        'font-weight': 600,
      } as any,
    },
    {
      selector: 'node[label = "Company"]',
      style: {
        'shape': 'ellipse',
      } as any,
    },
    {
      selector: 'node:selected',
      style: {
        'border-color': '#faad14',
        'border-width': 4,
      },
    },
    {
      selector: 'edge',
      style: {
        'curve-style': 'bezier',
        'target-arrow-shape': 'triangle',
        'width': 2,
        'line-color': 'data(color)',
        'target-arrow-color': 'data(color)',
        'label': 'data(label)',
        'font-size': 10,
        'color': '#475569',
        'text-background-color': '#fff',
        'text-background-opacity': 0.8,
        'text-background-padding': '2px',
      } as any,
    },
    {
      selector: 'edge[type = "UPSTREAM_OF"]',
      style: {
        'width': 3,
        'curve-style': 'bezier',
      } as any,
    },
    {
      selector: 'edge[type = "HAS_STAGE"]',
      style: {
        'line-style': 'dashed',
      } as any,
    },
  ]
}