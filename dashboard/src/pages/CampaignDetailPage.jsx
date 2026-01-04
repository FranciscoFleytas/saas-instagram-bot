import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";

export default function CampaignDetailPage() {
  const { id } = useParams();
  const [campaign, setCampaign] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [err, setErr] = useState("");

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
    load();
    const timer = setInterval(load, 3000); // polling cada 3s
    return () => clearInterval(timer);
  }, [id]);

  const stats = useMemo(() => {
    const by = { PENDING: 0, IN_PROGRESS: 0, SUCCESS: 0, RETRY: 0, ERROR: 0 };
    for (const t of tasks) by[t.status] = (by[t.status] || 0) + 1;
    return by;
  }, [tasks]);

  return (
    <div>
      <div className="row">
        <h2>Campaña</h2>
        <button className="btn" onClick={load}>Refrescar</button>
      </div>

      {err && <div className="alert">{err}</div>}
      {!campaign ? <div>Cargando...</div> : (
        <div className="card">
          <div className="kpis">
            <div><div className="kpiLabel">Status</div><div className="kpiValue">{campaign.status}</div></div>
            <div><div className="kpiLabel">SUCCESS</div><div className="kpiValue">{stats.SUCCESS}</div></div>
            <div><div className="kpiLabel">RETRY</div><div className="kpiValue">{stats.RETRY}</div></div>
            <div><div className="kpiLabel">ERROR</div><div className="kpiValue">{stats.ERROR}</div></div>
            <div><div className="kpiLabel">PENDING</div><div className="kpiValue">{stats.PENDING}</div></div>
          </div>
        </div>
      )}

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Bot</th>
              <th>Acción</th>
              <th>Status</th>
              <th>Attempts</th>
              <th>Mensaje</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.id}>
                <td>{t.ig_account_username || t.ig_account}</td>
                <td>{t.action}</td>
                <td><span className={"badge " + (t.status || "").toLowerCase()}>{t.status}</span></td>
                <td>{t.attempts}</td>
                <td className="muted">{t.result_message || t.error_code || "-"}</td>
              </tr>
            ))}
            {tasks.length === 0 && (
              <tr><td colSpan={5} className="muted">No hay tasks.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
