import React from "react";
import { NavLink } from "react-router-dom";

export default function Layout({ children }) {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">SaaS IG</div>
        <nav>
          <NavLink to="/campaigns" className={({isActive}) => isActive ? "nav active" : "nav"}>
            Campañas
          </NavLink>
          <NavLink to="/bots" className={({isActive}) => isActive ? "nav active" : "nav"}>
            Bots
          </NavLink>
        </nav>
      </aside>

      <main className="main">
        <header className="header">
          <div className="title">Dashboard</div>
          <div className="hint">MVP</div>
        </header>
        <div className="content">{children}</div>
      </main>
    </div>
  );
}
