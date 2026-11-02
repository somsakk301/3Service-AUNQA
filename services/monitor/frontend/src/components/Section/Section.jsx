/** A titled box on the PS detail page. */
export function Section({ id, title, testId, children }) {
  return (
    <section id={id} className="box" aria-labelledby={`${id}-h`} data-testid={testId}>
      <h2 id={`${id}-h`}>{title}</h2>
      {children}
    </section>
  );
}
