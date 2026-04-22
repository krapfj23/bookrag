// Renders a dismissible "connection lost" alert. Shown by polling loops after
// N consecutive network failures so transient blips don't surface, but a real
// outage does. Caller controls visibility; component has no internal state.
export function ConnectionBanner({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <div role="alert" aria-label="Connection lost" className="connection-banner">
      Connection lost. Retrying…
    </div>
  );
}
