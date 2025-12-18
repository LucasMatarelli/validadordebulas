import streamlit as st
import google.generativeai as genai
from google.api_core import exceptions
from PIL import Image
import fitz  # PyMuPDF
import io
import time
import json
import re

# ----------------- CONFIGURAÇÃO DA PÁGINA -----------------
st.set_page_config(
    page_title="Validador de Bulas (Flash Latest)",
    page_icon="💊",
    layout="wide"
)

# ----------------- ESTILOS CSS (INTERFACE "BONITINHA") -----------------
st.markdown("""
<style>
    /* Ajustes Gerais */
    .main { background-color: #f4f6f8; }
    .block-container { padding-top: 20px !important; }
    
    /* Estilo dos Cards de Texto */
    .texto-bula { 
        font-size: 0.95rem; 
        line-height: 1.6; 
        color: #2c3e50; 
        font-family: 'Segoe UI', sans-serif; 
        white-space: pre-wrap; 
        text-align: justify;
    }

    /* Cores dos Marcatextos (Compatível com o Prompt) */
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

    /* Boxes de Comparação */
    .box-ref {
        background-color: #fdfdfe;
        border: 1px solid #e9ecef;
        border-left: 5px solid #6c757d;
        padding: 15px; border-radius: 8px; height: 100%;
    }
    .box-val {
        background-color: #ffffff;
        border: 1px solid #dee2e6;
        border-left: 5px solid #6c757d;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        padding: 15px; border-radius: 8px; height: 100%;
    }
    
    /* Header Personalizado */
    h1 { color: #55a68e; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ----------------- CONFIGURAÇÃO DO MODELO -----------------
MODELO_FIXO = "models/gemini-flash-latest"

def setup_model():
    keys = [st.secrets.get("GEMINI_API_KEY"), st.secrets.get("GEMINI_API_KEY2")]
    valid_keys = [k for k in keys if k]
    if not valid_keys: return None, "Sem chaves."
    
    for api_key in valid_keys:
        try:
            genai.configure(api_key=api_key)
            # JSON Mode ativado para garantir estrutura
            model = genai.GenerativeModel(
                MODELO_FIXO, 
                generation_config={"response_mime_type": "application/json", "temperature": 0.1}
            )
            return api_key, model
        except: continue
    return None, "Erro conexão."

# ----------------- FUNÇÃO DE RETRY -----------------
def generate_with_retry(model, payload, max_retries=3):
    for attempt in range(max_retries):
        try:
            return model.generate_content(payload)
        except exceptions.ResourceExhausted as e:
            wait_time = 30
            st.warning(f"⚠️ Pico de uso no Google (Erro 429). Aguardando {wait_time}s...")
            time.sleep(wait_time)
        except Exception as e:
            st.error(f"Erro: {e}")
            return None
    return None

# ----------------- UTILITÁRIOS -----------------
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

# ----------------- INTERFACE -----------------
with st.sidebar:
    st.title("Validador Belfar")
    key, model = setup_model()
    if key: st.success(f"Conectado: {MODELO_FIXO}")
    else: st.error("Erro na API Key"); st.stop()

st.markdown("<h1>Validador de Bulas (Seção a Seção)</h1>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
f1 = c1.file_uploader("📂 Arte (Referência)", type=["pdf", "jpg", "png"], key="f1")
f2 = c2.file_uploader("📂 Gráfica (Prova)", type=["pdf", "jpg", "png"], key="f2")

if st.button("🚀 INICIAR AUDITORIA"):
    if f1 and f2:
        with st.status("🔄 Processando...", expanded=True) as status:
            st.write("📸 Extraindo imagens e lendo textos...")
            imgs1 = pdf_to_images(f1) if f1.name.endswith(".pdf") else [Image.open(f1)]
            imgs2 = pdf_to_images(f2) if f2.name.endswith(".pdf") else [Image.open(f2)]
            
            st.write("🤖 Analisando divergências e ortografia...")
            
            prompt = f"""
            Você é um auditor farmacêutico. Analise as imagens.
            Retorne APENAS um JSON com a lista de seções comparadas.
            
            Lista de Seções Obrigatórias: {SECOES_PACIENTE}
            
            Estrutura do JSON desejado:
            [
              {{
                "titulo": "NOME DA SEÇÃO",
                "status": "CONFORME" ou "DIVERGENTE" ou "ATENCAO",
                "ref": "Texto completo extraído do documento de Referência (Arte)",
                "bel": "Texto completo extraído do documento da Gráfica, COM TAGS HTML"
              }},
              ...
            ]
            
            REGRAS PARA O CAMPO 'bel' (Texto da Gráfica):
            1. Se houver divergência (texto extra, faltante ou diferente), envolva a parte diferente com: <mark class='diff'>TEXTO</mark>
            2. Se houver erro de português ou digitação, envolva com: <mark class='ort'>ERRO</mark>
            3. Na seção 'DIZERES LEGAIS', envolva a data de aprovação da Anvisa com: <mark class='anvisa'>Esta bula foi aprovada... (DATA)</mark>
            
            Se o texto for idêntico, apenas transcreva sem tags (exceto a data da anvisa).
            """
            
            payload = [prompt, "--- ARTE (REF) ---"] + imgs1 + ["--- GRÁFICA (BEL) ---"] + imgs2
            
            response = generate_with_retry(model, payload)
            
            if response:
                try:
                    # Limpeza básica caso o modelo envie markdown ```json
                    text_resp = response.text.replace("```json", "").replace("```", "")
                    data = json.loads(text_resp)
                    status.update(label="✅ Análise Concluída!", state="complete", expanded=False)
                    
                    # ---------------- RENDERIZAÇÃO LADO A LADO ----------------
                    st.divider()
                    
                    # Contadores
                    total = len(data)
                    divs = sum(1 for x in data if "DIVERGENTE" in x['status'] or "ATENCAO" in x['status'])
                    oks = total - divs
                    
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Seções Analisadas", total)
                    k2.metric("Conformes", oks)
                    k3.metric("Divergências", divs, delta_color="inverse")
                    
                    st.write("")
                    
                    for item in data:
                        titulo = item.get('titulo', 'Seção')
                        status_sec = item.get('status', 'ERRO')
                        ref_text = item.get('ref', '')
                        bel_text = item.get('bel', '')
                        
                        # Definição de Cores e Ícones
                        if "CONFORME" in status_sec:
                            icon = "✅"
                            cor = "#28a745"
                        elif "DIVERGENTE" in status_sec or "ATENCAO" in status_sec:
                            icon = "⚠️"
                            cor = "#ffc107"
                        else:
                            icon = "ℹ️"
                            cor = "#17a2b8" # Azul para Dizeres Legais geralmente
                        
                        # Acordeão
                        with st.expander(f"{icon} {titulo}", expanded=("DIVERGENTE" in status_sec)):
                            col_ref, col_bel = st.columns(2)
                            
                            with col_ref:
                                st.caption("📄 ARTE (REFERÊNCIA)")
                                st.markdown(f"""
                                <div class='texto-bula box-ref' style='border-left-color: {cor}'>
                                    {ref_text}
                                </div>
                                """, unsafe_allow_html=True)
                                
                            with col_bel:
                                st.caption("📄 GRÁFICA (PROVA)")
                                st.markdown(f"""
                                <div class='texto-bula box-val' style='border-left-color: {cor}'>
                                    {bel_text}
                                </div>
                                """, unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Erro ao processar o JSON do Gemini: {e}")
                    st.code(response.text) # Mostra o raw para debug
    else:
        st.warning("Anexe os arquivos.")
