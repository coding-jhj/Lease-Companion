interface StateMessageProps {
  title: string;
  description: string;
}

export function LoadingState({ title, description }: StateMessageProps) {
  return (
    <div className="state-panel state-panel--loading" role="status" aria-live="polite">
      <span className="state-icon spinner" aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
    </div>
  );
}

interface ErrorStateProps extends StateMessageProps {
  onRetry: () => void;
}

export function ErrorState({ title, description, onRetry }: ErrorStateProps) {
  return (
    <div className="state-panel state-panel--error" role="alert">
      <span className="state-icon" aria-hidden="true">!</span>
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
        <button className="inline-button" type="button" onClick={onRetry}>다시 시도</button>
      </div>
    </div>
  );
}

export function EmptyState({ title, description }: StateMessageProps) {
  return (
    <div className="state-panel state-panel--empty" role="status">
      <span className="state-icon" aria-hidden="true">○</span>
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
    </div>
  );
}
