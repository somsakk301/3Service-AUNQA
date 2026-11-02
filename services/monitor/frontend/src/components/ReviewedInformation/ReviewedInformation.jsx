/**
 * What the reviewer is shown, subject by subject, exactly as the backend sent it (see `reviewedInformation`).
 * DISPLAY ONLY: nothing is judged here; a value the source lacks is "—".
 */
export function ReviewedInformation({ subjects }) {
  return (
    <ul className="subjects" data-testid="reviewed-information">
      {subjects.map((s, i) => (
        <li key={i} data-testid="reviewed-subject">
          <div className="subject-head">
            <span className="subject-name">{s.name}</span>
          </div>
          <dl className="meta">
            {s.rows.map((row, j) => (
              <div key={j}>
                <dt>{row.label}</dt>
                <dd>{row.value ?? "—"}</dd>
              </div>
            ))}
          </dl>
        </li>
      ))}
    </ul>
  );
}
