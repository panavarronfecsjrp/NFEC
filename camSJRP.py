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

# Função para validar e-mail
def validar_email(email):
    # Expressão regular para validar o formato do e-mail
    padrao_email = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(padrao_email, email) is not None

# Função para carregar e exibir a logomarca e a hora
def exibir_logo(logo_path="logo.jpg"):
    col1, col2, col3 = st.columns([1, 2, 3])  # Cria duas colunas para layout
    with col1:
        if os.path.exists(logo_path):
            logo = Image.open(logo_path)
            st.image(logo, width=220)  # Exibe a logomarca com largura ajustável
    with col2:
        quantidade_canhotos = contar_canhotos()
        st.markdown(f"<h3 style='text-align: center; font-weight:bold'>Qtd. Canhotos:<br>🔗{quantidade_canhotos}</h3>", unsafe_allow_html=True)

    with col3:
        hora_atual = datetime.datetime.now().strftime("%H:%M:%S")
        st.markdown(f"<h3 style='text-align: center; font-weight:bold'>Empresa<br>São José do Rio Preto<br></h3>", unsafe_allow_html=True)

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


def salvar_imagem_no_banco(imagem, nota_fiscal):
    if imagem.mode == 'RGBA':
        imagem = imagem.convert('RGB')

        # Remover o fundo da imagem
        img_byte_arr = io.BytesIO()
        imagem.save(img_byte_arr, format='PNG')  # Converte para PNG para permitir transparência
        img_byte_arr = img_byte_arr.getvalue()
        img_tratada = remove(img_byte_arr)  # Remove o fundo usando rembg

    img_byte_arr = io.BytesIO()
    imagem.save(img_byte_arr, format='JPEG')
    img_byte_arr = img_byte_arr.getvalue()

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

# Função para contar canhotos
def contar_canhotos():
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM NotaFiscaisCanhotoSJRP")
    quantidade = cursor.fetchone()[0]
    conn.close()
    return quantidade

# Função para limpar a tela e atualizar o estado
def limpar_tela():
    st.session_state.captura_concluida = True
    st.session_state.recarregar = True

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

def enviar_email_cpanel(destinatario, assunto, mensagem, imagem_bytes, nome_imagem):
    # Configurações do servidor de e-mail no cPanel
    email_origem = os.getenv("EMAIL_ORIGEM")
    senha_email = os.getenv("EMAIL_SENHA")
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT"))

    # Configura o e-mail
    msg = EmailMessage()
    msg['From'] = email_origem
    msg['To'] = destinatario
    msg['Subject'] = assunto
    msg.set_content(mensagem, subtype='html')

    # Anexa a imagem
    msg.add_attachment(imagem_bytes, maintype='image', subtype='jpeg', filename=nome_imagem)

    # Envia o e-mail usando TLS (porta 587)
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as smtp:
            smtp.starttls()  # Inicia a conexão TLS
            smtp.login(email_origem, senha_email)
            smtp.send_message(msg)
        st.success("E-mail enviado com sucesso!")
    except smtplib.SMTPException as e:
        st.error(f"Erro ao enviar e-mail: {e}")
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao enviar o e-mail: {e}")

# Código para mover o texto para o rodapé
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
    /* Garantindo que o rodapé fique no topo de outros elementos */
    .main > div {
        padding-bottom: 150px; /* ajuste conforme necessário */
    }
</style>
<div class="footer">
    Desenvolvido.: Dinatec peças e serviços | <a href="mailto:thiago.panuto@dinatec.com.br">Suporte</a>
</div>
"""
# Exibir logomarca no topo da página
exibir_logo("logo.jpg")

# Interface do Streamlit
st.title("📌 Sistema de Captura e Consulta de Canhoto - Grupo Dinatec")

# Menu de navegação
pagina = st.sidebar.selectbox("Selecione a página", ["📸 Captura de Imagem", "🔍 Consulta de Canhoto", "📩 Envio de E-mail"])

if pagina == "📸 Captura de Imagem":
    st.header("📸 Captura Imagem - Canhoto Nota Fiscal")

    # Entrada de dados para o número da nota fiscal com validação
    nota_fiscal = st.text_input("☑️ Número da Nota Fiscal", max_chars=50, placeholder="Digite o número da nota fiscal aqui")

    # Validação para permitir apenas números
    if nota_fiscal and not nota_fiscal.isdigit():
        st.error("⚠️ Por favor, insira apenas números para o número da nota fiscal.")
    else:
        # Variável para verificar se a nota fiscal já existe
        nota_existente = False

        # Verifica a duplicidade ao digitar o número da nota fiscal
        if nota_fiscal:
            nota_existente = verificar_nota_existente(nota_fiscal)
            if nota_existente:
                st.warning("⚠️ Nota fiscal já gravada no banco de dados.")
        
        # Exibe o uploader de imagem somente se a nota fiscal não for duplicada
        if not nota_existente and nota_fiscal:
            image_data = st.camera_input("Capture a imagem do canhoto")

            if image_data is not None:
                image = Image.open(image_data)
                st.image(image, caption="Imagem Capturada", use_column_width=True)

                # Salva a imagem no banco de dados
                if st.button("☑️ Salvar Imagem"):
                    with st.spinner("Salvando imagem..."):
                        salvar_imagem_no_banco(image, nota_fiscal)
                        limpar_tela()

                        # Força a atualização da página com JavaScript
                        streamlit_js_eval(js_expressions="parent.window.location.reload()")
        elif nota_existente:
            st.info("⚠️ Insira um novo número de nota fiscal para capturar uma nova imagem.")

elif pagina == "🔍 Consulta de Canhoto":
    st.header("🔍 Consulta de Canhoto")

    # Entrada de dados para consulta
    numero_nota = st.number_input("✅ Número Nota Fiscal para consulta", min_value=0, step=1, format="%d", placeholder="Digite número nota fiscal aqui")

    if st.button("Consultar Canhoto"):
        if numero_nota:
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

    # Campos para inserção de dados
    email_destino = st.text_input("🧑‍💼 Destinatário:", placeholder="Digite o e-mail do destinatário")
    # Validação do e-mail
    if email_destino and not validar_email(email_destino):
        st.error("⚠️ O e-mail informado não é válido. Por favor, insira um e-mail correto.")
    assunto_email = st.text_input("📝 Assunto do e-mail:", "Canhoto de Nota Fiscal")
    numero_nota = st.number_input("🗂️ Digite número Nota Fiscal:", min_value=0, step=1, format="%d", placeholder="Digite o número da Nota Fiscal para envio")
    
    # Variável para armazenar o resultado da consulta
    resultado = None

    # Consulta o canhoto ao digitar o número da nota fiscal
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

    # Botão para envio de e-mail
    if resultado and email_destino and assunto_email:
        if st.button("Enviar por E-mail"):
            with st.spinner("Enviando e-mail..."):
                enviar_email_cpanel(
                    destinatario=email_destino,
                    assunto=assunto_email,
                    mensagem=f"<p>Segue em anexo o canhoto da Nota Fiscal {numero_nota}.</p>",
                    imagem_bytes=io.BytesIO(imagem_binaria).getvalue(),
                    nome_imagem=f"Canhoto_{numero_nota}.jpeg"
                )
                limpar_tela()
        
                # Força a atualização da página com JavaScript
                streamlit_js_eval(js_expressions="parent.window.location.reload()")
    else:
        st.info("🖥️ Preencha e-mail, assunto e a nota fiscal para prosseguir.")
        
st.markdown(footer, unsafe_allow_html=True)