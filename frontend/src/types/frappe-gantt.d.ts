declare module 'frappe-gantt' {
  export interface FrappeTask {
    id: string
    name: string
    start: string
    end: string
    progress: number
    dependencies?: string
    custom_class?: string
  }

  export interface FrappeGanttOptions {
    view_mode: string
    language?: string
    popup_on?: 'click' | 'hover'
    view_modes?: string[]
    on_date_change?: (task: FrappeTask, start: Date, end: Date) => void
    on_progress_change?: (task: FrappeTask, progress: number) => void
    popup?: (context: { task: FrappeTask; get_title: () => string; get_details: () => string }) => string
  }

  export default class Gantt {
    constructor(element: HTMLElement, tasks: FrappeTask[], options: FrappeGanttOptions)
    refresh(tasks: FrappeTask[]): void
    change_view_mode(mode: string): void
    hide_popup(): void
  }
}
