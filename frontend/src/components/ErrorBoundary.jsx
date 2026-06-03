import { Component } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'

/**
 * Capture les erreurs de rendu d'une page et affiche un message ciblé
 * au lieu de laisser tout l'app devenir un écran blanc.
 * Se réinitialise automatiquement au changement de page (prop `resetKey`).
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary a capturé une erreur :', error, info)
  }

  componentDidUpdate(prevProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.hasError) {
      this.setState({ hasError: false, error: null })
    }
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', minHeight: '60vh', gap: 16, textAlign: 'center',
        padding: 24,
      }}>
        <div style={{
          width: 56, height: 56, borderRadius: '50%',
          background: 'var(--red-dim)', border: '1px solid var(--red)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <AlertTriangle size={26} color="var(--red)" />
        </div>
        <div style={{
          fontFamily: 'var(--font-display)', fontSize: 16,
          color: 'var(--red)', letterSpacing: '0.05em',
        }}>
          ERREUR D'AFFICHAGE DE CETTE PAGE
        </div>
        <div style={{
          fontFamily: 'var(--font-mono)', fontSize: 11,
          color: 'var(--text-muted)', maxWidth: 520, lineHeight: 1.6,
        }}>
          Le reste de l'application reste fonctionnel — changez de page dans le menu,
          ou rechargez cette vue.
        </div>
        {this.state.error?.message && (
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 10,
            color: 'var(--text-dim)', background: 'var(--bg-elevated)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            padding: '8px 12px', maxWidth: 520, overflowWrap: 'anywhere',
          }}>
            {String(this.state.error.message)}
          </div>
        )}
        <button
          className="btn btn-primary"
          onClick={() => this.setState({ hasError: false, error: null })}
        >
          <RotateCcw size={14} />
          Réessayer
        </button>
      </div>
    )
  }
}
