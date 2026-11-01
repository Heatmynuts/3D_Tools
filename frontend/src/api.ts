import type { Credits, Meta, ORModel, ProjectState, ProjectSummary, Selection, Usage, Version } from './types'

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* not JSON */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

const post = <T>(path: string, body: unknown = {}) => call<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  fabricationProfiles: () => call<Record<string, string[]>>('/fabrication/profiles'),
  generateCad: (pid: string, body: { remarks?: string; parent_id?: string; params?: Record<string, number> }) => post<ProjectState>(`/projects/${pid}/cad`, body),
  validateCad: (pid: string, rid: string) => post<ProjectState>(`/projects/${pid}/cad/${rid}/validate`),
  sliceCad: (pid: string, rid: string, body: { machine: string; process: string; filament: string; bed_type: string }) => post<ProjectState>(`/projects/${pid}/cad/${rid}/slice`, body),
  validateSlice: (pid: string, rid: string, sid: string) => post<ProjectState>(`/projects/${pid}/cad/${rid}/slices/${sid}/validate`),
  meta: () => call<Meta>('/meta'),
  projects: () => call<ProjectSummary[]>('/projects'),
  models: () => call<ORModel[]>('/models'),
  credits: () => call<Credits>('/credits'),
  usage: (pid: string) => call<Usage>(`/projects/${pid}/usage`),
  createProject: (prompt: string, b_model?: string | null) => post<ProjectState>('/projects', { prompt, b_model: b_model ?? null }),
  project: (pid: string) => call<ProjectState>(`/projects/${pid}`),
  deleteProject: (pid: string) => call<{ ok: string }>(`/projects/${pid}`, { method: 'DELETE' }),
  version: (pid: string, vid: string) => call<Version>(`/projects/${pid}/versions/${vid}`),
  answer: (
    pid: string,
    body: { kind: string; text: string; option_id?: string | null; selection?: Selection | null; b_model?: string | null },
  ) => post<ProjectState>(`/projects/${pid}/answer`, body),
  choose: (pid: string, candidate_id: string) => post<ProjectState>(`/projects/${pid}/choose`, { candidate_id }),
  discard: (pid: string, batch_id: string) => post<ProjectState>(`/projects/${pid}/discard`, { batch_id }),
  startParallel: (pid: string, batch_id: string) => post<ProjectState>(`/projects/${pid}/parallel/start`, { batch_id }),
  trackAnswer: (pid: string, tid: string, body: { kind: string; text: string; option_id?: string | null }) =>
    post<ProjectState>(`/projects/${pid}/tracks/${tid}/answer`, body),
  chooseTrack: (pid: string, tid: string) => post<ProjectState>(`/projects/${pid}/tracks/${tid}/choose`),
  plan: (pid: string, remarks?: string, b_model?: string | null) =>
    post<ProjectState>(`/projects/${pid}/plan`, { remarks: remarks ?? null, b_model: b_model ?? null }),
  validatePlan: (pid: string) => post<ProjectState>(`/projects/${pid}/plan/validate`),
  checkout: (pid: string, version_id: string, branch?: string) =>
    post<ProjectState>(`/projects/${pid}/head`, { version_id, branch: branch ?? null }),
  duplicate: (pid: string, version_id: string) => post<ProjectState>(`/projects/${pid}/duplicate`, { version_id }),
}
