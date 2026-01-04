import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { Link } from "react-router-dom";
import Modal from "../components/Modal";

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState([]);
  const [bots, setBots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const [open, setOpen] = useState(false);
  const [postUrl, setPostUrl] = useState("");
  const [action, setAction] = useState("COMMENT");
  const [comment, setComment] = useState("🔥 Excelente post!");
  const [selectedBotIds, setSelectedBotIds] = useState([]);

  const activeBots = useMemo(() => bots.filter(b => b.status === "ACTIVE"), [bots]);

  async function load() {
    setLoading(true);
    setErr("");
    try {
      const [c, b] = await Promise.all([
        api("/api/campaigns/"),
        api("/api/bots/"),
      ]);
      setCampaigns(c);
      setBots(b);
      if (selectedBotIds.length === 0) {
        setSelectedBotIds(b.filter(x => x.status === "ACTIVE").slice(0, 5).map(x => x.id));
      }
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function toggleBot(id) {
    setSelectedBotIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  }

  async function createCampaign() {
    setErr("");
    try {
      // Endpoint recomendado: crea campaign + tasks en un request
      const created = await api("/api/campaigns/", {
        method: "POST",
        body: JSON.stringify({
          action,
          post_url: postUrl,
          comment_text: comment,
          ig_account_ids: selectedBotIds,
          mode: "SAFE",
        }),
      });
      setOpen(false);
      setPostUrl("");
      await load();
      // si el backend devuelve id
      if (created?.id) window.location.href = `/campaigns/${created.id}`;
    } catch (e) {
      setErr(String(e.message || e));
    }
  }

  return (
    <div>
      <div className="row">
        <h2>Campañas</h2>
        <div>
          <button className="btn primary" onClick={() => setOpen(true)}>Crear campaña</button>
          <button className="btn" onClick={load} disabled={loading}>Refrescar</button>
        </div>
      </div>

      {err && <div className="alert">{err}</div>}
      {loading ? <div>Cargando...</div> : null}

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Nombre/ID</th>
              <th>Acción</th>
              <th>Status</th>
              <th>Creada</th>
            </tr>
          </thead>
          <tbody>
            {campaigns.map((c) => (
              <tr key={c.id}>
                <td>
                  <Link to={`/campaigns/${c.id}`}>{c.name || c.id}</Link>
                </td>
                <td>{c.action}</td>
                <td><span className={"badge " + (c.status || "").toLowerCase()}>{c.status}</span></td>
                <td className="muted">{c.created_at || "-"}</td>
              </tr>
            ))}
            {campaigns.length === 0 && (
              <tr><td colSpan={4} className="muted">No hay campañas.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Modal open={open} title="Crear campaña" onClose={() => setOpen(false)}>
        <div className="form">
          <label>URL del post</label>
          <input value={postUrl} onChange={(e) => setPostUrl(e.target.value)} placeholder="https://www.instagram.com/p/XXXX/" />

          <label>Acción</label>
          <select value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="COMMENT">COMMENT</option>
            <option value="LIKE">LIKE</option>
          </select>

          {action === "COMMENT" && (
            <>
              <label>Comentario</label>
              <textarea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} />
            </>
          )}

          <label>Bots (activos: {activeBots.length})</label>
          <div className="botPicker">
            {activeBots.map((b) => (
              <label key={b.id} className="botPick">
                <input
                  type="checkbox"
                  checked={selectedBotIds.includes(b.id)}
                  onChange={() => toggleBot(b.id)}
                />
                <span>{b.username}</span>
              </label>
            ))}
            {activeBots.length === 0 && <div className="muted">No hay bots ACTIVE.</div>}
          </div>

          <div className="row">
            <button className="btn primary" onClick={createCampaign} disabled={!postUrl.trim() || selectedBotIds.length === 0}>
              Crear y encolar
            </button>
            <button className="btn" onClick={() => setOpen(false)}>Cancelar</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
