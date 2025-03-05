import pymysql
import datetime
import io
from PIL import Image
import re
import streamlit as st
from dotenv import load_dotenv
import os
import smtplib
from email.message import EmailMessage
from streamlit_js_eval import streamlit_js_eval
import cv2
from pyzbar.pyzbar import decode
import numpy as np
import easyocr

# Carregar variáveis do arquivo .env
load_dotenv()

# Configuração da página
st.set_page_config(page_title='Dinatec - Canhoto Nota Fiscal', 
                   layout='wide', 
                   page_icon=':truck:',
                   initial_sidebar_state="collapsed",
                   )

# Configuração para conectar ao MariaDB
def conectar_banco():
    try:
        # Tentar conectar ao banco de dados MariaDB
        conn = pymysql.connect(
            host="186.224.105.220",
            port=3306,
            user="panavarr",
            password="331sbA8g?",
            database="panavarr_",
            charset='utf8mb4'
        )
        return conn  # Retorne o objeto de conexão válido
    except pymysql.MySQLError as e:
        st.error(f"Erro ao conectar ao MariaDB: {e}")
        return None  # Retorne None em caso de erro

# Função para validar e-mail
def validar_email(email):
    # Expressão regular para validar o formato do e-mail
    padrao_email = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(padrao_email, email) is not None

# Função para criar um divisor colorido usando CSS
def colored_divider(color="#3498db", height="2px"):
    st.markdown(
        f"""
        <hr style="border:none; border-top:{height} solid {color};" />
        """,
        unsafe_allow_html=True
    )

# Função para carregar e exibir a logomarca e a hora
def exibir_logo(logo_path="logo.jpg"):
    col1, col2 = st.columns([1, 2])  # Cria duas colunas para layout
    with col1:
        if os.path.exists(logo_path):
            logo = Image.open(logo_path)
            st.image(logo, width=300)  # Exibe a logomarca com largura ajustável
    with col2:
        quantidade_canhotos = contar_canhotos()
        st.title("📌 Sistema Captura e Consulta Canhoto - Grupo Dinatec")

def verificar_nota_existente(nota_fiscal):
    conn = conectar_banco()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT COUNT(*) FROM notafiscaiscanhotosjrp
                WHERE NumeroNota = %s
                """,
                (nota_fiscal,)
            )
            existe = cursor.fetchone()[0] > 0
            return existe
        except Exception as e:
            st.error(f"Erro ao consultar a nota fiscal, favor informar novamente o numero da nota fiscal, e em caso de duvida procure o administrador do sistema. {e}")
        finally:
            cursor.close()
            conn.close()
    return False

def salvar_imagem_no_banco(imagem, nota_fiscal, info_envio):
    conn = conectar_banco()
    if conn:
        cursor = conn.cursor()
        try:
            if imagem.mode == 'RGBA':
                imagem = imagem.convert('RGB')
            
            # Convertendo imagem para formato binário
            img_byte_arr = io.BytesIO()
            imagem.save(img_byte_arr, format='JPEG')
            imagem_binaria = img_byte_arr.getvalue()

            # Obter a data/hora atual
            data_atual = datetime.datetime.now()

            # Inserindo no banco de dados
            cursor.execute(
                """
                INSERT INTO notafiscaiscanhotosjrp (NumeroNota, DataBipe, CaminhoImagem, Imagem, InfoEnvio)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (nota_fiscal, data_atual, "caminho_fake.jpg", imagem_binaria, info_envio)
            )
            conn.commit()
            st.success("Imagem salva com sucesso.")
        except Exception as e:
            st.error(f"Erro ao salvar imagem, favor procurar o administrador do sistema.  {e}")
        finally:
            cursor.close()
            conn.close()

def contar_canhotos():
    conn = conectar_banco()  # Função que conecta ao MariaDB
    if conn:  # Verifica se a conexão foi bem-sucedida
        try:
            with conn.cursor() as cursor:
                # Consulta para contar o número de registros na tabela
                cursor.execute("SELECT COUNT(*) FROM notafiscaiscanhotosjrp")
                quantidade = cursor.fetchone()[0]
                return quantidade
        except Exception as e:
            st.error(f"Erro ao contar canhotos, em caso de duvida procurar o administrador do sistema.{e}")
            return 0
        finally:
            conn.close()  # Garante que a conexão será fechada
    else:
        st.error("Não foi possível conectar ao banco, favor procurar o administrador do sistema.")
        return 0

# Função para limpar a tela e atualizar o estado
def limpar_tela():
    st.session_state.captura_concluida = True
    st.session_state.recarregar = True

# Consultar nota fiscal no MariaDB
def consultar_nota(nota_fiscal):
    conn = conectar_banco()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT Imagem, DataBipe
                FROM notafiscaiscanhotosjrp
                WHERE NumeroNota = %s
                """,
                (nota_fiscal,)
            )
            resultado = cursor.fetchone()
            if resultado:
                imagem_binaria, data_bipe = resultado
                return imagem_binaria, data_bipe
            return None, None
        except Exception as e:
            st.error(f"Erro ao consultar canhoto. {e}")
        finally:
            cursor.close()
            conn.close()
    return None, None

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

# Função para ler o código de barras
def ler_codigo_barras(imagem):
    # Converte a imagem para escala de cinza
    gray = cv2.cvtColor(np.array(imagem), cv2.COLOR_RGB2GRAY)
    
    # Inicializa o leitor OCR
    reader = easyocr.Reader(['pt'])
    
    # Tenta ler o texto na imagem
    results = reader.readtext(gray)
    
    # Retorna o primeiro texto encontrado que pareça ser um número de nota fiscal
    for (bbox, text, prob) in results:
        # Filtra para pegar apenas números que pareçam ser número de nota fiscal
        if text.isdigit() and len(text) > 5:
            return text
    
    return None

# Função para capturar e decodificar o código de barras
def capturar_codigo_barras():
    # Inicia a captura de vídeo
    cap = cv2.VideoCapture(0)  # 0 para a câmera padrão
    stframe = st.empty()  # Cria um espaço vazio para exibir o vídeo

    # Gera uma chave única para esta instância de captura
    unique_key = f"parar_captura_{datetime.datetime.now().timestamp()}"

    while True:
        ret, frame = cap.read()  # Lê um frame da câmera
        if not ret:
            st.error("Erro ao acessar a câmera.")
            break

        # Decodifica os códigos de barras no frame
        decoded_objects = decode(frame)
        for obj in decoded_objects:
            # Desenha um retângulo ao redor do código de barras
            (x, y, w, h) = obj.rect
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            # Retorna o texto do código de barras
            numero_nota = obj.data.decode('utf-8')
            st.success(f"Número da Nota Fiscal reconhecido: {numero_nota}")
            cap.release()  # Libera a câmera
            return numero_nota  # Retorna o número da nota fiscal

        # Exibe o frame na interface do Streamlit
        stframe.image(frame, channels="BGR", use_container_width=True)

        # Para a captura se o usuário clicar em um botão
        if st.button("Parar Captura", key=unique_key):
            break

    cap.release()  # Libera a câmera

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

    /* Estilização do botão flutuante do WhatsApp */
    .whatsapp-button {
        position: fixed;
        bottom: 80px;
        right: 20px;
        background-color: #25D366;
        color: white;
        border-radius: 50%;
        width: 60px;
        height: 60px;
        display: flex;
        justify-content: center;
        align-items: center;
        box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.2);
        z-index: 1000;
        transition: transform 0.3s;
        text-decoration: none !important;
        border: none;
    }

    .whatsapp-button:hover {
        transform: scale(1.1);
    }

    .whatsapp-icon {
        font-size: 36px;
        color: white;
    }
</style>

<div class="footer">
    Desenvolvido.: 🛡️ <a href="https://www.panavarro.com.br" target="_blank">Panavarro</a> | 📩 <a href="mailto:thiago@panavarro.com.br">Suporte</a>
</div>
<a href="https://wa.me/5516993253920" target="_blank" class="whatsapp-button">
    <i class="fab fa-whatsapp whatsapp-icon"></i>
</a>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
"""



# Exibir logomarca no topo da página
exibir_logo("logo.jpg")

# Menu de navegação
pagina = st.sidebar.selectbox("Selecione a página", ["📸 Captura de Imagem", "🔍 Consulta de Canhoto", "📩 Envio de E-mail", "🗂️ Salvar Nota Fiscal"])

# Adicionar conteúdo à barra lateral
with st.sidebar:
    with st.container():  # Organiza o layout no sidebar
        quantidade_canhotos = contar_canhotos()
    st.markdown(
        f"<h3 style='text-align: center; font-weight:bold'>"
        f"🏭 Sao Jose do Rio Preto<br>Qtd. Canhotos:<br>🔗{quantidade_canhotos}</h3>", unsafe_allow_html=True)

st.sidebar.divider()

if pagina == "📸 Captura de Imagem":
    st.header("📸 Captura Imagem - Canhoto Nota Fiscal")

    if st.button("📸 Iniciar Captura Automática"):
        numero_nota = capturar_codigo_barras()
        if numero_nota:
            # Aqui você pode usar o número da nota fiscal para verificar se existe no banco de dados
            nota_existente = verificar_nota_existente(numero_nota)
            # Continue com o fluxo normal...

    # Entrada de dados para o número da nota fiscal com validação
    nota_fiscal = st.number_input("☑️ Número da Nota Fiscal", min_value=0, step=1, format="%d", placeholder="Digite o número da nota fiscal aqui")

    # Verificar se a nota fiscal existe e exibir o resultado
    if nota_fiscal > 0:  # Verifica se a nota fiscal é um número positivo
        nota_existente = verificar_nota_existente(nota_fiscal)
        
        if nota_existente:
            st.warning("⚠️ Nota fiscal já gravada no banco de dados.")
        else:
            # Upload de arquivo
            st.info("📱 Para alta resolução, capture a imagem externamente e faça o upload abaixo.")
            image_tratada = st.file_uploader("Envie a imagem do canhoto em alta resolução", type=["jpg", "jpeg", "png"])

            if image_tratada is not None:
                # Carregar a imagem com PIL.Image
                img_tratada = Image.open(image_tratada)

                # Opção de rotação
                rotacao = st.radio(
                    "Selecione a orientação da imagem:",
                    ["Original", "Rotação 90°", "Rotação 180°", "Rotação 270°"],
                    horizontal=True
                )

                # Aplicar rotação, se necessário
                if rotacao == "Rotação 90°":
                    img_tratada = img_tratada.transpose(Image.Transpose.ROTATE_90)
                elif rotacao == "Rotação 180°":
                    img_tratada = img_tratada.transpose(Image.Transpose.ROTATE_180)
                elif rotacao == "Rotação 270°":
                    img_tratada = img_tratada.transpose(Image.Transpose.ROTATE_270)

                # Exibir imagem após rotação
                st.image(img_tratada, caption="Imagem Carregada via Upload", use_container_width=True)
                
                # Adicionar checkbox para selecionar Motorista ou Transportadora
                tipo_envio = st.radio("Selecione o tipo de envio:", ["Motorista", "Transportadora"])

                # Campo condicional para nome do motorista
                nome_motorista = ""
                if tipo_envio == "Motorista":
                    nome_motorista = st.text_input("Nome do Motorista:", placeholder="Digite o nome do motorista aqui", key="motorista")

                # Botão para salvar imagem do upload
                if st.button("☑️ Salvar Imagem do Upload"):
                    if tipo_envio == "Motorista" and not nome_motorista:
                        st.error("Por favor, insira o nome do motorista.")
                    else:
                        with st.spinner("Salvando imagem..."):
                            # Verifica se é motorista e adiciona o nome, se não, adiciona 'Transportadora'
                            info_envio = nome_motorista if tipo_envio == "Motorista" else "Transportadora"
                            salvar_imagem_no_banco(img_tratada, nota_fiscal, info_envio)  # Adiciona o terceiro parâmetro
                            limpar_tela()
                            streamlit_js_eval(js_expressions="parent.window.location.reload()")

elif pagina == "🔍 Consulta de Canhoto":
    st.header("🔍 Consulta de Canhoto")

    # Entrada de dados para consulta
    NumeroNota = st.number_input("✅ Número Nota Fiscal para consulta", min_value=0, step=1, format="%d", placeholder="Digite número nota fiscal aqui")

    if st.button("Consultar Canhoto"):
        if NumeroNota:
            resultado = consultar_nota(NumeroNota)
            if resultado:
                imagem_binaria, data_bipe = resultado
                st.write(f"Data Bipe: {data_bipe}")

                if imagem_binaria:
                    image = Image.open(io.BytesIO(imagem_binaria))
                    st.image(image, caption="Canhoto Consultado", use_container_width=True)
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
        resultado = consultar_nota(numero_nota)
        if resultado:
            imagem_binaria, data_bipe = resultado
            st.write(f"Data do Bipe: {data_bipe}")

            if imagem_binaria:
                image = Image.open(io.BytesIO(imagem_binaria))
                st.image(image, caption="Canhoto da Nota Fiscal", use_container_width=True)
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
                streamlit_js_eval(js_expressions="parent.window.location.reload()")
    else:
        st.info("🖥️ Preencha e-mail, assunto e a nota fiscal para prosseguir.")

if st.button("📸 Abrir Câmera"):
    st.camera_input("Capture a imagem")

st.markdown(footer, unsafe_allow_html=True)