import re
import streamlit as st
import pyodbc
import datetime
from PIL import Image
from dotenv import load_dotenv
import os
import io
from rembg import remove  # Biblioteca para remover fundo da imagem
import smtplib
from email.message import EmailMessage
from streamlit_js_eval import streamlit_js_eval
import cv2
from PIL import Image, ImageEnhance, ImageFilter  # Mantenha este import no topo do arquivo

# Carregar variáveis do arquivo .env
load_dotenv()

def conectar_banco():
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={os.getenv('DB_SERVER')};"
        f"DATABASE={os.getenv('DB_DATABASE')};"
        f"UID={os.getenv('DB_USER')};"
        f"PWD={os.getenv('DB_PASSWORD')}"
    )
    return pyodbc.connect(conn_str)

# Configuração da página
st.set_page_config(page_title='Dinatec - Canhoto Nota Fiscal', 
                   layout='wide', 
                   page_icon=':truck:',
                   initial_sidebar_state="collapsed",
                   )

# Função para capturar imagem da câmera
def capturar_imagem():
    cap = cv2.VideoCapture(0)
    st.info("Pressione 'Espaço' para capturar a imagem e 'Esc' para sair.")
    img = None
    while True:
        ret, frame = cap.read()
        if not ret:
            st.error("Não foi possível acessar a câmera.")
            break
        cv2.imshow("Captura de Imagem", frame)
        key = cv2.waitKey(1)
        if key % 256 == 27:  # ESC
            break
        elif key % 256 == 32:  # Espaço
            img = frame
            break
    cap.release()
    cv2.destroyAllWindows()
    return img


# Função para validar e-mail
def validar_email(email):
    padrao_email = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(padrao_email, email) is not None

# Função para verificar duplicidade de nota fiscal
def verificar_nota_existente(nota_fiscal):
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) FROM NotaFiscaisCanhotoSJRP
        WHERE NumeroNota = ?
        """,
        (nota_fiscal,)
    )
    existe = cursor.fetchone()[0] > 0
    conn.close()
    return existe

# Função para salvar imagem com fundo removido no banco de dados
def salvar_imagem_no_banco(imagem, nota_fiscal):
    if imagem.mode != 'RGB':
        imagem = imagem.convert('RGB')

    # Remove o fundo da imagem usando rembg
    img_byte_arr = io.BytesIO()
    imagem.save(img_byte_arr, format='PNG')  # Converte para PNG para permitir transparência
    img_byte_arr = img_byte_arr.getvalue()
    img_tratada = remove(img_byte_arr)  # Remove o fundo usando rembg

    conn = conectar_banco()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO NotaFiscaisCanhotoSJRP (NumeroNota, Imagem, DataBipe)
            VALUES (?, ?, ?)
            """,
            (nota_fiscal, pyodbc.Binary(img_tratada), datetime.datetime.now())
        )
        conn.commit()
        st.success("Imagem salva com sucesso no banco de dados.")
    except Exception as e:
        st.error(f"Erro ao salvar imagem no banco de dados: {e}")
    finally:
        conn.close()

# Função para limpar a tela e atualizar o estado
def limpar_tela():
    st.session_state.captura_concluida = True
    st.session_state.recarregar = True

# Função para contar canhotos
def contar_canhotos():
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM NotaFiscaisCanhotoSJRP")
    quantidade = cursor.fetchone()[0]
    conn.close()
    return quantidade

# Função para consultar o canhoto no banco de dados
def consultar_canhoto(numero_nota):
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT Imagem, DataBipe
        FROM NotaFiscaisCanhotoSJRP
        WHERE NumeroNota = ?
        """,
        (numero_nota,)
    )
    resultado = cursor.fetchone()
    conn.close()
    return resultado

# Função para envio de e-mail pelo servidor cPanel
def enviar_email_cpanel(destinatario, assunto, mensagem, imagem_bytes, nome_imagem):
    email_origem = os.getenv("EMAIL_ORIGEM")
    senha_email = os.getenv("EMAIL_SENHA")
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT"))

    msg = EmailMessage()
    msg['From'] = email_origem
    msg['To'] = destinatario
    msg['Subject'] = assunto
    msg.set_content(mensagem, subtype='html')
    msg.add_attachment(imagem_bytes, maintype='image', subtype='png', filename=nome_imagem)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as smtp:
            smtp.starttls() 
            smtp.login(email_origem, senha_email)
            smtp.send_message(msg)
        st.success("E-mail enviado com sucesso!")
    except smtplib.SMTPException as e:
        st.error(f"Erro ao enviar e-mail: {e}")
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao enviar o e-mail: {e}")

# Interface do Streamlit
st.title("📌 Sistema de Captura e Consulta de Canhoto - Grupo Dinatec")

# Exibir logomarca no topo da página
def exibir_logo(logo_path="logo.jpg"):
    col1, col2, col3 = st.columns([1, 2, 3])  
    with col1:
        if os.path.exists(logo_path):
            logo = Image.open(logo_path)
            st.image(logo, width=220)
    with col2:
        quantidade_canhotos = contar_canhotos()
        st.markdown(f"<h3 style='text-align: center; font-weight:bold'>Qtd. Canhotos:<br>🔗{quantidade_canhotos}</h3>", unsafe_allow_html=True)

    with col3:
        hora_atual = datetime.datetime.now().strftime("%H:%M:%S")
        st.markdown(f"<h3 style='text-align: center; font-weight:bold'>Empresa<br>São José do Rio Preto<br></h3>", unsafe_allow_html=True)

"""Função para otimizar automaticamente a qualidade da imagem"""
def otimizar_imagem(imagem):
    try:
        # Aplica nitidez
        enhancer_nitidez = ImageEnhance.Sharpness(imagem)
        imagem = enhancer_nitidez.enhance(1.5)  # Valor otimizado para nitidez
        
        # Ajusta contraste
        enhancer_contraste = ImageEnhance.Contrast(imagem)
        imagem = enhancer_contraste.enhance(0.4)  # Valor otimizado para contraste
        
        # Ajusta brilho
        enhancer_brilho = ImageEnhance.Brightness(imagem)
        imagem = enhancer_brilho.enhance(2.4)  # Valor otimizado para brilho
        
        # Aplica filtro de nitidez adicional
        imagem = imagem.filter(ImageFilter.SHARPEN)
        
        # Aplica um filtro de detalhes
        imagem = imagem.filter(ImageFilter.DETAIL)
        
        return imagem
    except Exception as e:
        st.error(f"Erro ao otimizar imagem: {str(e)}")
        return imagem

exibir_logo("logo.jpg")

# Menu de navegação
pagina = st.sidebar.selectbox("Selecione a página", ["📸 Captura de Imagem", "🔍 Consulta de Canhoto", "📩 Envio de E-mail"])

if pagina == "📸 Captura de Imagem":
    st.header("📸 Captura Imagem - Canhoto Nota Fiscal")

    # Entrada de dados para o número da nota fiscal com validação
    nota_fiscal = st.text_input("☑️ Número da Nota Fiscal", max_chars=50, placeholder="Digite o número da nota fiscal aqui")

    # Verificar se a nota fiscal existe e exibir o resultado
    if nota_fiscal and nota_fiscal.isdigit():
        nota_existente = verificar_nota_existente(nota_fiscal)
        
        if nota_existente:
            st.warning("⚠️ Nota fiscal já gravada no banco de dados.")
        else:
            # Criar duas colunas para câmera e upload
            col1, col2 = st.columns(2)

            with col1:
            # Câmera com tamanho ajustado
                camera_image = st.camera_input(
                    "Tire uma foto com a câmera",
                    key="camera",)

            if camera_image is not None:
                try:
                    # Abre a imagem
                    img_tratada = Image.open(camera_image)

                    # Aplica otimizações automáticas
                    img_tratada = otimizar_imagem(img_tratada)
        
                    # Opção de rotação
                    rotacao = st.radio(
                                "Selecione a orientação da imagem:",
                                ["Original", "Rotação 90°", "Rotação 180°", "Rotação 270°"],
                                horizontal=True
                                )
        
                    # Aplica a rotação escolhida
                    if rotacao == "Rotação 90°":
                        img_tratada = img_tratada.transpose(Image.Transpose.ROTATE_90)
                    elif rotacao == "Rotação 180°":
                        img_tratada = img_tratada.transpose(Image.Transpose.ROTATE_180)
                    elif rotacao == "Rotação 270°":
                        img_tratada = img_tratada.transpose(Image.Transpose.ROTATE_270)
        
                    # Ajusta o tamanho máximo
                    max_width = 2000
                    ratio = max_width / img_tratada.size[0]
                    new_size = (max_width, int(img_tratada.size[1] * ratio))
                    img_tratada = img_tratada.resize(new_size, Image.Resampling.LANCZOS)
        
                    # Exibe a imagem
                    st.image(
                        img_tratada,
                        caption="Imagem Capturada pela Câmera",
                        use_column_width=True,
                        )
        
                    # Botão para salvar imagem da câmera
                    if st.button("☑️ Salvar Imagem da Câmera"):
                        with st.spinner("Salvando imagem..."):
                            salvar_imagem_no_banco(img_tratada, nota_fiscal)
                            limpar_tela()
                            streamlit_js_eval(js_expressions="parent.window.location.reload()")
                except Exception as e:
                    st.error(f"Erro ao processar a imagem: {str(e)}")

            with col2:
                # Upload de arquivo
                st.info("📱 Para alta resolução, capture a imagem externamente e faça o upload abaixo.")
                image_data = st.file_uploader("Envie a imagem do canhoto em alta resolução", type=["jpg", "jpeg", "png"])
                
                if image_data is not None:
                    img_tratada = Image.open(image_data)
                    st.image(
                        img_tratada,
                        caption="Imagem Carregada via Upload",
                        use_column_width=True,
                    )
                    
                    # Botão para salvar imagem do upload
                    if st.button("☑️ Salvar Imagem do Upload"):
                        with st.spinner("Salvando imagem..."):
                            salvar_imagem_no_banco(img_tratada, nota_fiscal)
                            limpar_tela()
                            streamlit_js_eval(js_expressions="parent.window.location.reload()")

    elif nota_fiscal:
        st.error("⚠️ Por favor, insira apenas números para o número da nota fiscal.")

elif pagina == "🔍 Consulta de Canhoto":
    st.header("🔍 Consulta de Canhoto")
    numero_nota = st.number_input("✅ Número Nota Fiscal para consulta", min_value=0, step=1, format="%d", placeholder="Digite número nota fiscal aqui")

    if st.button("Consultar Canhoto"):
        resultado = consultar_canhoto(numero_nota)
        if resultado:
            imagem_binaria, data_bipe = resultado
            st.write(f"Data Bipe: {data_bipe}")
            if imagem_binaria:
                image = Image.open(io.BytesIO(imagem_binaria))
                st.image(image, caption="Canhoto Consultado", use_column_width=True)
            else:
                st.error("⚠️ Imagem não encontrada para essa nota fiscal.")
        else:
            st.error("⚠️ Nenhum registro encontrado para número nota fiscal fornecido.")

elif pagina == "📩 Envio de E-mail":
    st.header("📩 Envio de E-mail com Canhoto")
    email_destino = st.text_input("🧑‍💼 Destinatário:", placeholder="Digite o e-mail do destinatário")
    if email_destino and not validar_email(email_destino):
        st.error("⚠️ O e-mail informado não é válido.")
    assunto_email = st.text_input("📝 Assunto do e-mail:", "Canhoto de Nota Fiscal")
    numero_nota = st.number_input("🗂️ Digite número Nota Fiscal:", min_value=0, step=1, format="%d", placeholder="Digite o número da Nota Fiscal para envio")
    resultado = None

    if numero_nota:
        resultado = consultar_canhoto(numero_nota)
        if resultado:
            imagem_binaria, data_bipe = resultado
            st.write(f"Data do Bipe: {data_bipe}")
            if imagem_binaria:
                image = Image.open(io.BytesIO(imagem_binaria))
                st.image(image, caption="Canhoto da Nota Fiscal", use_column_width=True)
            else:
                st.error("⚠️ Imagem não encontrada para essa nota fiscal.")
        else:
            st.error("⚠️ Nenhum registro encontrado para o número de nota fiscal fornecido.")

    if resultado and email_destino and assunto_email:
        if st.button("Enviar por E-mail"):
            with st.spinner("Enviando e-mail..."):
                enviar_email_cpanel(
                    destinatario=email_destino,
                    assunto=assunto_email,
                    mensagem=f"<p>Segue em anexo o canhoto da Nota Fiscal {numero_nota}.</p>",
                    imagem_bytes=io.BytesIO(imagem_binaria).getvalue(),
                    nome_imagem=f"Canhoto_{numero_nota}.png"
                )
                limpar_tela()

# Rodapé da página
footer = """
<style>
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: white;
        color: black;
        text-align: center;
        padding: 10px;
    }
    .main > div {
        padding-bottom: 150px;
    }
</style>
<div class="footer">
    Desenvolvido.: Dinatec peças e serviços | <a href="mailto:thiago.panuto@dinatec.com.br">Suporte</a>
</div>
"""
st.markdown(footer, unsafe_allow_html=True)
