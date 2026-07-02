import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from src.utils.io import load_config
from src.modeling.run_storage import load_runs
from app.business_data import load_aggregates, load_vintage, DIMS

st.set_page_config(page_title="Monitor — Risco de Crédito Rural", layout="wide")
st.title("Acompanhamento dos Modelos de Risco de Crédito")

cfg = load_config("settings")
runs = load_runs(cfg)
if not runs:
    st.warning("Nenhuma run encontrada. Rode o treino primeiro.")
    st.stop()

kfold_runs = [r for r in runs if r.get("validation", "kfold") == "kfold"]
oot_runs = [r for r in runs if r.get("validation") == "temporal"]

all_models = sorted({res["model"] for r in runs for res in r["results"]})
modelos = st.sidebar.multiselect("Modelos", all_models, default=all_models)


# ---------- helpers de curva (reusados por k-fold e OOT) ----------
def show_curves(entries, key):
    """entries: lista de dicts com model, metrics, roc, ks_curve, calibration."""
    ents = [e for e in entries if e["model"] in modelos]
    c_roc, c_brier = st.columns(2)
    with c_roc:
        st.markdown("**Curva ROC**")
        if any(e.get("roc") for e in ents):
            fig, ax = plt.subplots(figsize=(5, 4))
            for e in ents:
                if e.get("roc"):
                    ax.plot(
                        [p["fpr"] for p in e["roc"]],
                        [p["tpr"] for p in e["roc"]],
                        label=f"{e['model']} (AUROC={e['metrics']['auroc']:.3f})",
                    )
            ax.plot([0, 1], [0, 1], "--", color="gray", lw=1)
            ax.set_xlabel("FPR")
            ax.set_ylabel("TPR")
            ax.legend(loc="lower right", fontsize=8)
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.info("Sem dados de ROC.")
    with c_brier:
        st.markdown("**Calibração / Brier**")
        if any(e.get("calibration") for e in ents):
            fig, ax = plt.subplots(figsize=(5, 4))
            for e in ents:
                if e.get("calibration"):
                    ax.plot(
                        [p["mean_pred"] for p in e["calibration"]],
                        [p["frac_pos"] for p in e["calibration"]],
                        "o-",
                        label=f"{e['model']} (Brier={e['metrics']['brier']:.4f})",
                    )
            ax.plot([0, 1], [0, 1], "--", color="gray", lw=1)
            ax.set_xlabel("prob. média prevista")
            ax.set_ylabel("freq. observada")
            ax.legend(loc="upper left", fontsize=8)
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.info("Sem dados de calibração.")
    st.markdown("**Curva KS (CDFs por classe)**")
    if any(e.get("ks_curve") for e in ents):
        kcols = st.columns(len(ents))
        for c, e in zip(kcols, ents):
            with c:
                ks = e.get("ks_curve")
                if not ks:
                    st.caption(f"{e['model']}: sem dados")
                    continue
                s = [p["score"] for p in ks]
                cp = [p["cdf_pos"] for p in ks]
                cn = [p["cdf_neg"] for p in ks]
                gaps = [abs(a - b) for a, b in zip(cp, cn)]
                i = int(np.argmax(gaps))
                fig, ax = plt.subplots(figsize=(3.4, 3))
                ax.plot(s, cp, label="inadimplentes")
                ax.plot(s, cn, label="adimplentes")
                ax.vlines(s[i], min(cp[i], cn[i]), max(cp[i], cn[i]), color="red", lw=2)
                ax.set_title(f"{e['model']} · KS={e['metrics']['ks']:.3f}", fontsize=9)
                ax.set_xlabel("score", fontsize=8)
                ax.legend(fontsize=7, loc="lower right")
                st.pyplot(fig)
                plt.close(fig)
    else:
        st.info("Sem dados de curva KS.")


@st.cache_data(show_spinner="Agregando concessões e inadimplência...")
def _biz_aggregates():
    return load_aggregates(load_config("settings"))


@st.cache_data(show_spinner="Calculando curva de safra...")
def _biz_vintage():
    return load_vintage(load_config("settings"))


tab_biz, tab_kf, tab_oot = st.tabs(
    ["Métricas de negócio", "Validação k-fold", "Out-of-time (por safra)"]
)

# ==================== K-FOLD ====================
with tab_kf:
    if not kfold_runs:
        st.info("Nenhuma run k-fold ainda. Rode `make train`.")
    else:
        rows = []
        for r in kfold_runs:
            for res in r["results"]:
                rows.append(
                    {
                        "run_id": r["run_id"],
                        "created_at": r["created_at"],
                        "model": res["model"],
                        **res["metrics"],
                    }
                )
        df = pd.DataFrame(rows).sort_values("created_at")
        run_ids = sorted(df.run_id.unique())
        run_sel = st.selectbox(
            "Run para detalhe", run_ids, index=len(run_ids) - 1, key="kf_run"
        )
        dff = df[df.model.isin(modelos)]

        st.subheader("Última execução")
        ult = df[df.run_id == run_ids[-1]]
        cc = st.columns(len(ult))
        for c, (_, row) in zip(cc, ult.iterrows()):
            c.metric(
                f"{row['model']} · AUROC",
                f"{row['auroc']:.3f}",
                help=f"KS={row['ks']:.3f} | Brier={row['brier']:.4f}",
            )

        st.subheader("Evolução por execução")
        for met in ("auroc", "ks", "brier"):
            st.markdown(f"**{met.upper()}**")
            st.line_chart(
                dff.pivot_table(
                    index="run_id", columns="model", values=met, aggfunc="last"
                )
            )

        st.subheader(f"Curvas — run {run_sel}")
        run = next(r for r in kfold_runs if r["run_id"] == run_sel)
        show_curves(run["results"], key="kf")

        st.subheader("Métricas por fold")
        for r in run["results"]:
            if r["model"] in modelos:
                with st.expander(
                    f"{r['model']} — AUROC {r['metrics']['auroc']:.3f} "
                    f"(±{r['metrics'].get('auroc_std', 0):.3f})"
                ):
                    st.dataframe(pd.DataFrame(r["folds"]), use_container_width=True)

# ==================== OUT-OF-TIME ====================
with tab_oot:
    if not oot_runs:
        st.info("Nenhuma run out-of-time ainda. Rode `make train-temporal`.")
    else:
        rid = st.selectbox(
            "Run OOT",
            [r["run_id"] for r in oot_runs],
            index=len(oot_runs) - 1,
            key="oot_run",
        )
        run = next(r for r in oot_runs if r["run_id"] == rid)

        # série por safra de teste (uma linha por modelo)
        rows = []
        for res in run["results"]:
            if res["model"] not in modelos:
                continue
            for e in res["per_safra"]:
                rows.append(
                    {
                        "safra": e["safra_label"],
                        "model": res["model"],
                        "n_test": e["n_test"],
                        "rate_test": e["rate_test"],
                        **e["metrics"],
                    }
                )
        if not rows:
            st.info("Sem resultados por safra para os modelos selecionados.")
            st.stop()
        sdf = pd.DataFrame(rows).sort_values("safra")

        st.subheader("Desempenho por safra de teste (walk-forward)")
        for met in ("auroc", "ks", "brier"):
            st.markdown(f"**{met.upper()} por safra**")
            st.line_chart(
                sdf.pivot_table(
                    index="safra", columns="model", values=met, aggfunc="last"
                )
            )

        st.subheader("Volume e taxa observada por safra")
        vol = sdf.pivot_table(
            index="safra", values=["n_test", "rate_test"], aggfunc="first"
        )
        st.dataframe(vol, use_container_width=True)
        st.caption(
            "Atenção: safras recentes podem ter os 18 meses do alvo ainda não observados "
            "(censura à direita) — taxa subestimada. Leia a queda de métrica na última "
            "safra com essa ressalva."
        )

        # curvas para uma safra escolhida
        safras = sorted(
            {e["safra_label"] for res in run["results"] for e in res["per_safra"]}
        )
        safra_sel = st.selectbox(
            "Safra para detalhe das curvas",
            safras,
            index=len(safras) - 1,
            key="oot_safra",
        )
        entries = []
        for res in run["results"]:
            e = next(
                (x for x in res["per_safra"] if x["safra_label"] == safra_sel), None
            )
            if e:
                entries.append(
                    {
                        "model": res["model"],
                        "metrics": e["metrics"],
                        "roc": e.get("roc"),
                        "ks_curve": e.get("ks_curve"),
                        "calibration": e.get("calibration"),
                    }
                )
        st.subheader(f"Curvas — safra {safra_sel}")
        show_curves(entries, key="oot")


# ==================== MÉTRICAS DE NEGÓCIO ====================
with tab_biz:
    ct, cb = st.columns([4, 1])
    ct.subheader("Volume de crédito e inadimplência por dimensão")
    if cb.button("🔄 Recarregar", key="biz_reload"):
        _biz_aggregates.clear()
        _biz_vintage.clear()
        st.rerun()
    try:
        aggs = _biz_aggregates()
        erro_biz = None
    except Exception as e:  # noqa: BLE001
        aggs, erro_biz = None, e
    if erro_biz is not None:
        st.error(f"Não foi possível agregar as métricas de negócio: {erro_biz}")
    else:
        dim = st.selectbox("Dimensão", DIMS, key="biz_dim")
        d = aggs[dim].copy()
        topn = len(d) if dim == "safra" else min(20, len(d))
        if dim != "safra":
            d = d.head(topn)
        cats = d["categoria"].astype(str).tolist()
        has_vol = "volume" in d.columns

        if has_vol:
            bar_vals = d["volume"].astype(float) / 1e6
            bar_label = "volume de crédito (R$ milhões)"
            titulo = "Volume de crédito (barras) e inadimplência (linha)"
        else:
            bar_vals = d["concessoes"].astype(float)
            bar_label = "concessões (operações)"
            titulo = "Concessões (barras) e inadimplência (linha)"

        fig, ax1 = plt.subplots(figsize=(9, 4))
        ax1.bar(cats, bar_vals, color="#4C78A8", alpha=0.85)
        ax1.set_ylabel(bar_label, color="#4C78A8")
        ax1.tick_params(axis="x", rotation=60, labelsize=8)
        ax2 = ax1.twinx()
        ax2.plot(cats, d["taxa"] * 100, "o-", color="#E45756", lw=2)
        ax2.set_ylabel("inadimplência por operação (%)", color="#E45756")
        ax1.set_title(
            f"{titulo} por {dim}"
            + ("" if dim == "safra" else f" — top {topn} por volume")
        )
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

        show = ["categoria", "concessoes", "inadimplentes", "taxa"]
        tbl = d.copy()
        if has_vol:
            tbl["volume_mm"] = (tbl["volume"].astype(float) / 1e6).round(2)
            show.insert(1, "volume_mm")
        tbl["taxa"] = (tbl["taxa"] * 100).round(2)
        st.dataframe(
            tbl[show].rename(columns={"taxa": "taxa_pct"}), use_container_width=True
        )

        if dim == "safra":
            st.subheader("Curva de safra — inadimplência acumulada por delta")
            try:
                v = _biz_vintage()
                deltas = [c for c in v.columns if c != "safra"]
                fig, ax = plt.subplots(figsize=(9, 4))
                for _, row in v.iterrows():
                    ax.plot(
                        [int(x) for x in deltas],
                        [row[c] * 100 for c in deltas],
                        marker=".",
                        label=str(int(row["safra"])),
                    )
                ax.set_xlabel("meses após emissão (delta)")
                ax.set_ylabel("inadimplência acumulada (%)")
                ax.legend(title="safra", fontsize=7, ncol=2)
                fig.tight_layout()
                st.pyplot(fig)
                plt.close(fig)
                st.caption(
                    "Cada linha é uma safra; a curva mostra como a inadimplência amadurece "
                    "ao longo dos meses. Safras recentes têm curva mais curta/parcial "
                    "(censura à direita) — leia o fim delas com ressalva."
                )
            except Exception as e:  # noqa: BLE001
                st.info(f"Curva de safra indisponível: {e}")

        st.caption(
            "Grão: operação (ref_bacen+nu_ordem); inadimplência = operação com algum "
            "tomador inadimplente em 18m. Barras = volume de crédito tomado nas operações "
            "(coluna modeling.valor_credito_col). Métricas sobre a base completa (sem amostragem)."
        )

st.caption(
    "k-fold: estratificada por target e agrupada por mutuário (sem vazamento de tomador). "
    "OOT: treina em safras passadas e testa em safras futuras — mede degradação temporal."
)
