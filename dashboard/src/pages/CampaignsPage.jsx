import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import Modal from "../components/Modal";
import { useNavigate } from "react-router-dom";

export default function CampaignsPage() {
  const nav = useNavigate();

  const [campaigns, setCampaigns] = useState([]);
  const [bots, setBots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const [open, setOpen] = useState(false);
  const [action, setAction] = useState("COMMENT"); // COMMENT | LIKE
  const [name, setName] = useState("");
  const [postUrl, setPostUrl] = useState("");
  const [commentText, setCommentText] = useState("");
  const [selectedBots, setSelectedBots] = useState([]);

  const activeBots = useMemo(
    () => bots.filter((b) => (b.status || "").toUpperCase() === "ACTIVE"),
    [bots]
  );

  async function loadAll() {
    setLoading(true);
    setErr("");
    try {
      const [camps, bs] = await Promise.all([
        api("/api/campaigns/"),
        api("/api/bots/"),
      ]);
      setCampaigns(camps);
      setBots(bs);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  function toggleBot(id) {
    setSelectedBots((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  function selectAllActive() {
    setSelectedBots(activeBots.map((b) => b.id));
  }

  function clearSelection() {
    setSelectedBots([]);
  }

  async function createCampaign() {
    setErr("");
    try {
      const payload = {
        name: name?.trim() || undefined,
        action,
        post_url: postUrl.trim(),
        ig_account_ids: selectedBots,
      };
      if (action === "COMMENT") payload.comment_text = commentText.trim();

      const res = await api("/api/campaigns/", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setOpen(false);
      setName("");
      setPostUrl("");
      setCommentText("");
      setSelectedBots([]);

      await loadAll();

      // ir al detalle
      if (res?.id) nav(`/campaigns/${res.id}`);
    } catch (e) {
      setErr(String(e.message || e));
    }
  }

  return (
    <div>
      <div className="row">
        <h2>Campañas</h2>
        <div>
          <button className="btn primary" onClick={() => setOpen(true)}>
            Nueva campaña
          </button>
          <button className="btn" onClick={loadAll} disabled={loading}>
            Refrescar
          </button>
        </div>
      </div>

      {err && <div className="alert">{err}</div>}
      {loading ? <div className="muted">Cargando...</div> : null}

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Acción</th>
              <th>Status</th>
              <th>Creada</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {campaigns.map((c) => (
              <tr key={c.id}>
                <td>{c.name || "(sin nombre)"}</td>
                <td>{c.action}</td>
                <td>
                  <span className={"badge " + (c.status || "").toLowerCase()}>
                    {c.status}
                  </span>
                </td>
                <td className="muted">{c.created_at || ""}</td>
                <td>
                  <button className="btn" onClick={() => nav(`/campaigns/${c.id}`)}>
                    Ver
                  </button>
                </td>
              </tr>
            ))}
            {campaigns.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  No hay campañas.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Modal open={open} title="Nueva campaña" onClose={() => setOpen(false)}>
        <div className="form">
          <label>Acción</label>
          <select value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="COMMENT">Comentarios</option>
            <option value="LIKE">Likes</option>
          </select>

          <label>Nombre (opcional)</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Campaña clientes enero" />

          <label>URL del post</label>
          <input
            value={postUrl}
            onChange={(e) => setPostUrl(e.target.value)}
            placeholder="https://www.instagram.com/p/XXXX/"
          />

          {action === "COMMENT" && (
            <>
              <label>Comentario</label>
              <textarea
                rows={4}
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                placeholder=" Comentario..."
              />
              <div className="muted">
                Tip: luego podemos generar comentario con IA por cuenta. Por ahora MVP: mismo texto.
              </div>
            </>
          )}

          <div className="card" style={{ marginTop: 0 }}>
            <div className="row">
              <div>
                <b>Seleccionar bots</b>{" "}
                <span className="muted">
                  ({selectedBots.length} seleccionados / {activeBots.length} activos)
                </span>
              </div>
              <div>
                <button className="btn" onClick={selectAllActive}>
                  Todos activos
                </button>
                <button className="btn" onClick={clearSelection}>
                  Limpiar
                </button>
              </div>
            </div>

            <div style={{ maxHeight: 260, overflow: "auto", marginTop: 10 }}>
              <table className="table">
                <thead>
                  <tr>
                    <th></th>
                    <th>Username</th>
                    <th>Status</th>
                    <th>Session</th>
                  </tr>
                </thead>
                <tbody>
                  {bots.map((b) => (
                    <tr key={b.id}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedBots.includes(b.id)}
                          onChange={() => toggleBot(b.id)}
                        />
                      </td>
                      <td>{b.username}</td>
                      <td className="muted">{b.status}</td>
                      <td className="muted">
                        {b.session_id ? "OK" : "VACÍA"}
                      </td>
                    </tr>
                  ))}
                  {bots.length === 0 && (
                    <tr>
                      <td colSpan={4} className="muted">
                        No hay bots. Cargalos primero en la pestaña Bots.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="row">
            <button
              className="btn primary"
              onClick={createCampaign}
              disabled={
                !postUrl.trim() ||
                selectedBots.length === 0 ||
                (action === "COMMENT" && !commentText.trim())
              }
            >
              Crear y enviar
            </button>
            <button className="btn" onClick={() => setOpen(false)}>
              Cancelar
            </button>
          </div>

          <div className="muted">
            Para procesar: asegurate de tener corriendo <code>python manage.py run_worker</code>.
          </div>
        </div>
      </Modal>
    </div>
  );
}
