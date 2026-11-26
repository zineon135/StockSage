import { Component, type ReactNode } from 'react'

/** Keeps one broken panel from blanking the whole app. */
export class ErrorBoundary extends Component<{ children: ReactNode; resetKey?: string }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) { return { error } }
  componentDidUpdate(prev: { resetKey?: string }) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null })
  }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="card p-6 text-sm">
        <div className="font-semibold text-ink">Something went wrong displaying this section.</div>
        <div className="mt-1 text-xs text-muted">{this.state.error.message}</div>
        <button onClick={() => this.setState({ error: null })} className="mt-3 rounded-lg border border-line px-3 py-1.5 text-xs text-ink-2 hover:text-ink">Try again</button>
      </div>
    )
  }
}
