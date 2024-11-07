import streamlit as st
import datetime
import io
import os
from PIL import Image, ImageEnhance
from dotenv import load_dotenv
from rembg import remove
import pyodbc
import re
import smtplib
from email.message import EmailMessage

# Carregar variáveis do arquivo .env
load_dotenv()

# Função de conexão com o banco de dados
def conectar_banco():
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={os.getenv('DB_SERVER')};"
        f"DATABASE={os.getenv('DB_DATABASE')};"
        f"UID={os.getenv('DB_USER')};"
        f"PWD={os.getenv('DB_PASSWORD')}"
    )
    return pyodbc.connect(conn_str)

# Função para capturar e ajustar a imagem
def capturar_ajustar_imagem():
    camera_image = st.camera_input("Capture uma foto")
    
    if camera_image:
        # Abrir e exibir a imagem
        img = Image.open(camera_image)
        st.image(img, caption="Imagem Original Capturada", use_column_width=True)

        # Ajustes de brilho, contraste e nitidez
        st.markdown("### Ajustes de Imagem")
        brilho = st.slider("Ajuste o Brilho", 0.5, 3.0, 1.0)
        contraste = st.slider("Ajuste o Contraste", 0.5, 3.0, 1.0)
        nitidez = st.slider("Ajuste a Nitidez", 0.5, 3.0, 1.0)

        enhancer_brilho = ImageEnhance.Brightness(img)
        img = enhancer_brilho.enhance(brilho)
        
        enhancer_contraste = ImageEnhance.Contrast(img)
        img = enhancer_contraste.enhance(contraste)
        
        enhancer_nitidez = ImageEnhance.Sharpness(img)
        img = enhancer_nitidez.enhance(nitidez)

        # Exibir imagem ajustada
        st.image(img, caption="Imagem Ajustada", use_column_width=True)

        return img
    return None

# Função para remover o fundo e salvar a imagem no banco de dados
def salvar_imagem_no_banco(imagem, nota_fiscal):
    if imagem.mode != 'RGB':
        imagem = imagem.convert('RGB')

    # Converte a imagem para bytes e remove o fundo
    img_byte_arr = io.BytesIO()
    imagem.save(img_byte_arr, format='PNG')
    img_tratada = remove(img_byte_arr.getvalue()) 

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

# Função para validar e-mail
def validar_email(email):
    padrao_email = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(padrao_email, email) is not None

def consultar_canhoto(numero_nota):
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT Imagem, DataBipe
        FROM NotaFiscaisCanhoto
        WHERE NumeroNota = ?
        """,
        (numero_nota,)
    )
    resultado = cursor.fetchone()
    conn.close()
    return resultado


# Função para contar canhotos no banco
def contar_canhotos():
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM NotaFiscaisCanhotoSJRP")
    quantidade = cursor.fetchone()[0]
    conn.close()
    return quantidade

# Função para exibir o logotipo e contagem de canhotos
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
        st.markdown(f"<h3 style='text-align: center; font-weight:bold'>Empresa<br>São José do Rio Preto<br></h3>", unsafe_allow_html=True)

# Função para enviar e-mail com a imagem do canhoto
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

# Interface principal
st.title("📌 Sistema de Captura e Consulta de Canhoto - Grupo Dinatec")
exibir_logo("logo.jpg")

# Menu de navegação
pagina = st.sidebar.selectbox("Selecione a página", ["📸 Captura de Imagem", "🔍 Consulta de Canhoto", "📩 Envio de E-mail"])

if pagina == "📸 Captura de Imagem":
    st.header("📸 Captura Imagem - Canhoto Nota Fiscal")

    # Entrada de dados para o número da nota fiscal com validação
    nota_fiscal = st.text_input("☑️ Número da Nota Fiscal", max_chars=50, placeholder="Digite o número da nota fiscal aqui")

    # Verificar se a nota fiscal já existe
    if nota_fiscal and nota_fiscal.isdigit():
        nota_existente = verificar_nota_existente(nota_fiscal)
        
        if nota_existente:
            st.warning("⚠️ Nota fiscal já gravada no banco de dados.")
        else:
            # Captura e ajuste da imagem
            imagem_capturada = capturar_ajustar_imagem()
            
            # Botão para salvar a imagem ajustada
            if imagem_capturada and st.button("☑️ Salvar Imagem Ajustada"):
                with st.spinner("Salvando imagem..."):
                    salvar_imagem_no_banco(imagem_capturada, nota_fiscal)
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
    
    if numero_nota and email_destino and assunto_email:
        resultado = consultar_canhoto(numero_nota)
        if resultado:
            imagem_binaria, data_bipe = resultado
            st.write(f"Data do Bipe: {data_bipe}")
            if imagem_binaria:
                st.image(Image.open(io.BytesIO(imagem_binaria)), caption="Canhoto da Nota Fiscal", use_column_width=True)
                if st.button("Enviar por E-mail"):
                    with st.spinner("Enviando e-mail..."):
                        enviar_email_cpanel(
                            destinatario=email_destino,
                            assunto=assunto_email,
                            mensagem=f"<p>Segue em anexo o canhoto da Nota Fiscal {numero_nota}.</p>",
                            imagem_bytes=io.BytesIO(imagem_binaria).getvalue(),
                            nome_imagem=f"Canhoto_{numero_nota}.png"
                        )

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
    Desenvolvido por: Dinatec peças e serviços | <a href="mailto:thiago.panuto@dinatec.com.br">Suporte</a>
</div>
"""
st.markdown(footer, unsafe_allow_html=True)
