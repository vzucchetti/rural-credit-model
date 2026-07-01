FEATURE_SPEC = [
    ("tp_produtor", ["ref_bacen", "mutuario"], "tp_produtor", "cat"),
    ("cat_emitente", ["ref_bacen", "nu_ordem"], "cat_emitente", "cat"),
    ("instrum_credito", ["ref_bacen", "nu_ordem"], "instrum_credito", "cat"),
    ("fonte_recurso", ["ref_bacen", "nu_ordem"], "fonte_recurso", "cat"),
    ("uf_operacao", ["ref_bacen", "nu_ordem"], "uf", "cat"),
    ("tipo_seguro", ["ref_bacen", "nu_ordem"], "tipo_seguro", "cat"),
    ("finalidade", ["ref_bacen", "nu_ordem"], "finalidade", "cat"),
    ("atividade", ["ref_bacen", "nu_ordem"], "atividade", "cat"),
    ("modalidade", ["ref_bacen", "nu_ordem"], "modalidade", "cat"),
    ("produto", ["ref_bacen", "nu_ordem"], "produto", "cat"),
    ("cesta_cultivo", ["ref_bacen", "nu_ordem"], "cesta_cultivo", "cat"),
    ("programa", ["ref_bacen", "nu_ordem"], "programa", "cat"),
    ("tipo_irrigacao", ["ref_bacen", "nu_ordem"], "tipo_irrigacao", "cat"),
    ("tipo_agricultura", ["ref_bacen", "nu_ordem"], "tipo_agricultura", "cat"),
    ("tipo_ciclo", ["ref_bacen", "nu_ordem"], "tipo_ciclo", "cat"),
    ("tipo_integracao", ["ref_bacen", "nu_ordem"], "tipo_integracao", "cat"),
    ("aliquota_proagro", ["ref_bacen", "nu_ordem"], "aliq_proagro", "num"),
    ("juros", ["ref_bacen", "nu_ordem"], "juros", "num"),
    ("area_informada", ["ref_bacen", "nu_ordem"], "area_informada", "num"),
]

ALL_FEATURES = [c for _, _, c, _ in FEATURE_SPEC]
CAT_FEATURES = [c for _, _, c, t in FEATURE_SPEC if t == "cat"]
NUM_FEATURES = [c for _, _, c, t in FEATURE_SPEC if t == "num"]
FILE_OF = {c: f for f, _, c, _ in FEATURE_SPEC}
KEYS_OF = {c: k for _, k, c, _ in FEATURE_SPEC}
PT_KEYS, BORROWER_KEYS = ["ref_bacen", "nu_ordem"], ["ref_bacen", "mutuario"]
PRIMARY_KEYS = ["ref_bacen", "nu_ordem", "mutuario"]
TARGET = "target_18m"
GROUP = "mutuario"
