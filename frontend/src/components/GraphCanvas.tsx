import { useEffect, useRef } from 'react'
import cytoscape from 'cytoscape'
import coseBilkent from 'cytoscape-cose-bilkent'
import type { GraphData, GraphNode } from '../types'

// 注册 cose-bilkent 布局（适合企业关系图，力导向 + 避免重叠）
cytoscape.use(coseBilkent)

interface Props {
  data: GraphData
  height?: number | string
  onNodeClick?: (node: GraphNode) => void
}

const TYPE_COLORS: Record<string, string> = {
  SUPPLIES: '#1677ff',
  PURCHASES_FROM: '#13c2c2',
  COMPETES_WITH: '#f5222d',
  PARTNER_OF: '#52c41a',
  SUBSIDIARY_OF: '#722ed1',
  INVESTED_BY: '#fa8c16',
  CUSTOMER_OF: '#eb2f96',
}

// 给节点分配颜色：根据所属行业 code 哈希到 AntD 调色板
function colorOfIndustry(code?: string | null): string {
  if (!code) return '#8c8c8c'
  let hash = 0
  for (let i = 0; i < code.length; i++) hash = (hash * 31 + code.charCodeAt(i)) >>> 0
  const palette = [
    '#1677ff', '#13c2c2', '#52c41a', '#fa8c16', '#722ed1',
    '#eb2f96', '#f5222d', '#a0d911', '#2f54eb', '#08979c',
  ]
  return palette[hash % palette.length]
}

export default function GraphCanvas({ data, height = 'calc(100vh - 200px)', onNodeClick }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const cy = cytoscape({
      container: containerRef.current,
      elements: [
        ...data.nodes.map((n) => ({
          data: {
            id: n.id,
            label: n.name,
            industry_code: n.industry_code ?? null,
            industry_name: n.industry_name ?? null,
            color: colorOfIndustry(n.industry_code),
          },
        })),
        ...data.edges.map((e) => ({
          data: {
            id: e.id,
            source: e.source,
            target: e.target,
            label: e.type,
            color: TYPE_COLORS[e.type] ?? '#8c8c8c',
          },
        })),
      ],
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            'label': 'data(label)',
            'color': '#fff',
            'font-size': 12,
            'text-valign': 'center',
            'text-halign': 'center',
            'text-outline-color': '#000',
            'text-outline-width': 2,
            'width': 70,
            'height': 70,
            'border-width': 2,
            'border-color': '#fff',
          },
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
            'color': '#333',
            'text-background-color': '#fff',
            'text-background-opacity': 0.8,
            'text-background-padding': 2,
          },
        },
      ],
      layout: { name: 'cose-bilkent', animate: false } as any,
      minZoom: 0.2,
      maxZoom: 3,
      wheelSensitivity: 0.2,
    })
    cyRef.current = cy

    cy.on('tap', 'node', (evt) => {
      const node = evt.target
      if (onNodeClick) {
        onNodeClick({
          id: node.id(),
          name: node.data('label'),
          industry_code: node.data('industry_code'),
          industry_name: node.data('industry_name'),
        })
      }
    })

    return () => {
      cy.destroy()
      cyRef.current = null
    }
    // data 变化时整体重建（节点/边数量一般不会特别大，重建最简单稳定）
  }, [data])

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