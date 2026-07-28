import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { error: Error | null };

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Error en la aplicación:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="login-wrap">
          <div className="login-card">
            <h1>Error al cargar</h1>
            <p className="sub">La página no pudo iniciarse correctamente.</p>
            <p className="error">{this.state.error.message}</p>
            <button type="button" onClick={() => window.location.reload()}>
              Recargar
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
