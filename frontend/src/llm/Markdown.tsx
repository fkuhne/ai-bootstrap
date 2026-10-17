// Text written in Markdown, as answers are, rendered as React elements: raw HTML stays text and is
// never run, except `<br>`, a line break.
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import styles from './Markdown.module.css'
import { remarkLineBreaks } from './markdownPlugins'

const PLUGINS = [remarkGfm, remarkLineBreaks]

const COMPONENTS: Components = {
  // A link opens in a new tab, so the conversation stays where it was.
  a: ({ node: _node, children, ...props }) => (
    <a {...props} target="_blank" rel="noreferrer">
      {children}
    </a>
  ),
}

export function Markdown({ text }: { text: string }) {
  return (
    <div className={styles.markdown}>
      <ReactMarkdown remarkPlugins={PLUGINS} components={COMPONENTS}>
        {text}
      </ReactMarkdown>
    </div>
  )
}
