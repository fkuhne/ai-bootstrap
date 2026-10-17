// What a module gives the web UI's shell, so its pages plug in through one list,
// `src/modules/index.ts` (docs/foundations.md#the-web-ui). The shell shows a module while the
// backend has it on, as `GET /api/modules` says.
import type { ComponentType, ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

export interface SidebarProps {
  // Something was chosen in the sidebar: a drawer closes.
  readonly onChoose: () => void
}

export interface UiModule {
  // The backend module it shows, by the name `GET /api/modules` gives it.
  readonly name: string
  // Its entry in the sidebar.
  readonly title: string
  readonly icon: LucideIcon
  // Where its pages are: `/<path>` and below.
  readonly path: string
  // Its pages, under its path: it routes within it, by relative paths.
  readonly Page: ComponentType
  // What it adds to the sidebar while one of its pages is open.
  readonly Sidebar?: ComponentType<SidebarProps>
  // State its page and its sidebar share, wrapped around the whole shell.
  readonly Provider?: ComponentType<{ readonly children: ReactNode }>
  // The modules whose page this one replaces when both are on.
  readonly replaces?: readonly string[]
}

// The modules to show: those the backend has on, less any another one replaces, in the list's
// order.
export function visibleModules(
  modules: readonly UiModule[],
  on: readonly string[],
): readonly UiModule[] {
  const listed = modules.filter((module) => on.includes(module.name))
  const replaced = new Set(listed.flatMap((module) => module.replaces ?? []))
  return listed.filter((module) => !replaced.has(module.name))
}
