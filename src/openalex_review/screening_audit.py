"""Exporta relatorio auditavel consolidado da triagem.

Combina decisoes, conflitos, resolucoes e status de leitura em CSV
para obra/etapa.
"""
from __future__ import annotations

import csv
from pathlib import Path

from .common import project_root


def export_screening_audit(root: Path | None = None, *, run_id: str | None = None) -> Path:
    base = root or project_root()
    db = base / "data" / "db" / "openalex.duckdb"
    if not db.is_file():
        raise FileNotFoundError(f"Banco DuckDB nao encontrado: {db}")
    import duckdb
    con = duckdb.connect(str(db), read_only=True)
    try:
        works = con.execute("SELECT record_key, openalex_id, doi, title FROM works").fetchall()
        decis = con.execute("SELECT d.record_key, d.stage, d.decision, d.reviewer, d.decided_at, d.exclusion_reason, d.notes FROM screening_decisions d").fetchall()
        resol = con.execute("SELECT record_key, stage, final_decision, resolver, resolved_at, notes FROM screening_resolutions").fetchall()
        leit = con.execute("SELECT record_key, priority, status, responsible, started_at, completed_at, note_path, notes FROM reading_status").fetchall()
    finally:
        con.close()
    dec_map = {}
    for rk, st, dec, rev, dt, exc, nt in decis:
        dec_map.setdefault((rk, st), []).append({"dec": dec, "rev": rev, "dt": dt, "exc": exc, "nt": nt})
    res_map = {}
    for rk, st, fdec, rslv, rdt, nt in resol:
        res_map[(rk, st)] = {"fdec": fdec, "rslv": rslv, "rdt": rdt, "nt": nt or ""}
    leit_map = {}
    for rk, pri, stt, resp, sdt, cdt, ntp, nt in leit:
        if rk not in leit_map:
            leit_map[rk] = {"pri": pri, "stt": stt, "resp": resp, "sdt": sdt, "cdt": cdt, "ntp": ntp, "nt": nt}
    header = ["record_key","openalex_id","doi","title","stage","decision","reviewer","decided_at","exclusion_reason","conflict_status","resolution_final_decision","resolution_resolver","resolution_resolved_at","reading_status","reading_priority","reading_responsible","reading_notes"]
    out_dir = base / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    run_label = run_id or "latest"
    rpt = out_dir / f"screening_audit_{run_label}.csv"
    rows = [header]
    for rk, oa, doi, tit in works:
        sts = {""}
        sts.update(s for s in [None] + [d[1] for d in decis if d[0]==rk] + [r[1] for r in resol if r[0]==rk] if s)
        sts.update(s for s in [rk] if rk in leit_map)
        for st in sorted(sts):
            dlist = dec_map.get((rk, st), [])
            rinfo = res_map.get((rk, st), {})
            leit_info = leit_map.get(rk, {"pri":"","stt":"","resp":"","sdt":"","cdt":"","ntp":"","nt":""})
            has_in = any(d["dec"]=="incluir" for d in dlist)
            has_ex = any(d["dec"]=="excluir" for d in dlist)
            conf = "sim" if (has_in and has_ex) else "nao"
            dec_row = next((d for d in dlist if d["dec"]=="incluir"), None)
            if not dec_row:
                dec_row = next((d for d in dlist if d["dec"]=="excluir"), dlist[-1] if dlist else {})
            decv = dec_row["dec"] if dec_row else ""
            revv = dec_row["rev"] if dec_row else ""
            dtv = dec_row["dt"] if dec_row else ""
            excv = dec_row["exc"] if dec_row else ""
            frdec = rinfo.get("fdec","")
            frslv = rinfo.get("rslv","")
            frdt = rinfo.get("rdt","")
            row = [rk, oa, doi, tit, st, decv, revv, dtv, excv, conf, frdec, frslv, frdt, leit_info["stt"], leit_info["pri"], leit_info["resp"], leit_info["nt"]]
            rows.append(row)
    with rpt.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)
    return rpt