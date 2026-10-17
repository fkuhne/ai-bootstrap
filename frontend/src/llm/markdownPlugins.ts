// A change to the Markdown tree before it's rendered.
import type { Root, RootContent } from 'mdast'

const LINE_BREAK = /^<br\s*\/?>$/i

// Raw HTML stays text, except a line break: models often separate lines with `<br>` inside a
// table's cells, where Markdown has no other way to, and it becomes a real line break.
export function remarkLineBreaks() {
  return (tree: Root) => {
    replaceBreaks(tree)
  }
}

function replaceBreaks(node: Root | RootContent): void {
  if (!('children' in node)) {
    return
  }
  // A break goes wherever raw HTML can, in a paragraph's text or a table's cell.
  const children = node.children as RootContent[]
  for (const [index, child] of children.entries()) {
    if (child.type === 'html' && LINE_BREAK.test(child.value)) {
      children[index] = { type: 'break' }
    } else {
      replaceBreaks(child)
    }
  }
}
