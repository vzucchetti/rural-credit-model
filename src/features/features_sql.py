_LOOKUP = """
COPY (
  WITH safra AS (SELECT ref_bacen, nu_ordem, mutuario, target_18m FROM read_parquet('{labels}target_18m.parquet')),
       {cte1}
       {cte2}
  SELECT safra.ref_bacen, safra.nu_ordem, safra.mutuario, {expr}
  FROM safra {join1} {join2}
) TO '{out}' (FORMAT PARQUET)
"""

cte_mut = """mut AS (SELECT "REF_BACEN" AS ref_bacen, CD_CPF_CNPJ AS mutuario, {src} FROM read_parquet('{inpath}mutuarios.parquet'))"""
cte_op = """op AS (SELECT "#REF_BACEN" AS ref_bacen, NU_ORDEM AS nu_ordem, {src} FROM read_parquet('{inpath}operacao_basica.parquet'))"""

join_mut = (
    """JOIN mut ON safra.ref_bacen = mut.ref_bacen AND safra.mutuario = mut.mutuario"""
)
join_op = (
    """JOIN op ON safra.ref_bacen = op.ref_bacen AND safra.nu_ordem = op.nu_ordem"""
)

FEATURE_SQL = {
    "tp_produtor": _LOOKUP.replace("{cte1}", cte_mut)
    .replace("{src}", "CD_TIPO_BENEFICIARIO as tipo_produtor")
    .replace(
        "{cte2}",
        ",tipo AS ( \
        SELECT CAST(\"#CODIGO\" AS INT) AS tipo, DESCRICAO AS tipo_produtor \
        FROM read_parquet('{inpath}tipo_beneficiario.parquet'))",
    )
    .replace(
        "{expr}",
        "CASE \
            WHEN tipo.tipo_produtor IS NULL THEN NULL \
            WHEN tipo.tipo_produtor = 'Produtor rural (pessoa física ou jurídica) - (MCR 1-4-1-a)' THEN 'Produtor Rural PF/PJ' \
            WHEN tipo.tipo_produtor = 'Extrativista (MCR 2-1-15)' THEN 'Extrativista' \
            WHEN tipo.tipo_produtor = 'Pescador (MCR 2-1-15 e 20)' THEN 'Pescador' \
            WHEN tipo.tipo_produtor = 'Silvícola/indígena (MCR 1-4-3)' THEN 'Sílvicola/Indígena' \
            WHEN tipo.tipo_produtor IN ( \
                'Cooperativa de produção agropecuária – na condição de sociedade prestadora de serviços de natureza agropecuária aos seus cooperados (MCR 5-1-2-b e c)', \
                'Cooperativa de produção agropecuária – na condição de produtor rural - (MCR 5-1-2-a)' \
            ) THEN 'Cooperativa de Produção Agropecuária' \
            WHEN tipo.tipo_produtor = 'Aquicultor (MCR 2-1-20)' THEN 'Aquicultor' \
            WHEN tipo.tipo_produtor = 'Silvicultor (MCR 10-2-2-a-III)' THEN 'Silvicultor' \
            WHEN tipo.tipo_produtor = 'Pessoa física ou jurídica produtora de mudas, sementes, sêmen para inseminação artificial e embriões (MCR 1-4-2-a e b)' THEN 'Produtor PF/PJ de Mudas/Sementes/Embriões' \
            WHEN tipo.tipo_produtor = 'Quilombola rural (MCR 10-2-2-b-II)' THEN 'Quilombola Rural' \
            WHEN tipo.tipo_produtor = 'Agroindústria (MCR 1-4-2A-a)' THEN 'Agroindústria' \
            ELSE 'Outros Produtores' \
        END AS tp_produtor",
    )
    .replace("{join1}", join_mut)
    .replace("{join2}", "JOIN tipo ON mut.tipo_produtor = tipo.tipo_produtor"),
    "cat_emitente": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "CD_CATEG_EMITENTE")
    .replace(
        "{cte2}",
        ",cat AS ( \
        SELECT \"#CODIGO\" AS cod, DESCRICAO AS categoria_emitente \
        FROM read_parquet('{inpath}categoria_emitente.parquet'))",
    )
    .replace(
        "{expr}",
        "CASE \
            WHEN cat.categoria_emitente IS NULL THEN NULL \
            WHEN cat.categoria_emitente IN ('Pequeno Produtor Rural','Médio Produtor Rural','Grande Produtor Rural') THEN cat.categoria_emitente \
            ELSE 'Outras Categorias' \
        END AS cat_emitente",
    )
    .replace("{join1}", join_op)
    .replace("{join2}", "JOIN cat ON op.CD_CATEG_EMITENTE = cat.cod"),
    "instrum_credito": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "CD_INST_CREDITO")
    .replace(
        "{cte2}",
        ",cred AS ( \
        SELECT CAST(\"#CODIGO\" AS INT) AS cod, DESCRICAO AS instrum_credito \
        FROM read_parquet('{inpath}instrumento_credito.parquet'))",
    )
    .replace(
        "{expr}",
        "CASE \
            WHEN cred.instrum_credito IS NULL THEN NULL \
            WHEN cred.instrum_credito IN ( \
                'Cédula Rural Pignoratícia','Cédula Rural Hipotecária','Cédula Rural Pignoratícia e Hipotecária','Nota de Crédito Rural','Cédula de Crédito Bancário','Nota Promissória Rural','Contrato de Crédito Rural' \
            ) THEN cred.instrum_credito \
            ELSE 'Demais Instrumentos de Crédito' \
        END AS instrum_credito",
    )
    .replace("{join1}", join_op)
    .replace("{join2}", "JOIN cred ON op.CD_INST_CREDITO = cred.cod"),
    "fonte_recurso": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "CD_FONTE_RECURSO")
    .replace(
        "{cte2}",
        ",fonte AS ( \
        SELECT CAST(\"#CODIGO\" AS INT) AS cod, DESCRICAO AS fonte_recurso \
        FROM read_parquet('{inpath}fonte_recursos.parquet'))",
    )
    .replace(
        "{expr}",
        "CASE \
             WHEN fonte.fonte_recurso IN ( \
            'RECURSOS LIVRES EQUALIZÁVEIS','FACULDADE DE APLICAÇÃO - COMPULSÓRIO','TESOURO NACIONAL','OBRIGATÓRIOS - MCR 6.2','POUPANÇA RURAL - CONTROLADOS - SUBVENÇÃO ECONÔMICA','POUPANÇA RURAL - CONTROLADOS - CONDIÇÕES MCR 6.2', \
            'POUPANÇA RURAL - CONTROLADOS - FATOR DE PONDERAÇÃO','FUNDO CONSTITUCIONAL DE FINANCIAMENTO DO NORTE (FNO)','FUNDO CONSTITUCIONAL DE FINANCIAMENTO DO NORDESTE (FNE)','FUNDO CONSTITUCIONAL DE FINANCIAMENTO DO CENTRO-OESTE (FCO)', \
            'BNDES/FINAME - EQUALIZÁVEL','FAT - FUNDO DE AMPARO AO TRABALHADOR','FUNCAFE-FUNDO DE DEFESA DA ECONOMIA CAFEEIRA','FUNDO DE TERRAS E DA REFORMA AGRÁRIA','INCRA','GOVERNOS E FUNDOS ESTADUAIS OU MUNICIPAIS','PIS/PASEP', \
            'INSTR HIBRIDO CAPITAL DÍVIDA-IHCD (Lei 12.793/2013 - Art. 6º) - EQUALIZÁVEL','COMPULSÓRIO SOBRE RECURSOS À VISTA - REFORÇO DO INVESTIMENTO (CIRC 3.745)','LETRA DE CRÉDITO DO AGRONEGÓCIO (LCA) - TAXA FAVORECIDA', \
            'Exigibilidade Adicional dos Recursos à Vista - Resolução 5030 ENCERRADO','LETRA DE CRÉDITO DO AGRONEGÓCIO (LCA) - CONTROLADOS - SUBVENÇÃO ECONÔMICA - MCR 6-7-7A-\"b\"-I','Exigibilidade Adicional dos Recursos à Vista - Resolução 5087 - ENCERRADO', \
            'Exigibilidade Adicional dos Recursos à Vista - Resolução 5157','Fundo Nacional sobre Mudança do Clima (Fundo Clima) - RES CMN 5.130/2024','EXIGIBILIDADE ADICIONAL DOS RECURSOS À VISTA','EXIGIBILIDADE ADICIONAL DA POUPANÇA RURAL' \
        ) THEN 'Recursos Controlados' \
        ELSE 'Recursos Livres' \
        END AS fonte_recurso",
    )
    .replace("{join1}", join_op)
    .replace("{join2}", "JOIN fonte ON op.CD_FONTE_RECURSO = fonte.cod"),
    "uf": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "CD_ESTADO as uf")
    .replace("{cte2}", "")
    .replace("{expr}", "op.uf")
    .replace("{join1}", join_op)
    .replace("{join2}", ""),
    "tipo_seguro": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "CD_TIPO_SEGURO")
    .replace(
        "{cte2}",
        ",seg AS ( \
        SELECT CAST(\"#CODIGO\" AS INT) AS cod, DESCRICAO AS seguro \
        FROM read_parquet('{inpath}tipo_seguro.parquet'))",
    )
    .replace(
        "{expr}",
        "CASE \
            WHEN seg.seguro IS NULL THEN NULL \
            WHEN seg.seguro IN ('Não se aplica', 'Sem adesão a seguro') THEN 'Sem seguro' \
            WHEN seg.seguro IN ('Proagro mais', 'Proagro tradicional') THEN 'Proagro' \
            ELSE 'Outros seguros' \
        END AS tipo_seguro",
    )
    .replace("{join1}", join_op)
    .replace("{join2}", "JOIN seg ON op.CD_TIPO_SEGURO = seg.cod"),
    "finalidade": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "CD_EMPREENDIMENTO as empreendimento")
    .replace(
        "{cte2}",
        ",emp AS ( \
        SELECT \"#CODIGO\" AS cod, FINALIDADE \
        FROM read_parquet('{inpath}empreendimento.parquet'))",
    )
    .replace(
        "{expr}",
        "CASE \
            WHEN emp.FINALIDADE IN ('Custeio','Investimento','Comercialização','Industrialização') THEN emp.FINALIDADE \
            ELSE 'Outras finalidades' \
        END AS finalidade",
    )
    .replace("{join1}", join_op)
    .replace("{join2}", "JOIN emp ON op.empreendimento = emp.cod"),
    "atividade": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "CD_EMPREENDIMENTO as empreendimento")
    .replace(
        "{cte2}",
        ",emp AS ( \
        SELECT \"#CODIGO\" AS cod, ATIVIDADE \
        FROM read_parquet('{inpath}empreendimento.parquet'))",
    )
    .replace(
        "{expr}",
        "CASE \
            WHEN emp.ATIVIDADE IN ('Agrícola','Pecuário(a)') THEN emp.ATIVIDADE \
            ELSE 'Outras atividades' \
        END AS atividade",
    )
    .replace("{join1}", join_op)
    .replace("{join2}", "JOIN emp ON op.empreendimento = emp.cod"),
    "modalidade": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "CD_EMPREENDIMENTO as empreendimento")
    .replace(
        "{cte2}",
        ",emp AS ( \
        SELECT \"#CODIGO\" AS cod, FINALIDADE, MODALIDADE \
        FROM read_parquet('{inpath}empreendimento.parquet'))",
    )
    .replace(
        "{expr}",
        "CASE \
            WHEN emp.MODALIDADE IS NULL THEN NULL \
            WHEN emp.MODALIDADE IN ( \
                'APICULTURA','AQUISIÇÃO E MANUTENÇÃO DE ANIMAIS','AVICULTURA','BUBALINOCULTURA','CAPRINOCULTURA','CRIA DE ANIMAIS','CUNICULTURA E DEMAIS ROEDORES','EQUINOCULTURA','EXPLORAÇÃO SOB REGIME DE INTEGRAÇÃO - ENCERRADO', \
                'LAVOURA','MANUTENÇÃO/CRIAÇÃO DE ANIMAIS (CRIA)','MANUTENÇÃO/CRIAÇÃO DE ANIMAIS (RECRIA E ENGORDA)','MINHOCULTURA','OVINOCULTURA','SERICICULTURA','SUINOCULTURA','Agroindústria Familiar (MCR 10-11)', \
            ) OR (emp.MODALIDADE = 'AQUICULTURA' AND emp.FINALIDADE = 'Custeio') \
            OR (emp.MODALIDADE = 'BOVINOCULTURA' AND emp.FINALIDADE = 'Custeio') \
            OR (emp.MODALIDADE = 'EXTRATIVISMO DE ESPÉCIES NATIVAS' AND emp.FINALIDADE = 'Custeio') \
            OR (emp.MODALIDADE = 'FLORESTAMENTO E REFLORESTAMENTO' AND emp.FINALIDADE = 'Custeio') \
            OR (emp.MODALIDADE = 'PASTAGEM' AND emp.FINALIDADE = 'Custeio') \
            OR (emp.MODALIDADE = 'AQUISIÇÃO DE INSUMOS PARA INDÚSTRIA FAMILIAR' AND emp.FINALIDADE = 'Custeio') \
            OR (emp.MODALIDADE = 'BENEFICIAMENTO OU INDUSTRIALIZAÇÃO' AND emp.FINALIDADE = 'Custeio') \
            OR (emp.MODALIDADE = 'PESCA' AND emp.FINALIDADE = 'Custeio') \
            OR (emp.MODALIDADE = 'SERVIÇOS PROFISSIONAIS/TÉCNICOS' AND emp.FINALIDADE = 'Custeio') \
            THEN 'Manutenção de ciclo' \
            WHEN emp.MODALIDADE IN ( \
                'AQUISIÇÃO DE ATIVOS OPERACIONAIS','AQUISIÇÃO DE PROPRIEDADES RURAIS','AQUISIÇÃO DE VEÍCULOS','Financiamento para Aquisição da Produção/Materia P','MELHORAMENTO DAS EXPLORAÇÕES', \
                'MÁQUINAS, EQUIPAMENTOS, MATERIAIS E UTENSÍLIOS', \
            ) OR (emp.MODALIDADE = 'AQUICULTURA' AND emp.FINALIDADE = 'Investimento') \
            OR (emp.MODALIDADE = 'EXTRATIVISMO DE ESPÉCIES NATIVAS' AND emp.FINALIDADE = 'Investimento') \
            OR (emp.MODALIDADE = 'AQUISIÇÃO DE INSUMOS PARA INDÚSTRIA FAMILIAR' AND emp.FINALIDADE = 'Investimento') \
            OR (emp.MODALIDADE = 'BENEFICIAMENTO OU INDUSTRIALIZAÇÃO' AND emp.FINALIDADE = 'Investimento') \
            OR (emp.MODALIDADE = 'PESCA' AND emp.FINALIDADE = 'Investimento') \
            OR (emp.MODALIDADE = 'SERVIÇOS PROFISSIONAIS/TÉCNICOS' AND emp.FINALIDADE = 'Investimento') \
            THEN 'Investimento em máquinas/infraestrutura/ativos' \
            WHEN emp.MODALIDADE IN ( \
                'AQUISIÇÃO DE ANIMAIS','AQUISIÇÃO DE ANIMAIS DE SERVIÇO','AQUISIÇÃO DE ANIMAIS DE SERVIÇO (USO AGRICULTURA)','FORMAÇÃO DE CULTURAS PERENES','IMPLANTAÇÃO E MELHORAMENTO' \
            ) OR (emp.MODALIDADE = 'BOVINOCULTURA' AND emp.FINALIDADE = 'Investimento') \
             OR (emp.MODALIDADE = 'PASTAGEM' AND emp.FINALIDADE = 'Investimento') \
            THEN 'Investimento em material biológico' \
            WHEN emp.MODALIDADE IN ( \
                'Aquisição de Matéria Prima direto do Produtor/Coop','CPR (CÉDULA DE PRODUTO RURAL)','DESCONTO (NPR E DR)','ESTOCAGEM','FAC - Financiamento para Aquisição de Café','FEE (EX-LEC)','FEPM (EX-EGF) - encerrado', \
                'FGPP-Financiamento para Garantia de Preços ao Prod','FINANCIAMENTO PARA PROTEÇÃO DE PREÇOS EM OPERAÇÕES','PRÉ-COMERCIALIZAÇÃO - encerrado' \
            ) \
            OR (emp.MODALIDADE = 'AQUICULTURA' AND emp.FINALIDADE = 'Comercialização') \
            OR (emp.MODALIDADE = 'PESCA' AND emp.FINALIDADE = 'Comercialização') \
            OR (emp.MODALIDADE = 'SERVIÇOS PROFISSIONAIS/TÉCNICOS' AND emp.FINALIDADE = 'Comercialização') \
            THEN 'Estocagem/processamento/proteção de preço' \
            WHEN emp.MODALIDADE IN ( \
                'ATENDIMENTO A COOPERADOS','COOPERATIVAS DE CRÉDITO (SINGULAR OU CENTRAL) - en','Crédito para Cooperativa Pronaf MCR 10-3-1A','FINANCIAMENTO PROCAP-AGRO','INTEGRALIZAÇÃO DE COTAS PARTES' \
            ) THEN 'Cooperativismo/linhas de apoio' \
            ELSE 'Outras modalidades' \
        END AS modalidade",
    )
    .replace("{join1}", join_op)
    .replace("{join2}", "JOIN emp ON op.empreendimento = emp.cod"),
    "produto": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "CD_EMPREENDIMENTO as empreendimento")
    .replace(
        "{cte2}",
        ",emp AS ( \
        SELECT \"#CODIGO\" AS cod, MODALIDADE, FINALIDADE, PRODUTO, VARIEDADE \
        FROM read_parquet('{inpath}empreendimento.parquet'))",
    )
    .replace(
        "{expr}",
        "CASE \
            WHEN emp.PRODUTO IS NULL THEN NULL \
            WHEN emp.PRODUTO IN ('SOJA','ARROZ','FEIJÃO','AGROARTESANATO','AGROINDÚSTRIA') THEN emp.PRODUTO \
            WHEN emp.PRODUTO IN ('MILHO','MILHO SILAGEM') THEN 'MILHO' \
            WHEN emp.PRODUTO IN ('TRIGO','TRIGO SILAGEM','TRIGO SARRACENO/MOURISCO') THEN 'TRIGO' \
            WHEN emp.PRODUTO IN ('ALGODÃO','CAROÇO DE ALGODÃO') THEN 'ALGODÃO' \
            WHEN emp.PRODUTO IN ('CAFÉ','RECUPERAÇÃO DE CAFEZAIS') THEN 'CAFÉ' \
            WHEN emp.PRODUTO IN ('BOVINOS','Confinamento de bovinos \"free stall','SEBO BOVINO','Aquisição de Sistemas para Rastreabilidade de bovinos e bubalinos') THEN 'BOVINOCULTURA' \
            WHEN emp.PRODUTO IN ('GRANJAS DE SUÍNOS','SUINOCULTURA','SUÍNOS') THEN 'SUÍNOCULTURA' \
            WHEN emp.PRODUTO IN ( \
                'ABACATE','ABACAXI','ABRICÓ (DAMASCO)','ACEROLA','AMEIXA','AMORA','ARAÇA','ATEMOIA','AÇAÍ','BABAÇU','BANANA','BURITI','CACAU','CAMU-CAMU','CAJU','CAJÁ','CAMAPU (PHYSALIS)','CAQUI','CARAMBOLA','CEREJA','CHERIMOIA', \
                'CIDRA','COCO','COCO-DA-BAIA','CUPUAÇU','FIGO','FRAMBOESA','FRUTAS DIVERSAS N. E.','GABIROBA','GOIABA','GRAVIOLA','GROSELHA','GUARANÁ','JABUTICABA','JACA','JILÓ','LARANJA','LIMA','LIMÃO','LONGAN','MAMÃO','MANGA', \
                'MANGABA','MANGOSTÃO','MARACUJÁ','MARMELO','MAÇÃ','MELANCIA','MELÃO','MIRTILO','MORANGO','MURICI','NECTARINA','NESPERA','PEQUI','PERA','PINHA (ATA, FRUTA-DO-CONDE, ANONA)','PITANGA','PITAYA','POMELO','PÊSSEGO', \
                'QUIUÍ (KIWI)','ROMÃ','SAPOTI','TAMARINDO','TANGERINA','TAPEREBÁ','TORANJA','TUCUM','UMBU','UVA','CÂMARA FRIA PARA ARMAZENAMENTO DE FRUTAS' \
            ) THEN 'FRUTICULTURA' \
            WHEN emp.PRODUTO IN ( \
                'ABOBRINHA','ABÓBORA-MORANGA','ACELGA','AGRIÃO','AIPO','ALCACHOFRA','ALFACE','ALFAFA','ALHO','ALHO PORÓ','ALMEIRÃO','ASPARGO','BATATA','BATATA ASTERIX','BATATA-DOCE','BATATA-INGLESA','BERINJELA', \
                'BETERRABA','BRÓCOLOS (BRÓCOLIS)','CARÁ','CEBOLA','CEBOLINHA','CEBOLINHA VERDE','CENOURA','CHICORIA','CHUCHU','COENTRO','COUVE','COUVE-FLOR','ESCAROLA','ESPINAFRE','HORTALIÇAS','Hortaliça ora-pro-nóbis','INHAME', \
                'MANDIOCA (AIPIM, MACAXEIRA)','MANDIOQUINHA (BATATA: BAROA, SALSA, AIPO)','MAXIXE','MOSTARDA','NABO','OLERÍCOLAS','PEPINO','PIMENTÃO','QUIABO','RABANETE','REPOLHO','RÚCULA','SALSA','TAIOBA','TOMATE','VAGEM' \
            ) THEN 'OLERICULTURA/HORTALIÇAS' \
            WHEN emp.PRODUTO IN ( \
                'ALGICULTURA (Cultivo de Algas)','Alevinos','Algas','Alimentador de Peixe','CAMARÃO','CAMARÃO E/OU LAGOSTA','CARCINICULTURA','CARCINICULTURA (Cultivo de Camarão e Lagosta)','CRUSTÁCEOS','MEXILHÃO','MARISCOS', \
                'Camarão e Lagosta','Descamadora de Peixe','Descascador de Camarão e Lagosta','Girinos','MALACOCULTURA (Cultivo e Criação de Moluscos)','MARICULTURA (Cultivo de Marisco)','Mariscos','PESCADO IN NATURA', \
                'MITILICULTURA (Cultivo de Mexilhão)','MOLUSCOS (Caramujos, Lulas etc)','Mexilhões','OSTRAS','OSTREICULTURA','OSTREICULTURA (Cultivo de Ostras)','PEIXE','PESCA','PESCADO','PISCICULTURA','RÃ','RANICULTURA', \
                'PESCADO (ARMAZENAMENTO, ACONDICIONAMENTO E PRESERVACAO, INCLUSIVE SEGURO, IMPOSTOS, FRETES ETC)','PISCICULTURA (CULTIVO DE PEIXES)','PISCICULTURA (Cultivo de Peixe)','RANICULTURA (Cultivo de Rã)', \
                'Petrechos para Pesca (anzóis, iscas, cordas, bóias, combustivel, redes, mão-de-obra etc)','Aerador','Armação para Barco de Pesca','CLASSIFICADOR DE PESCADO','COZEDOR DE PESCADO','DEPÓSITO PARA RAÇÕES', \
                'DESPOLPADOR DE PESCADO','Embarcação Grande (a partir de 100 A/B)','Embarcação Média (acima de 20 e abaixo de 100 A/B)','Embarcação Pequena (até 20 A/B)','Esteira','Estufa','Evisceradora', \
                'MESA PARA DESCABEÇAMENTO DE PESCADO','MESA PARA RETIRADA DE PELE, ESCAMA E CARCAÇA DE PESCADO','Mesa para Filetagem','SEPARADOR DE RESÍDUOS','Tanques Escavados','Tanques Redes', \
                'PRODUTOS AQUICOLAS (Armazenamento, Acondicionamento e Preservação, inclusive Seguro, Impostos etc)','Unidade de Beneficiamento ou Processamento' \
            ) THEN 'AQUICULTURA/PESCADO' \
            WHEN emp.PRODUTO IN ( \
                'ABELHA','APICULTURA','ANIMAIS SILVESTRES','ASININOS','AVESTRUZ','BICHO-DA-SEDA','BÚFALOS (BUBALINOS)','CANINOS','CAPRINOS','CHINCHILAS','COELHO','CUNICULTURA','EQUINOS','LÃ','MEL','MINHOCA','MELIPONICULTURA', \
                'Caixas de abelhas, favos, centrifugas p/ extração de mel, fumegadores','Instalações para Aves, Suínos e Coelhos','MUARES','OUTROS ANIMAIS','OVINOS','SERICICULTURA','SIRGARIAS','TRIPAS','VISCACHAS','COURO','LEITE', \
                'Balança para Animais','Caminhões Frigoríficos','INSEMINAÇÃO ARTIFICIAL','Matrizes e Reprodutores','Medicamentos, Rações e Insumos','RESÍDUOS DE PRODUÇÃO ANIMAL','Raspador','SAL', \
                'VACINAS, SAIS MINERAIS E MEDICAMENTOS' \
            ) THEN 'OUTRAS PECUÁRIAS' \
            WHEN emp.PRODUTO IN ( \
                'ACÁCIA NEGRA','AGAVE (SISAL)','ANDIROBA','ARAUCÁRIA','BUCHA VEGETAL','Bambu','BARU','CASTANHA DE BARU','CASTANHA DE CAJU','CASTANHA-DO-BRASIL','CAMBARÁ','CARNAÚBA','CEDRINHO','CEDRO','CURAUÁ','DENDÊ', \
                'Cumaru/Champanhe','EUCALIPTO','GARAPEIRA','GUARIROBA','JATOBÁ','JUTA','Kiri (Paulownia spp)','LINHO','MADEIRA','MURUMURU','Macaúba','NOZ','OLIVA (AZEITONA)','PALMITO (PUPUNHA,AÇAI)','PARICÁ','PIAÇABA (PIAÇAVA)', \
                'PINHÃO','PINUS','PORONGO (CUIA,CABAÇA)','PRACAXI','PUPUNHA','RAMI','SERINGUEIRA','TUNGUE','VIME','ÓLEO VEGETAL','TANINO','EQUIPAMENTOS E UTENSÍLIOS PARA EXTRATIVISMO DE ESPÉCIES NATIVAS' \
            ) OR (emp.PRODUTO = 'FLORESTAMENTO E REFLORESTAMENTO' AND emp.VARIEDADE IN ( \
                'EUCALIPTO DUNNII','EUCALIPTO GRANDIS','EUCALIPTO GLOBULUS','EUCALIPTO SALIGNA','EUCALIPTO VIMINALIS','EUCALIPTO BENTHAMII' \
            )) THEN 'SILVICULTURA/EXTRATIVISMO' \
            WHEN emp.PRODUTO IN ( \
                'AMENDOIM','AVEIA','CANOLA','CARINATA','CENTEIO','CEVADA','CHIA','COLZA','ERVILHA','GERGELIM','GIRASSOL','GRÃO-DE-BICO','GRÃOS','LENTILHA','LICHIA (LECHIA)','LINHAÇA','LÚPULO','PAINÇO','QUINOA' \
            ) THEN 'OUTROS GRÃOS/OLEAGINOSAS' \
            WHEN emp.PRODUTO IN ( \
                'AROEIRA (PIMENTA-ROSA)','AÇAFRÃO','CHÁ','COPAÍBA','CRAVO','CRAVO-DA-ÍNDIA','ERVA CIDREIRA (MELISSA)','ERVA-DOCE','ERVA-MATE','Ervas medicinais, aromáticas ou condimentares','GENGIBRE','HORTELÃ', \
                'MALVA','MANJERICÃO','MENTA','MORINGA','NEEM','PATAUÁ','PIMENTA','PIMENTA-DO-REINO','PIXURIM','POEJO','SERRALHA','URUCUM' \
            ) THEN 'CONDIMENTOS/ERVAS MEDICINAIS' \
            WHEN emp.PRODUTO IN ('AVES','AVES EXCETO GALINÁCEOS','AVICULTURA','FRANGO','GALINÁCEOS','GRANJAS AVÍCOLAS','OVOS') THEN 'AVICULTURA' \
            WHEN emp.PRODUTO IN ( \
                'AZEVEM','CAPIM','CROTALÁRIA','ERVILHACA - RALIÇA, VICIA SATIVA','ESTILOSANTES','FORRAÇÃO DE JARDIM','MAMONA','MILHETO','NIGER','PALMA','PASTAGEM','SORGO','TIFTON','TRITICALE' \
            ) THEN 'PASTAGENS/FORRAGENS' \
            WHEN emp.PRODUTO IN ( \
                'CITRONELA (CYMBOPOGON NARDUS)','COGUMELO','ESTÉVIA','FLORESTAMENTO - TRATOS CULTURAIS','FLORESTAMENTO E REFLORESTAMENTO','FUMO','MUDAS DIVERSAS','OUTRAS CULTURAS','OUTRAS LAVOURAS','PLANTAS PARA INFUSÃO', \
                'ADUBAÇÃO ORGÂNICA/MINERAL, CALAGEM, SUBSTRATOS INERTES(PEDRA, AREIA, VERMICULITA, SILTE, ARGILA ETC)','AQUISIÇÃO DE FERRAMENTA PORTÁTIL MANUAL PARA TRATOS CULTURAIS','CONSERVAÇÃO DE SOLOS', \
                'CERCAS, ARAMADOS, TELHAS, TELAS PARA SOMBREAMENTO E COBERTURAS DE SOLO','COBERTURAS DE SOLO (PLÁSTICAS, TNT, TECIDOS, SERRAGEM, PALHADAS DE CAPIM E DE GRÃOS ETC)','DESPOLPADOR','CANA-DE-AÇÚCAR','AÇUCAR', \
                'EQUIPAMENTOS E UTENSILIOS PARA AGRICULTURA DE PRECISÃO','ESTUFAS/VIVEIROS (ILUMIN. ARTIFICIAL, MUDAS, SEMENTES, SACOS, TALAGARÇAS, BANDEJAS, VASOS)','HIDROPONIA/FAZENDA VERTICAL (ALVENARIA, MADEIRA, AÇO, ETC)', \
                'IRRIGAÇÃO/LIXIVIAÇÃO (GOTEJADOR, ASPERSOR, NEBULIZADOR, EXAUSTOR, VENTILADOR, MANGUEIRAS, CANAIS ET)','SECADOR','TENDA, GALPÃO, TÚNEL PLÁSTICO (ABRANGE LONAS, FILMES, LONGARINAS, ESTACAS E MAT. SUSTENTAÇÃO)', \
                'TULHA' \
            ) OR (emp.PRODUTO = 'AQUISIÇÃO DE INSUMOS' AND emp.MODALIDADE = 'LAVOURA') THEN 'OUTRAS CULTURAS' \
            WHEN emp.PRODUTO IN ('CRISÂNTEMO','FLORES','GRAMA','PALMEIRA','PALMÁCEA','PLANTAS ORNAMENTAIS','SANSÃO-DO-CAMPO') THEN 'ORNAMENTAIS' \
            ELSE 'OUTROS PRODUTOS' \
        END AS produto",
    )
    .replace("{join1}", join_op)
    .replace("{join2}", "JOIN emp ON op.empreendimento = emp.cod"),
    "cesta_cultivo": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "CD_EMPREENDIMENTO as empreendimento")
    .replace(
        "{cte2}",
        ",emp AS ( \
        SELECT \"#CODIGO\" AS cod, CESTA AS cesta_cultivo\
        FROM read_parquet('{inpath}empreendimento.parquet'))",
    )
    .replace("{expr}", "emp.cesta_cultivo")
    .replace("{join1}", join_op)
    .replace("{join2}", "JOIN emp ON op.empreendimento = emp.cod"),
    "programa": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "CD_PROGRAMA as programa")
    .replace("{cte2}", "")
    .replace(
        "{expr}",
        "CASE \
            WHEN op.programa IS NULL THEN NULL \
            WHEN op.programa = '0001' THEN 'PRONAF' \
            WHEN op.programa = '0050' THEN 'PRONAMP' \
            ELSE 'DEMAIS PROGRAMAS' \
        END AS programa",
    )
    .replace("{join1}", join_op)
    .replace("{join2}", ""),
    "tipo_irrigacao": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "CD_TIPO_IRRIGACAO AS tipo_irrigacao")
    .replace(
        "{cte2}",
        ",irrig AS ( \
        SELECT \"#CODIGO\" AS cod, DESCRICAO AS tipo_irrigacao \
        FROM read_parquet('{inpath}tipo_irrigacao.parquet'))",
    )
    .replace(
        "{expr}",
        "CASE \
            WHEN irrig.tipo_irrigacao IS NULL THEN NULL \
            WHEN irrig.tipo_irrigacao NOT IN ('Não Irrigado','Não se aplica') THEN irrig.tipo_irrigacao \
            WHEN irrig.tipo_irrigacao IN ('Irrigação com cobertura contra a seca MCR 12-2-3-\"c') THEN 'Cobertura contra a seca' \
            ELSE 'Não irrigado/Não se aplica' \
        END AS tipo_irrigacao",
    )
    .replace("{join1}", join_op)
    .replace("{join2}", "JOIN irrig ON op.tipo_irrigacao = irrig.cod"),
    "tipo_agricultura": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "CD_TIPO_AGRICULTURA AS cod_agricultura")
    .replace(
        "{cte2}",
        ",agri AS ( \
        SELECT \"#CODIGO\" AS cod, DESCRICAO AS tipo_agricultura \
        FROM read_parquet('{inpath}tipo_agricultura.parquet'))",
    )
    .replace(
        "{expr}",
        "CASE \
            WHEN agri.tipo_agricultura IS NULL THEN NULL \
            WHEN agri.tipo_agricultura IN ('Não se aplica','Floresta Plantada','Floresta Nativa') THEN 'Não se aplica' \
            ELSE agri.tipo_agricultura \
        END AS tipo_agricultura",
    )
    .replace("{join1}", join_op)
    .replace("{join2}", "JOIN agri ON op.cod_agricultura = agri.cod"),
    "tipo_ciclo": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "CD_FASE_CICLO_PRODUCAO AS cod_ciclo")
    .replace(
        "{cte2}",
        ",ciclo AS ( \
        SELECT \"#CODIGO\" AS cod, DESCRICAO AS tipo_ciclo \
        FROM read_parquet('{inpath}fase_ciclo_producao.parquet'))",
    )
    .replace(
        "{expr}",
        "CASE \
            WHEN ciclo.tipo_ciclo IS NULL THEN NULL \
            WHEN ciclo.tipo_ciclo IN ('Creche - ENCERRADO','Cria ou Multiplicação','Cria/Creche - ENCERRADO','Retenção de Matrizes','Cria/Recria','Recria') THEN 'Cria/Recria' \
            WHEN ciclo.tipo_ciclo IN ('Engorda','Terminação - ENCERRADO','Engorda em confinamento') THEN 'Engorda' \
            WHEN ciclo.tipo_ciclo IN ('Cria/Recria/Engorda (Ciclo Completo)','Cria/Recria/Engorda - ENCERRADO','Cria e Engorda','Recria e Engorda','Recria/Terminação - ENCERRADO') THEN 'Ciclo completo' \
            WHEN ciclo.tipo_ciclo IN ( \
                'Corte Raso Final','Corte Raso Intermediário - ENCERRADO','Demais Cortes - ENCERRADO','Primeiro Corte - ENCERRADO','Segundo Corte - ENCERRADO','Terceiro Corte - ENCERRADO','Quarto Corte - ENCERRADO' \
            ) THEN 'Corte' \
             WHEN ciclo.tipo_ciclo IN ('Semestral','Anual','Bienal') THEN ciclo.tipo_ciclo \
            ELSE 'Outros ciclos' \
        END AS tipo_ciclo",
    )
    .replace("{join1}", join_op)
    .replace("{join2}", "JOIN ciclo ON op.cod_ciclo = ciclo.cod"),
    "tipo_integracao": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "CD_TIPO_INTGR_CONSOR AS cod_integracao")
    .replace(
        "{cte2}",
        ",integ AS ( \
        SELECT \"#CODIGO\" AS cod, DESCRICAO AS tipo_integracao \
        FROM read_parquet('{inpath}tipo_integracao.parquet'))",
    )
    .replace("{expr}", "integ.tipo_integracao")
    .replace("{join1}", join_op)
    .replace("{join2}", "JOIN integ ON op.cod_integracao = integ.cod"),
    "aliq_proagro": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "VL_ALIQ_PROAGRO as aliq_proagro")
    .replace("{cte2}", "")
    .replace("{expr}", "op.aliq_proagro")
    .replace("{join1}", join_op)
    .replace("{join2}", ""),
    "juros": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "VL_JUROS as juros")
    .replace("{cte2}", "")
    .replace("{expr}", "op.juros")
    .replace("{join1}", join_op)
    .replace("{join2}", ""),
    "area_informada": _LOOKUP.replace("{cte1}", cte_op)
    .replace("{src}", "VL_AREA_INFORMADA as area_informada")
    .replace("{cte2}", "")
    .replace("{expr}", "op.area_informada")
    .replace("{join1}", join_op)
    .replace("{join2}", ""),
}
