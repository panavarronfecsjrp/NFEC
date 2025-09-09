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
import mysql.connector

# Adicionando suporte à leitura de código de barras
try:
    from pyzbar.pyzbar import decode as pyzbar_decode
except ImportError:
    pyzbar_decode = None

# Carregar variáveis do arquivo .env
load_dotenv()

# Configuração da página
st.set_page_config(page_title='Dinatec - Canhoto Nota Fiscal', 
                   layout='wide', 
                   page_icon=':truck:',
                   initial_sidebar_state="collapsed",
                   )

# Configuração para conectar ao MySQL

def conectar_banco():
    try:
        # Tentar conectar ao banco de dados MySQL
        conn = mysql.connector.connect(
            host="186.224.105.111",
            user="panavarr_panavarro",
            password="D1n4t3c2025**",
            database="panavarr_NotasFiscaisCanhoto",
            charset='utf8mb4'
        )
        return conn  # Retorne o objeto de conexão válido
    except mysql.connector.Error as e:
        st.error(f"Erro conectar MySQL: {e}")
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
            st.image(logo, width=220)  # Exibe a logomarca com largura ajustável
    with col2:
        quantidade_canhotos = contar_canhotos()
        st.title("📌 Sistema Captura/Consulta Canhoto - Grupo Dinatec")

def verificar_nota_existente(nota_fiscal, empresa_selecionada=None):
    # Adapta a verificação para a tabela correta se empresa_selecionada for fornecida
    tabela = "notafiscaiscanhotosjrp"
    if empresa_selecionada == "Sao Jose do Rio Preto":
        tabela = "notafiscaiscanhotosjrp"
    # Dinatec Matriz ou default: notafiscaiscanhoto

    conn = conectar_banco()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"""
                SELECT COUNT(*) FROM {tabela}
                WHERE NumeroNota = %s
                """,
                (nota_fiscal,)
            )
            existe = cursor.fetchone()[0] > 0
            return existe
        except Exception as e:
            st.error(f"Erro consultar nota fiscal, favor informar novamente o numero da nota fiscal, e em caso de duvida procure o administrador do sistema. {e}")
        finally:
            cursor.close()
            conn.close()
    return False

def salvar_imagem_no_banco(imagem, nota_fiscal, empresa_selecionada=None):
    # Decide a tabela de acordo com a empresa selecionada
    tabela = "notafiscaiscanhotosjrp"
    if empresa_selecionada == "Sao Jose do Rio Preto":
        tabela = "notafiscaiscanhotosjrp"
    # Dinatec Matriz ou default: notafiscaiscanhoto


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
                f"""
                INSERT INTO {tabela} (NumeroNota, DataBipe, CaminhoImagem, Imagem)
                VALUES (%s, %s, %s, %s)
                """,
                (nota_fiscal, data_atual, "caminho_fake.jpg", imagem_binaria)
            )
            conn.commit()
            st.success("Imagem salva com sucesso MySQL.")
        except Exception as e:
            st.error(f"Erro salvar imagem MySQL: {e}")
        finally:
            cursor.close()
            conn.close()

# Função que conta canhotos da Unidade Bra  Sao Jose do Rio Preto
def contar_canhotos():
    conn = conectar_banco()
    if conn:
        try:
            with conn.cursor() as cursor:
                
                cursor.execute("SELECT COUNT(*) FROM notafiscaiscanhotosjrp")
                quantidade = cursor.fetchone()[0]
                return quantidade
        except Exception as e:
            st.error(f"Erro contar registros MySQL: {e}")
            return 0
        finally:
            conn.close() 
    else:
        st.error("Não foi possível conectar ao banco MySQL, entrar em contato com o administrador.")
        return 0

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
            st.error(f"Erro contar canhotos, em caso de duvida procurar o administrador do sistema.{e}")
            return 0
        finally:
            conn.close()  # Garante que a conexão será fechada
    else:
        st.error("Não foi possível conectar ao banco, favor procurar o administrador do sistema.")
        return 0

# ===== NOVA FUNÇÃO: obter todas as contagens em uma única consulta cacheada =====

@st.cache_data(ttl=60, show_spinner=False)
def obter_quantidades_canhotos():
    """Retorna um dicionário com as quantidades de canhotos por unidade.

    O resultado fica em cache por 60 segundos, evitando consultas repetidas em cada
    rerun do Streamlit e acelerando o carregamento da página.
    """
    conn = conectar_banco()
    if conn is None:
        return {}

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM notafiscaiscanhotosjrp)    AS SaoJoseDoRioPreto
            """
        )
        valores = cursor.fetchone()
        if not valores:
            return {}

        chaves = [
            "São José do Rio Preto",
        ]
        return dict(zip(chaves, valores))
    except Exception as e:
        st.error(f"Erro obter contagens: {e}")
        return {}
    finally:
        cursor.close()
        conn.close()

# Função para limpar a tela e atualizar o estado
def limpar_tela():
    st.session_state.captura_concluida = True
    st.session_state.recarregar = True

def consultar_nota_sjrp(nota_fiscal_sjrp):
    conn = conectar_banco()
    if conn:
        cursor = conn.cursor(buffered=True)
        try:
            cursor.execute(
                """
                SELECT Imagem, DataBipe
                FROM notafiscaiscanhotosjrp
                WHERE NumeroNota = %s
                """,
                (nota_fiscal_sjrp,)
            )
            resultado = cursor.fetchone()
            if resultado:
                imagem_binaria, data_bipe = resultado
                return imagem_binaria, data_bipe
            return None, None
        except Exception as e:
            st.error(f"Erro consultar MySQL: {e}")
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
        st.error(f"Erro enviar e-mail: {e}")
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao enviar o e-mail: {e}")

# Função para ler código de barras de uma imagem usando pyzbar
def ler_codigo_barras(imagem):
    # Se a biblioteca pyzbar não estiver instalada, retorna None e mostra mensagem em português
    if pyzbar_decode is None:
        st.info("Leitura automática código de barras não disponível neste ambiente. Digite manualmente o número da nota fiscal.")
        return None
    # pyzbar espera uma imagem PIL no modo RGB ou L
    if imagem.mode not in ("RGB", "L"):
        imagem = imagem.convert("RGB")
    decoded_objects = pyzbar_decode(imagem)
    if decoded_objects:
        # Retorna o primeiro código de barras encontrado
        return decoded_objects[0].data.decode("utf-8")
    return None

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
    Desenvolvido.: 🛡️ <a href="https://www.dinatec.com.br" target="_blank">Dinatec</a> | 📩 <a href="mailto:thiago.panuto@dinatec.com.br">Suporte</a>
</div>
<a href="https://wa.me/5516993253920" target="_blank" class="whatsapp-button">
    <i class="fab fa-whatsapp whatsapp-icon"></i>
</a>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
"""

# Função para exibir o rodapé (permite reutilizar em diferentes fluxos)
def exibir_footer():
    st.markdown(footer, unsafe_allow_html=True)

# Exibir logomarca no topo da página
exibir_logo("logo.jpg")

# Menu de navegação
pagina = st.sidebar.selectbox("Selecione a página", ["📸 Captura de Imagem", "🔍 Consulta de Canhoto", "📩 Envio de E-mail"])

# Adicionar conteúdo à barra lateral usando apenas UMA consulta ao banco

quantidades = obter_quantidades_canhotos()

def card_sidebar(unidade_label: str, chave_dict: str):
    """Exibe um card com a contagem de canhotos para a unidade informada."""
    st.sidebar.divider()
    with st.sidebar:
        with st.container():
            quantidade = quantidades.get(chave_dict, 0)
        st.markdown(
            f"<h3 style='text-align: center; font-weight:bold'>"
            f"🏭 {unidade_label}<br>Qtd. Canhotos:<br>📝 {quantidade}</h3>",
            unsafe_allow_html=True,
        )

# Exibe os cards na ordem desejada
card_sidebar("São José do Rio Preto", "São José do Rio Preto")
# Divisor final para estética
st.sidebar.divider()

if pagina == "📸 Captura de Imagem":
    st.header("📸 Captura Imagem - Canhoto Nota Fiscal")
    col1, col2 = st.columns(2)
    with col1:
        # Adiciona seleção de empresa
        empresas = ["São José do Rio Preto"]
        empresa_selecionada = st.selectbox("Selecione a empresa:", empresas, disabled=True)
    with col2:
        # Escolha do método de captura
        metodo_captura = st.selectbox(
        "Selecione o método de captura:",
        ["Digitar número da Nota Fiscal", "Carregar imagem do canhoto"]
    )
    # Caso o usuário opte por carregar diretamente a imagem
    if metodo_captura == "Carregar imagem do canhoto":
        st.info("📱 Para alta resolução, capture a imagem externamente e faça o upload abaixo.")
        image_tratada = st.file_uploader(
            "Envie a imagem do canhoto em alta resolução", type=["jpg", "jpeg", "png"], key="upload_sem_nota"
        )

        if image_tratada is not None:
            img_tratada = Image.open(image_tratada)

            # Opção de rotação (semelhante ao fluxo original)
            rotacao_upload = st.radio(
                "Selecione a orientação da imagem:",
                ["Original", "Rotação 90°", "Rotação 180°", "Rotação 270°"],
                horizontal=True,
                key="rotacao_upload_sem_nota"
            )

            img_exibir = img_tratada
            if rotacao_upload == "Rotação 90°":
                img_exibir = img_tratada.transpose(Image.Transpose.ROTATE_90)
            elif rotacao_upload == "Rotação 180°":
                img_exibir = img_tratada.transpose(Image.Transpose.ROTATE_180)
            elif rotacao_upload == "Rotação 270°":
                img_exibir = img_tratada.transpose(Image.Transpose.ROTATE_270)

            # Exibe a imagem (possivelmente rotacionada)
            st.image(img_exibir, caption="Imagem Carregada", use_container_width=True)
            # Tenta ler o código de barras na imagem exibida
            nota_detectada = ler_codigo_barras(img_exibir)
            if nota_detectada and nota_detectada.isdigit():
                st.success(f"✅ Código de barras lido: {nota_detectada}. Salvando automaticamente...")
                with st.spinner("Salvando imagem automaticamente..."):
                    salvar_imagem_no_banco(img_exibir, nota_detectada, empresa_selecionada)
                    limpar_tela()
                    streamlit_js_eval(js_expressions="parent.window.location.reload()")
                # Interrompe a execução após salvar automaticamente
                exibir_footer()
                st.stop()
            elif nota_detectada:
                st.warning(f"✅ Código de barras lido: {nota_detectada}, mas não é apenas dígitos. Digite manualmente o número da nota fiscal.")
                nota_detectada = ""
            else:
                st.info("⚠️ Não foi possível detectar código de barras automaticamente. Digite manualmente o número da nota fiscal.")
                nota_detectada = ""
            # Campo para confirmação ou digitação manual do número da nota fiscal
            nota_fiscal_carregada = st.text_input(
                "☑️ Número da Nota Fiscal",
                value=nota_detectada,
                max_chars=50,
                placeholder="Digite o número da nota fiscal"
            )

            # Botão para salvar a imagem
            if st.button("☑️ Salvar Imagem"):
                if nota_fiscal_carregada and nota_fiscal_carregada.isdigit():
                    with st.spinner("Salvando imagem..."):
                        salvar_imagem_no_banco(img_exibir, nota_fiscal_carregada, empresa_selecionada)
                        limpar_tela()
                        streamlit_js_eval(js_expressions="parent.window.location.reload()")
                else:
                    st.error("⚠️ Número da nota fiscal inválido. Digite apenas dígitos.")

        # Interrompe a execução para evitar que o restante do fluxo (digitar número) seja exibido
        exibir_footer()
        st.stop()

    # Fluxo original (digitar número da nota fiscal) permanece abaixo
    # Entrada de dados para o número da nota fiscal com validação
    nota_fiscal = st.text_input("☑️ Número da Nota Fiscal", max_chars=50, placeholder="Digite o número da nota fiscal aqui")

    # Verificar se a nota fiscal existe e exibir o resultado
    if nota_fiscal and nota_fiscal.isdigit():
        nota_existente = verificar_nota_existente(nota_fiscal, empresa_selecionada)
        
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
                
                # Botão para salvar imagem do upload
                if st.button("☑️ Salvar Imagem do Upload"):
                    with st.spinner("Salvando imagem..."):
                        salvar_imagem_no_banco(img_tratada, nota_fiscal, empresa_selecionada)
                        limpar_tela()
                        streamlit_js_eval(js_expressions="parent.window.location.reload()")

            # --- NOVA OPÇÃO: Upload com leitura de código de barras ---
            st.markdown("---")
            st.subheader("📷 Upload de Imagem com Leitura de Código de Barras")
            image_barcode = st.file_uploader("Envie a imagem do canhoto para ler o código de barras", type=["jpg", "jpeg", "png"], key="barcode_upload")

            if image_barcode is not None:
                img_barcode = Image.open(image_barcode)

                # Exibir imagem carregada
                st.image(img_barcode, caption="Imagem para Leitura de Código de Barras", use_container_width=True)

                # Tentar ler o código de barras
                codigo_lido = ler_codigo_barras(img_barcode)
                if codigo_lido:
                    st.success(f"✅ Código de barras lido: {codigo_lido}")
                    # Permitir ao usuário usar o código lido como número da nota fiscal
                    if st.button("Usar código de barras como número da nota fiscal"):
                        st.session_state["nota_fiscal"] = codigo_lido
                        st.experimental_rerun()
                else:
                    st.info("⚠️ Não foi possível detectar código de barras automaticamente. Digite manualmente o número da nota fiscal.")

                # Opção de rotação para tentar melhorar a leitura
                st.markdown("Se não leu corretamente, tente girar a imagem:")
                rotacao_barcode = st.radio(
                    "Rotacionar imagem para leitura do código de barras:",
                    ["Original", "Rotação 90°", "Rotação 180°", "Rotação 270°"],
                    horizontal=True,
                    key="barcode_rotation"
                )
                img_barcode_rot = img_barcode
                if rotacao_barcode == "Rotação 90°":
                    img_barcode_rot = img_barcode.transpose(Image.Transpose.ROTATE_90)
                elif rotacao_barcode == "Rotação 180°":
                    img_barcode_rot = img_barcode.transpose(Image.Transpose.ROTATE_180)
                elif rotacao_barcode == "Rotação 270°":
                    img_barcode_rot = img_barcode.transpose(Image.Transpose.ROTATE_270)

                if rotacao_barcode != "Original":
                    st.image(img_barcode_rot, caption="Imagem Rotacionada para Leitura", use_container_width=True)
                    codigo_lido_rot = ler_codigo_barras(img_barcode_rot)
                    if codigo_lido_rot:
                        st.success(f"✅ Código de barras lido após rotação: {codigo_lido_rot}")
                        if st.button("Usar código de barras lido após rotação como número da nota fiscal"):
                            st.session_state["nota_fiscal"] = codigo_lido_rot
                            st.experimental_rerun()
                    else:
                        st.info("⚠️ Ainda não foi possível detectar código de barras automaticamente. Digite manualmente o número da nota fiscal.")

    elif nota_fiscal:
        st.error("⚠️ Por favor, insira apenas números para o número da nota fiscal.")

elif pagina == "🔍 Consulta de Canhoto":
    st.header("🔍 Consulta de Canhoto")
    # Substitui os radios por selectbox para seleção de consulta
    opcoes_consulta = ["São José do Rio Preto"]
    selecao_consulta = st.selectbox("Selecione a(s) origem(ns) para consulta:", opcoes_consulta)
    # Entrada de dados para consulta
    NumeroNota = st.number_input("✅ Número Nota Fiscal para consulta", min_value=0, step=1, format="%d", placeholder="Digite número nota fiscal aqui")
    if NumeroNota:
        if selecao_consulta == "São José do Rio Preto":
                imagem_binaria, data_bipe = consultar_nota_sjrp(NumeroNota)
                st.write(f"Data Bipe: {data_bipe}")
                if imagem_binaria:
                    image = Image.open(io.BytesIO(imagem_binaria))
                    st.image(image, caption="Canhoto Consultado - São José do Rio Preto", use_container_width=True)
                else:
                    st.error("⚠️ Imagem não encontrada para essa nota fiscal em São José do Rio Preto.")

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
        resultado = consultar_nota_sjrp(numero_nota)
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

# Exibe o rodapé no final da execução (para os demais fluxos)
exibir_footer()