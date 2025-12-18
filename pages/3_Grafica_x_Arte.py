import streamlit as st
import google.generativeai as genai
from PIL import Image
import fitz  # PyMuPDF
import io
import json
import re

# ----------------- 1. CONFIGURAÇÃO VISUAL (CSS) -----------------
st.set_page_config(page_title="Validador Lado a Lado", page_icon="⚖️", layout="wide")

st.markdown("""
<style>
    /* Fundo geral */
    .main { background-color: #f4f6f8; }
    
    /* Estilo das Caixas de Texto (Bula) */
    .texto-bula { 
        font-size: 0.95rem; 
        line-height: 1.6; 
        color: #2c3e50; 
        font-family: 'Segoe UI', sans-serif; 
        white-space: pre-wrap; 
        background-color: white;
        padding: 20px;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        height: 100%; /* Garante altura igual */
    }

    /* MARCA-TEXTOS (Garante que funcionem no HTML injetado) */
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

    /* Bordas de Status */
    .border-ok { border-left: 6px solid #28a745 !important; }
    .border-warn { border-left: 6px solid #ffc107 !important; }
    .border-info { border-left: 6px solid #17a2b8 !important; }
</style>
""", unsafe_allow_html=True)

# ----------------- 2. CONFIGURAÇÃO MODELO (FLASH LATEST) -----------------
MODELO_FIXO = "models/gemini-flash-latest"

def setup_model():
    # Tenta pegar as chaves configuradas
    keys = [st.secrets.get("GEMINI_API_KEY"), st.secrets.get("GEMINI_API_KEY2")]
    valid_keys = [k for k in keys if k]
    if not valid_keys: return None
    
    # Configura com a primeira chave válida
    for api_key in valid_keys:
        try:
            genai.configure(api_key=api_key)
            return genai.GenerativeModel(MODELO_FIXO, generation_config={"response_mime_type": "application/json"})
        except: continue
    return None

# ----------------- 3. PROCESSAMENTO DE ARQUIVOS -----------------
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

# ----------------- 4. INTERFACE PRINCIPAL -----------------
st.title("⚖️ Comparador Visual (Lado a Lado)")
st.caption(f"Conectado em: {MODELO_FIXO}")

c1, c2 = st.columns(2)
f1 = c1.file_uploader("📂 Arte (Original)", type=["pdf", "jpg", "png"])
f2 = c2.file_uploader("📂 Gráfica (Prova)", type=["pdf", "jpg", "png"])

if st.button("🚀 Iniciar Comparação Lado a Lado"):
    if f1 and f2:
        model = setup_model()
        if not model:
            st.error("Chave API não encontrada ou inválida.")
            st.stop()

        with st.spinner("Lendo arquivos e gerando visualização..."):
            # Converte arquivos para lista de imagens
            imgs1 = pdf_to_images(f1) if f1.name.endswith(".pdf") else [Image.open(f1)]
            imgs2 = pdf_to_images(f2) if f2.name.endswith(".pdf") else [Image.open(f2)]
            
            # Prompt focado em JSON para permitir a montagem do layout
            prompt = f"""
            Atue como auditor de qualidade farmacêutica.
            Analise as imagens do CONJUNTO A (Referência) e CONJUNTO B (Prova).
            Extraia o texto e compare seção por seção.

            Lista de seções obrigatórias: {SECOES_PACIENTE}

            Retorne APENAS um JSON (array de objetos) com esta estrutura exata:
            [
              {{
                "titulo": "NOME DA SEÇÃO",
                "texto_arte": "Texto puro extraído da Arte",
                "texto_grafica": "Texto da Gráfica com as tags HTML de destaque aplicadas",
                "status": "CONFORME" (se igual) ou "DIVERGENTE" (se diferente)
              }}
            ]

            REGRAS DE HIGHLIGHT (Para o campo 'texto_grafica'):
            1. Divergências de conteúdo (frases a mais, a menos ou diferentes): use <span class="highlight-yellow">TEXTO</span>
            2. Erros de português/digitação: use <span class="highlight-red">TEXTO</span>
            3. Na seção DIZERES LEGAIS, destaque a data da Anvisa com: <span class="highlight-blue">DATA</span>
            """
            
            payload = [prompt, "--- ARTE ---"] + imgs1 + ["--- GRAFICA ---"] + imgs2
            
            try:
                # Chama o Gemini
                response = model.generate_content(payload)
                
                # Limpeza do JSON (caso venha com markdown ```json)
                clean_json = response.text.replace("```json", "").replace("```", "").strip()
                dados_auditados = json.loads(clean_json)

                # --- RENDERIZAÇÃO DA TELA ---
                st.write("")
                
                # Resumo
                total = len(dados_auditados)
                divergentes = sum(1 for d in dados_auditados if d.get('status') != 'CONFORME')
                conformes = total - divergentes
                
                k1, k2, k3 = st.columns(3)
                k1.metric("Seções Analisadas", total)
                k2.metric("Conformes", conformes)
                k3.metric("Com Divergências", divergentes, delta_color="inverse")
                
                st.divider()

                # Loop criando as caixas Lado a Lado
                for item in dados_auditados:
                    titulo = item.get('titulo', 'Seção Desconhecida')
                    status = item.get('status', 'DIVERGENTE')
                    t_arte = item.get('texto_arte', '')
                    t_grafica = item.get('texto_grafica', '')

                    # Define cor da borda e ícone baseado no status
                    if status == "CONFORME":
                        css_class = "border-ok"
                        icon = "✅"
                    elif "DIZERES LEGAIS" in titulo.upper():
                        css_class = "border-info"
                        icon = "👁️" # Olho para dizeres legais (validação visual)
                    else:
                        css_class = "border-warn"
                        icon = "⚠️"

                    # Cria o Expander
                    with st.expander(f"{icon} {titulo}", expanded=(status != "CONFORME")):
                        
                        # AQUI ESTÁ A MÁGICA DO LADO A LADO
                        col_esq, col_dir = st.columns(2)
                        
                        with col_esq:
                            st.caption("📄 Arte (Referência)")
                            # Renderiza o HTML com a classe CSS
                            st.markdown(f"""
                            <div class="texto-bula {css_class}">
                                {t_arte}
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col_dir:
                            st.caption("📄 Gráfica (Prova)")
                            # Renderiza o HTML com os highlights coloridos
                            st.markdown(f"""
                            <div class="texto-bula {css_class}">
                                {t_grafica}
                            </div>
                            """, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Erro ao processar o retorno do modelo: {e}")
                # Mostra o texto cru caso o JSON falhe, para debug
                st.text_area("Retorno Cru (Debug)", response.text)

    else:
        st.warning("Por favor, envie os dois arquivos para começar.")
