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
              <th>Source</th>
              <th>Content</th>
              <th>Ingested</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id}>
                <td>{entry.id}</td>
                <td>{entry.source}</td>
                <td>{entry.content}</td>
                <td>{new Date(entry.ingestedAt).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
};

export default HomePage;
