import streamlit as st
import google.generativeai as genai
from PIL import Image
import fitz  # PyMuPDF
import io
import json
import re

# ----------------- CONFIGURAÇÃO VISUAL (ESTILO MISTRAL) -----------------
st.set_page_config(page_title="Validador Visual", page_icon="💊", layout="wide")

st.markdown("""
<style>
    /* Estilo Geral */
    .main { background-color: #f4f6f8; }
    
    /* Estilo das Caixas de Texto */
    .texto-bula { 
        font-size: 0.9rem; 
        line-height: 1.5; 
        color: #333; 
        font-family: 'Segoe UI', sans-serif; 
        white-space: pre-wrap; 
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #ddd;
        height: 100%;
    }

    /* Marcadores (Amarelo, Vermelho, Azul) */
    .highlight-yellow { 
        background-color: #fff3cd; color: #856404; 
        padding: 2px 4px; border-radius: 4px; border: 1px solid #ffeeba; 
        font-weight: bold;
    }
    .highlight-red { 
        background-color: #f8d7da; color: #721c24; 
        padding: 2px 4px; border-radius: 4px; border: 1px solid #f5c6cb; 
        text-decoration: underline wavy red; font-weight: bold;
    }
    .highlight-blue { 
        background-color: #d1ecf1; color: #0c5460; 
        padding: 2px 4px; border-radius: 4px; border: 1px solid #bee5eb; 
        font-weight: bold;
    }

    /* Bordas laterais coloridas para status */
    .border-ok { border-left: 5px solid #28a745 !important; }
    .border-warn { border-left: 5px solid #ffc107 !important; }
    .border-info { border-left: 5px solid #17a2b8 !important; }
</style>
""", unsafe_allow_html=True)

# ----------------- CONFIGURAÇÃO DO MODELO -----------------
MODELO_FIXO = "models/gemini-flash-latest"

def setup_gemini():
    keys = [st.secrets.get("GEMINI_API_KEY"), st.secrets.get("GEMINI_API_KEY2")]
    valid_keys = [k for k in keys if k]
    if not valid_keys: return None
    
    for k in valid_keys:
        try:
            genai.configure(api_key=k)
            return genai.GenerativeModel(MODELO_FIXO, generation_config={"response_mime_type": "application/json"})
        except: continue
    return None

# ----------------- PROCESSAMENTO DE ARQUIVOS -----------------
def pdf_to_images(uploaded_file):
    try:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        images = []
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            images.append(Image.open(io.BytesIO(pix.tobytes("jpeg"))))
        return images
    except: return []

SECOES_PACIENTE = [
    "APRESENTAÇÕES", "COMPOSIÇÃO", 
    "PARA QUE ESTE MEDICAMENTO É INDICADO", "COMO ESTE MEDICAMENTO FUNCIONA?", 
    "QUANDO NÃO DEVO USAR ESTE MEDICAMENTO?", "O QUE DEVO SABER ANTES DE USAR ESTE MEDICAMENTO?", 
    "ONDE, COMO E POR QUANTO TEMPO POSSO GUARDAR ESTE MEDICAMENTO?", "COMO DEVO USAR ESTE MEDICAMENTO?", 
    "O QUE DEVO FAZER QUANDO EU ME ESQUECER DE USAR ESTE MEDICAMENTO?", 
    "QUAIS OS MALES QUE ESTE MEDICAMENTO PODE CAUSAR?", 
    "O QUE FAZER SE ALGUEM USAR UMA QUANTIDADE MAIOR DO QUE A INDICADA DESTE MEDICAMENTO?", 
    "DIZERES LEGAIS"
]

# ----------------- UI PRINCIPAL -----------------
st.title("💊 Validador Lado a Lado (Gemini Flash)")

c1, c2 = st.columns(2)
f1 = c1.file_uploader("📄 Arte (Referência)", type=["pdf", "jpg", "png"])
f2 = c2.file_uploader("📄 Gráfica (Prova)", type=["pdf", "jpg", "png"])

if st.button("🚀 Comparar Seções"):
    if f1 and f2:
        model = setup_gemini()
        if not model:
            st.error("Erro na API Key.")
            st.stop()
            
        with st.spinner("Processando imagens e estruturando JSON..."):
            imgs1 = pdf_to_images(f1) if f1.name.endswith(".pdf") else [Image.open(f1)]
            imgs2 = pdf_to_images(f2) if f2.name.endswith(".pdf") else [Image.open(f2)]
            
            # Prompt focado em JSON para separar as colunas
            prompt = f"""
            Você é um auditor farmacêutico. Analise as imagens da ARTE e da GRÁFICA.
            Extraia e compare o texto de cada uma destas seções: {SECOES_PACIENTE}

            Retorne APENAS um JSON seguindo este esquema exato para cada seção:
            [
              {{
                "titulo": "NOME DA SEÇÃO",
                "texto_arte": "Texto extraído da arte (OCR puro)",
                "texto_grafica": "Texto da gráfica com tags HTML de destaque",
                "status": "CONFORME ou DIVERGENTE"
              }}
            ]

            REGRAS PARA O 'texto_grafica':
            1. Use <span class="highlight-yellow">TEXTO</span> para divergências de conteúdo (frases a mais/menos).
            2. Use <span class="highlight-red">TEXTO</span> para erros de português.
            3. Na seção DIZERES LEGAIS, use <span class="highlight-blue">DATA</span> para a data da Anvisa.
            4. Se o texto for igual, não use tags.
            """
            
            payload = [prompt, "--- ARTE ---"] + imgs1 + ["--- GRAFICA ---"] + imgs2
            
            try:
                response = model.generate_content(payload)
                dados = json.loads(response.text)
                
                # Renderização Visual Bonita
                st.write("")
                conforme = sum(1 for d in dados if d['status'] == 'CONFORME')
                divergente = sum(1 for d in dados if d['status'] != 'CONFORME')
                
                k1, k2, k3 = st.columns(3)
                k1.metric("Total Seções", len(dados))
                k2.metric("Conformes", conforme)
                k3.metric("Atenção", divergente, delta_color="inverse")
                st.divider()

                for item in dados:
                    status = item.get('status', 'DIVERGENTE')
                    titulo = item.get('titulo', 'Seção')
                    ref_text = item.get('texto_arte', '...')
                    val_text = item.get('texto_grafica', '...')
                    
                    # Define cor da borda e ícone
                    css_class = "border-ok" if status == "CONFORME" else "border-warn"
                    icon = "✅" if status == "CONFORME" else "⚠️"
                    if "DIZERES LEGAIS" in titulo: 
                        icon = "👁️"
                        css_class = "border-info"

                    # Layout Lado a Lado (Side by Side) dentro do Expander
                    with st.expander(f"{icon} {titulo}", expanded=(status != "CONFORME")):
                        col_a, col_b = st.columns(2)
                        
                        with col_a:
                            st.caption("📄 Arte (Original)")
                            st.markdown(f"""
                            <div class="texto-bula {css_class}">
                                {ref_text}
                            </div>
                            """, unsafe_allow_html=True)
                            
                        with col_b:
                            st.caption("📄 Gráfica (Validação)")
                            st.markdown(f"""
                            <div class="texto-bula {css_class}">
                                {val_text}
                            </div>
                            """, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Erro ao processar: {e}")
                # Fallback para mostrar o texto cru se o JSON falhar
                if 'response' in locals(): st.text(response.text)

    else:
        st.warning("Envie os arquivos.")
