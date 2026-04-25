import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary caught", error, info);
  }

  handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          className="flex min-h-screen items-center justify-center bg-bg-base text-text-primary"
        >
          <div className="max-w-md rounded-md border border-border-subtle bg-bg-elevated p-6 shadow">
            <h1 className="font-display text-lg font-semibold mb-2">
              Something went wrong
            </h1>
            <p className="text-sm text-text-secondary mb-4">
              An unexpected error occurred. Please reload the page to continue.
            </p>
            <button
              type="button"
              onClick={this.handleReload}
              className="rounded-md bg-accent-primary px-3 py-1.5 text-sm font-medium text-accent-on"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
