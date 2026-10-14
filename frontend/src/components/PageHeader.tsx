export default function PageHeader({ title, description, action }: { title: string; description?: string; action?: React.ReactNode }) {
  return <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div><h1 className="text-3xl font-bold tracking-tight text-slate-950">{title}</h1>{description && <p className="mt-1 text-sm text-slate-500">{description}</p>}</div>{action}</div>
}
