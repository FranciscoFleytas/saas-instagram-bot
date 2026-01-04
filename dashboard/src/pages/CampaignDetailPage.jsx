import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { useParams } from "react-router-dom";

export default function CampaignDetailPage() {
  const { id } = useParams();

  const [campaign, setCampaign] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setErr("");
    try {
      const [c, t] = await Promise.all([
        api(`/api/campaigns/${id}/`),
        api(`/api/tasks/?campaign_id=${id}`),
      ]);
      setCampaign(c);
      setTasks(t);
    } catch (e) {
      setErr(String(e.message || e));
    }
  }

  useEffect(() => {
    let alive = true;
    setLoading(true);
    load().finally(() => alive && setLoading(false));

    const timer = setInterval(() => {
      if (!alive) return;
      load();
    }, 2500);

    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [id]);

  const stats = useMemo(() => {
    const s = { PENDING: 0, IN_PROGRESS: 0, DONE: 0, FAILED: 0, RETRY: 0, OTHER: 0 };
    for (const t of tasks) {
      const st = (t.status || "").toUpperCase();
      if (s[st] !== undefined) s[st] += 1;
      else s.OTHER += 1;
    }
    return s;
  }, [tasks]);

  return (
    <div>
      <div className="row">
        <h2>Detalle campaña</h2>
        <button className="btn" onClick={load}>
          Refrescar
        </button>
      </div>

      {err && <div className="alert">{err}</div>}
      {loading && <div className="muted">Cargando...</div>}

      <div className="card">
        <div className="row">
          <div>
            <div style={{ fontWeight: 700, fontSize: 18 }}>
              {campaign?.name || "(sin nombre)"}
            </div>
            <div className="muted">
              Acción: {campaign?.action} • Status: {campaign?.status} • ID: {id}
            </div>
          </div>

          <div className="row" style={{ justifyContent: "flex-end" }}>
            <span className="badge pending">PENDING {stats.PENDING}</span>
            <span className="badge in_progress">IN_PROGRESS {stats.IN_PROGRESS}</span>
            <span className="badge success">DONE {stats.DONE}</span>
            <span className="badge error">FAILED {stats.FAILED}</span>
            <span className="badge retry">RETRY {stats.RETRY}</span>
          </div>
        </div>
      </div>

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Bot</th>
              <th>Status</th>
              <th>Intentos</th>
              <th>Resultado</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.id}>
                <td>{t.ig_account_username || t.ig_account_id}</td>
                <td>
                  <span className={"badge " + (t.status || "").toLowerCase()}>
                    {t.status}
                  </span>
                </td>
                <td className="muted">{t.attempts}</td>
                <td className="muted">{t.result_message || ""}</td>
                <td className="muted">{t.error_code || ""}</td>
              </tr>
            ))}
            {tasks.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  No hay tasks todavía. (Si la campaña se creó, deberían aparecer.)
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <div className="muted" style={{ marginTop: 10 }}>
          Actualización automática cada 2.5s. Para ejecutar: <code>python manage.py run_worker</code>.
        </div>
      </div>
    </div>
  );
}
