import React, { useEffect, useState } from "react";
import Modal from "../components/Modal";
import { api } from "../api/client";

export default function BotsPage() {
  const [bots, setBots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const [open, setOpen] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newSessionId, setNewSessionId] = useState("");

  async function load() {
    setLoading(true);
    setErr("");
    try {
      const data = await api("/api/bots/");
      setBots(data);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function createBot() {
    setErr("");
    try {
      await api("/api/bots/", {
        method: "POST",
        body: JSON.stringify({
          username: newUsername,
          session_id: newSessionId || "",
          status: "ACTIVE",
        }),
      });
      setOpen(false);
      setNewUsername("");
      setNewSessionId("");
      await load();
    } catch (e) {
      setErr(String(e.message || e));
    }
  }

  async function updateBot(id, patch) {
    setErr("");
    try {
      await api(`/api/bots/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      await load();
    } catch (e) {
      setErr(String(e.message || e));
    }
  }

  return (
    <div>
      <div className="row">
        <h2>Bots</h2>
        <div>
          <button className="btn primary" onClick={() => setOpen(true)}>Agregar bot</button>
          <button className="btn" onClick={load} disabled={loading}>Refrescar</button>
        </div>
      </div>

      {err && <div className="alert">{err}</div>}
      {loading ? <div>Cargando...</div> : null}

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Status</th>
              <th>Session</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {bots.map((b) => (
              <tr key={b.id}>
                <td>{b.username}</td>
                <td>
                  <span className={"badge " + (b.status || "").toLowerCase()}>{b.status}</span>
                </td>
                <td className="muted">
                  {b.session_id ? "OK" : "VACÍA"}
                </td>
                <td>
                  <button
                    className="btn"
                    onClick={() => updateBot(b.id, { status: b.status === "ACTIVE" ? "PAUSED" : "ACTIVE" })}
                  >
                    {b.status === "ACTIVE" ? "Pausar" : "Activar"}
                  </button>

                  <button
                    className="btn"
                    onClick={() => {
                      const val = prompt("Pegá session_id (cookie sessionid) aquí:");
                      if (val !== null) updateBot(b.id, { session_id: val.trim() });
                    }}
                  >
                    Pegar session_id
                  </button>
                </td>
              </tr>
            ))}
            {bots.length === 0 && (
              <tr><td colSpan={4} className="muted">No hay bots.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Modal open={open} title="Agregar bot" onClose={() => setOpen(false)}>
        <div className="form">
          <label>Username</label>
          <input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} placeholder="bot_1" />

          <label>Session ID (opcional)</label>
          <textarea
            rows={4}
            value={newSessionId}
            onChange={(e) => setNewSessionId(e.target.value)}
            placeholder="Pegá sessionid (cookie) aquí"
          />

          <div className="row">
            <button className="btn primary" onClick={createBot} disabled={!newUsername.trim()}>
              Crear
            </button>
            <button className="btn" onClick={() => setOpen(false)}>Cancelar</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
