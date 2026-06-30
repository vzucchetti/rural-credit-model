import gzip
import os
import tempfile
import shutil
from datetime import datetime

from src.utils.io import duckdb_mem
from src.utils.logging import get_logger
from src.utils.minio_client import get_client, ensure_bucket, list_objects
from src.utils.orchestration import _freq_match


log = get_logger("sicor_transform")


def _detect_encoding(raw_tmp: str, key: str, sample: int = 1 << 20) -> str:
    opener = gzip.open if key.endswith(".gz") else open
    with opener(raw_tmp, "rb") as fh:
        data = fh.read(sample)
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError as e:
        if e.start >= len(data) - 3:
            return "utf-8"
    return "cp1252"


def _resolve_encoding(raw_tmp: str, key: str, tbl: dict, scfg: dict) -> str:
    return tbl.get("encoding") or scfg.get("encoding") or _detect_encoding(raw_tmp, key)


def _download_and_transcode(client, bronze, key, tbl=None, scfg=None):
    tbl = tbl or {}
    scfg = scfg or {}
    fd, raw_tmp = tempfile.mkstemp(suffix=".raw")
    os.close(fd)
    client.fget_object(bronze, key, raw_tmp)
    enc = _resolve_encoding(raw_tmp, key, tbl, scfg)
    fd, csv_tmp = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    opener = gzip.open if key.endswith(".gz") else open
    with opener(raw_tmp, "rt", encoding=enc, errors="replace") as fin, open(
        csv_tmp, "w", encoding="utf-8", newline=""
    ) as fout:
        shutil.copyfileobj(fin, fout, length=1 << 20)
    try:
        os.unlink(raw_tmp)
    except OSError:
        pass
    return csv_tmp, enc


def _sniff_delim(csv_path: str, candidates=(",", ";", "\t", "|")) -> str:
    with open(csv_path, "r", encoding="utf-8", errors="replace") as fh:
        header = fh.readline()
    counts = {c: header.count(c) for c in candidates}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def _resolve_delim(csv_tmp: str, tbl: dict, scfg: dict) -> str:
    return tbl.get("delimiter") or scfg.get("delimiter") or _sniff_delim(csv_tmp)


def _read_raw(con, csv_tmp: str, delim: str, explicit: bool) -> list[str]:
    con.execute("DROP TABLE IF EXISTS raw")
    d = delim.replace("'", "''")
    if explicit:
        sql = (
            "CREATE TABLE raw AS SELECT * FROM read_csv('" + csv_tmp + "', "
            "delim='" + d + "', header=true, quote='\"', escape='\"', "
            "all_varchar=true, auto_detect=false)"
        )
    else:
        sql = (
            "CREATE TABLE raw AS SELECT * FROM read_csv('" + csv_tmp + "', "
            "delim='" + d + "', all_varchar=true, auto_detect=true)"
        )
    con.execute(sql)
    return [r[0] for r in con.execute("DESCRIBE raw").fetchall()]


def _parse_key(key: str) -> dict:
    # parts = key.split("/")
    meta = {
        # "categoria": f"{parts[0]}",
        # "tabela": f"{parts[1]}",
        "_source_object": key
    }
    return meta


def _silver_key(source: str, table: str) -> str:
    return f"{source}/{table}.parquet"


def _latest_objects(keys: list[str]) -> list[str]:
    groups: dict[str, tuple[str, str]] = {}
    for k in keys:
        month, pid = "", []
        for s in k.split("/"):
            if s.startswith("ingest_month="):
                month = s.split("=", 1)[1]
            else:
                pid.append(s)
        pid = "/".join(pid)
        if pid not in groups or month > groups[pid][0]:
            groups[pid] = (month, k)
    return [v[1] for v in sorted(groups.values())]


def _infer_type(col: str, casts: dict, heuristics: bool) -> str:
    if col in casts:
        return casts[col]
    name = col.lower()
    if heuristics:
        if name.startswith("dt_"):
            return "date"
        if name.startswith(("vl_", "pc_")):
            return "double"
    return "string"


def _cast_expr(col: str, ctype: str, date_fmt: str, dec_sep: str) -> str:
    q = f'"{col}"'
    base = f"nullif(trim(trim(trim({q}), '\"')), '')"
    if ctype == "date":
        return f"try_strptime({base}, '{date_fmt}')::DATE AS {q}"
    if ctype == "double":
        cleaned = (
            f"replace(replace({base}, '.', ''), ',', '.')" if dec_sep == "," else base
        )
        return f"try_cast({cleaned} AS DOUBLE) AS {q}"
    return f"{base} AS {q}"


def build_select(columns, *, casts, date_fmt, dec_sep, heuristics, meta):
    parts = [
        _cast_expr(c, _infer_type(c, casts, heuristics), date_fmt, dec_sep)
        for c in columns
    ]
    for k, v in meta.items():
        if v is None:
            parts.append(f"CAST(NULL AS VARCHAR) AS {k}")
        else:
            parts.append("'" + str(v).replace("'", "''") + f"' AS {k}")
    return "SELECT " + ", ".join(parts) + " FROM raw"


def _load_into_acc(con, client, bronze, key, tbl, scfg, first, acc="acc"):
    csv_tmp, enc = _download_and_transcode(client, bronze, key, tbl, scfg)
    try:
        delim = _resolve_delim(csv_tmp, tbl, scfg)
        cols = _read_raw(con, csv_tmp, delim, explicit=False)
        if len(cols) <= 1:
            cols = _read_raw(con, csv_tmp, delim, explicit=True)
            if len(cols) > 1:
                log.info(
                    "%s: releitura forçando delimitador=%r corrigiu para %d colunas",
                    tbl["name"],
                    delim,
                    len(cols),
                )
            else:
                log.warning(
                    "%s: leitura ainda com %d coluna(s) com delimitador=%r — verifique o arquivo bruto",
                    tbl["name"],
                    len(cols),
                    delim,
                )
        log.info(
            "%s: carregado com encoding=%r, delimitador=%r, %d colunas",
            tbl["name"],
            enc,
            delim,
            len(cols),
        )
        meta = _parse_key(key)
        meta["_loaded_at"] = datetime.now().isoformat()
        select = build_select(
            cols,
            casts=tbl.get("casts", {}) or {},
            date_fmt=scfg.get("date_format", "%d/%m/%Y"),
            dec_sep=scfg.get("decimal_separator", "."),
            heuristics=scfg.get("name_heuristics", True),
            meta=meta,
        )
        con.execute(
            f"CREATE OR REPLACE TABLE {acc} AS {select}"
            if first
            else f"INSERT INTO {acc} BY NAME {select}"
        )
        return con.execute("SELECT COUNT(*) FROM raw").fetchone()[0]
    finally:
        try:
            os.unlink(csv_tmp)
        except OSError:
            pass


def _write_table(con, client, silver, source, table, acc="acc"):
    fd, out = tempfile.mkstemp(suffix=".parquet")
    os.close(fd)
    con.execute(f"COPY {acc} TO '{out}' (FORMAT PARQUET)")
    skey = _silver_key(source, table)
    client.fput_object(silver, skey, out, content_type="application/parquet")
    try:
        os.unlink(out)
    except OSError:
        pass
    return skey


def transform(
    cfg: dict, source: str, src_cfg: dict, only_frequency: str | None = None
) -> None:
    scfg = cfg.get("silver", {})
    bronze = cfg["object_storage"]["buckets"]["bronze"]
    silver = cfg["object_storage"]["buckets"]["silver"]
    duckdb_spill = cfg["paths"].get("duckdb_temp", None)
    client = get_client(cfg)
    ensure_bucket(client, silver)

    con = duckdb_mem("12GB", duckdb_spill, 4)

    for category in ("dominios", "operacionais", "temporais"):
        grp = src_cfg.get(category)
        if not grp:
            continue
        if not _freq_match(grp, only_frequency):
            log.info(
                "Pulando categoria %s (frequency=%s != filtro=%s)",
                category,
                grp.get("frequency"),
                only_frequency,
            )
            continue
        for tbl in grp.get("tables", []):
            if not tbl.get("enabled"):
                continue
            prefix = f"{source}/{tbl['name']}/"
            keys = [
                k
                for k in list_objects(client, bronze, prefix)
                if k.endswith((".gz", ".csv"))
            ]
            latest = _latest_objects(keys)
            if not latest:
                log.warning(
                    "Sem objetos no bronze para %s. Verifique a ingestão.", tbl["name"]
                )
                continue
            try:
                total = 0
                for i, key in enumerate(latest):
                    log.info(
                        "Transformando %s: arquivo %d/%d -> %s",
                        tbl["name"],
                        i + 1,
                        len(latest),
                        key,
                    )
                    total += _load_into_acc(
                        con, client, bronze, key, tbl, scfg, first=(i == 0)
                    )
                skey = _write_table(con, client, silver, source, tbl["name"])
                log.info(
                    "Transformado %s/%s (%d linhas, %d arquivos) -> %s",
                    category,
                    tbl["name"],
                    total,
                    len(latest),
                    skey,
                )
            except Exception as e:
                log.error("Erro ao transformar %s: %s", tbl["name"], e)
            finally:
                con.execute("DROP TABLE IF EXISTS acc")
