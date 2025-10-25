import useLogEntries from "../hooks/useLogEntries";

const HomePage = () => {
  const { entries, isLoading, error, refresh } = useLogEntries();

  return (
    <section className="page">
      <header className="page-header">
        <h1>Log Entries</h1>
        <button type="button" onClick={() => refresh()} disabled={isLoading}>
          Refresh
        </button>
      </header>

      {error && <p className="error">{error}</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <table className="log-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Timestamp</th>
              <th>Level</th>
              <th>Area</th>
              <th>Action</th>
              <th>Node</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id}>
                <td>{entry.id}</td>
                <td>
                  {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : "—"}
                </td>
                <td>{entry.level}</td>
                <td>{entry.area}</td>
                <td>{entry.action}</td>
                <td>{entry.source}</td>
                <td>
                  <code>{JSON.stringify(entry.details)}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
};
