import streamlit as st

# ----------------- CONFIGURAÇÃO DA PÁGINA -----------------
st.set_page_config(
    page_title="Validador de Bulas (Interface)",
    page_icon="💊",
    layout="wide",
)

# ----------------- ESTILOS CSS (INTERFACE BONITA) -----------------
st.markdown("""
<style>
    /* Ajustes Gerais */
    .main { background-color: #f8f9fa; }
    .block-container { padding-top: 30px !important; }

    /* Estilo dos Cards de Texto */
    .texto-bula { 
        font-size: 0.95rem; 
        line-height: 1.6; 
        color: #2c3e50; 
        font-family: 'Segoe UI', sans-serif; 
        white-space: pre-wrap; 
        text-align: justify;
    }

    /* Cores dos Marcatextos */
    mark.diff { 
        background-color: #fff3cd; 
        color: #856404; 
        padding: 2px 4px; 
        border-radius: 4px; 
        border: 1px solid #ffeeba;
        font-weight: 500;
    } 
    mark.ort { 
        background-color: #f8d7da; 
        color: #721c24; 
        padding: 2px 4px; 
        border-radius: 4px; 
        border-bottom: 2px solid #dc3545;
        font-weight: bold; 
    } 
    mark.anvisa { 
        background-color: #d1ecf1; 
        color: #0c5460; 
        padding: 2px 4px; 
        border-radius: 4px; 
        border: 1px solid #bee5eb;
        font-weight: bold; 
    }

    /* Container de Comparação */
    .box-comparacao {
        padding: 15px;
        border-radius: 8px;
        height: 100%;
    }
    
    /* Box Esquerda (Referência) */
    .box-ref {
        background-color: #fdfdfe;
        border: 1px solid #e9ecef;
        border-left: 5px solid #6c757d; /* Cinza padrão, muda dinamicamente */
    }
    
    /* Box Direita (Validação) */
    .box-val {
        background-color: #ffffff;
        border: 1px solid #dee2e6;
        border-left: 5px solid #6c757d; /* Cinza padrão, muda dinamicamente */
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
</style>
""", unsafe_allow_html=True)

# ----------------- DADOS SIMULADOS (PARA TESTE VISUAL) -----------------
# Isso simula o que o backend retornaria
resultados_simulados = [
    {
        "titulo": "APRESENTAÇÕES",
        "status": "CONFORME",
        "ref": "Comprimidos revestidos de 50mg. Embalagem contendo 30 comprimidos.",
        "bel": "Comprimidos revestidos de 50mg. Embalagem contendo 30 comprimidos."
    },
    {
        "titulo": "COMPOSIÇÃO",
        "status": "DIVERGENTE",
        "ref": "Cada comprimido contém 50mg de diclofenaco sódico.",
        "bel": "Cada comprimido contém <mark class='diff'>100mg</mark> de diclofenaco sódico e <mark class='diff'>excipiente q.s.p</mark>."
    },
    {
        "titulo": "1. PARA QUE ESTE MEDICAMENTO É INDICADO?",
        "status": "DIVERGENTE",
        "ref": "Este medicamento é indicado para tratar inflamações.",
        "bel": "Este medicamento é indicado para tratar <mark class='ort'>inflamasões</mark>."
    },
    {
        "titulo": "DIZERES LEGAIS",
        "status": "VISUALIZACAO",
        "ref": "MS: 1.0000.0000.001-1",
        "bel": "MS: 1.0000.0000.001-1 <br><br> <mark class='anvisa'>Esta bula foi aprovada pela Anvisa em 15/10/2024</mark>"
    }
]

# ----------------- INTERFACE PRINCIPAL -----------------

st.title("📋 Relatório de Auditoria")
st.markdown("---")

# Métricas no topo
k1, k2, k3 = st.columns(3)
k1.metric("Total de Seções", "4")
k2.metric("Conformes", "1")
k3.metric("Divergentes", "2", delta_color="inverse")

st.write("") # Espaçamento

# Loop de Renderização das Seções
for res in resultados_simulados:
    status = res.get('status', 'ERRO')
    titulo = res.get('titulo', 'Seção')
    
    # Definição de Ícones e Cores
    if "CONFORME" in status:
        icon = "✅"
        cor_borda = "#28a745" # Verde
        label_status = "Aprovado"
    elif "DIVERGENTE" in status:
        icon = "⚠️"
        cor_borda = "#ffc107" # Amarelo
        label_status = "Atenção"
    elif "VISUALIZACAO" in status:
        icon = "👁️"
        cor_borda = "#17a2b8" # Azul
        label_status = "Visualização"
    else:
        icon = "❌"
        cor_borda = "#dc3545" # Vermelho
        label_status = "Erro"

    # O Expander (Acordeão)
    with st.expander(f"{icon} {titulo}", expanded=("DIVERGENTE" in status)):
        c_ref, c_val = st.columns(2)
        
        # Coluna da Esquerda (Referência/Arte)
        with c_ref:
            st.caption("📄 DOCUMENTO REFERÊNCIA")
            html_ref = f"""
            <div class='texto-bula box-comparacao box-ref' style='border-left-color: {cor_borda}'>
                {res.get('ref', '')}
            </div>
            """
            st.markdown(html_ref, unsafe_allow_html=True)

        # Coluna da Direita (Belfar/Gráfica)
        with c_val:
            st.caption("📄 DOCUMENTO GRÁFICA/BELFAR")
            html_val = f"""
            <div class='texto-bula box-comparacao box-val' style='border-left-color: {cor_borda}'>
                {res.get('bel', '')}
            </div>
            """
            st.markdown(html_val, unsafe_allow_html=True)
            
            # Legenda rápida se houver divergência
            if "DIVERGENTE" in status:
                st.caption(f"Status: {label_status}")

st.markdown("---")
st.caption("Sistema de Comparação Visual v5.3")
