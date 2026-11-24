import type { ReactNode } from 'react'

/**
 * Простий Markdown карток уроку (docs/openapi.json, CardOut.body): `**жирний**`, `*курсив*`,
 * рядок `## ` — заголовок, рядки `- ` — список, рядки `1. ` — нумерований список, порожній
 * рядок — новий абзац. Усе інше (зокрема HTML) показується як звичайний текст: розмітку
 * перетворюємо на React-елементи, без dangerouslySetInnerHTML.
 */

type Block =
  | { kind: 'heading'; text: string }
  | { kind: 'paragraph'; lines: string[] }
  | { kind: 'list'; ordered: boolean; items: string[] }

const HEADING = /^#{1,6}\s+(.*)$/
const BULLET = /^[-*]\s+(.*)$/
const NUMBERED = /^\d{1,3}[.)]\s+(.*)$/

function parseBlocks(source: string): Block[] {
  const blocks: Block[] = []
  let paragraph: string[] | null = null
  let list: Extract<Block, { kind: 'list' }> | null = null

  const close = () => {
    paragraph = null
    list = null
  }

  for (const raw of source.replace(/\r\n?/g, '\n').split('\n')) {
    const line = raw.trim()
    if (line === '') {
      close()
      continue
    }
    const heading = HEADING.exec(line)
    if (heading) {
      close()
      blocks.push({ kind: 'heading', text: heading[1] ?? '' })
      continue
    }
    const bullet = BULLET.exec(line)
    const numbered = bullet ? null : NUMBERED.exec(line)
    const item = bullet ?? numbered
    if (item) {
      const ordered = numbered !== null
      if (!list || list.ordered !== ordered) {
        paragraph = null
        list = { kind: 'list', ordered, items: [] }
        blocks.push(list)
      }
      list.items.push(item[1] ?? '')
      continue
    }
    if (!paragraph) {
      list = null
      paragraph = []
      blocks.push({ kind: 'paragraph', lines: paragraph })
    }
    paragraph.push(line)
  }
  return blocks
}

// Жирний — подвійні зірочки; курсив — одинарні, без пробілу одразу після відкривної.
const INLINE = /\*\*(.+?)\*\*|\*([^*\s](?:[^*]*?[^*\s])?)\*/g

function inline(text: string, key: string): ReactNode[] {
  const nodes: ReactNode[] = []
  let last = 0
  let n = 0
  for (const match of text.matchAll(INLINE)) {
    const start = match.index
    if (start > last) nodes.push(text.slice(last, start))
    const id = `${key}-${n++}`
    if (match[1] !== undefined) {
      nodes.push(
        <strong key={id} className="font-bold text-parchment">
          {inline(match[1], id)}
        </strong>,
      )
    } else {
      nodes.push(<em key={id}>{match[2]}</em>)
    }
    last = start + match[0].length
  }
  if (last < text.length) nodes.push(text.slice(last))
  return nodes
}

/** Текст картки з простою розміткою. className — для кольору й розміру основного тексту. */
export default function Markdown({ text, className = '' }: { text: string; className?: string }) {
  const blocks = parseBlocks(text)
  if (blocks.length === 0) return null

  return (
    <div className={`flex flex-col gap-3 break-words ${className}`}>
      {blocks.map((block, i) => {
        const key = `b${i}`
        if (block.kind === 'heading') {
          return (
            <h3 key={key} className="pt-1 text-xl leading-7 font-bold text-parchment">
              {inline(block.text, key)}
            </h3>
          )
        }
        if (block.kind === 'list') {
          const List = block.ordered ? 'ol' : 'ul'
          return (
            <List
              key={key}
              className={`flex flex-col gap-1.5 pl-6 ${block.ordered ? 'list-decimal' : 'list-disc'} marker:text-accent`}
            >
              {block.items.map((item, j) => (
                <li key={j} className="pl-1">
                  {inline(item, `${key}-${j}`)}
                </li>
              ))}
            </List>
          )
        }
        return (
          <p key={key}>
            {block.lines.map((line, j) => (
              <span key={j}>
                {j > 0 && <br />}
                {inline(line, `${key}-${j}`)}
              </span>
            ))}
          </p>
        )
      })}
    </div>
  )
}
