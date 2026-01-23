import { render } from 'preact'
import './index.css'
import { App } from './app.tsx'
import { ErrorBoundary } from './components/ErrorBoundary'

render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>,
  document.getElementById('app')!
)
