import streamlit as st
from streamlit_autorefresh import st_autorefresh
import base64
import oci
from oci.generative_ai import GenerativeAiClient
from oci.generative_ai_inference import GenerativeAiInferenceClient
from oci.generative_ai_inference.models import (
    AudioContent,
    AudioUrl,
    ImageContent,
    ImageUrl,
    VideoContent,
    VideoUrl,
    TextContent,
    Message,
    ChatDetails,
    CohereChatRequest,
    GenericChatRequest,
    OnDemandServingMode
)
import uuid
import datetime
import time
import pytz
import hashlib
import json
import os
import re
from pathlib import Path

from chatdb import chatdb
from fetchmarkdown import fetchmarkdown

#
# 定義サンプル
#
# .streamlit/secrets.toml
# [oci]
# DEBUGMODE="False"
# CONFIG_PATH="~/.oci/config"
# CONFIG="DEFAULT"
# COMPARTMENT_ID="ocid1.compartment.oc1..aaaaaaahogehoge"
# CHAT_HISTORY_TABLENAME="ChatHistory2"
#

# テーマの取得
theme = "dark" if st.config.get_option("theme.base") == "dark" else "light"

# モバイル表示の問題を修正
# テーマに応じたCSSを適用
st.markdown(f"""
<style>
@media (max-width: 800px) {{
    .stChatInput {{
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        padding: 10px;
        z-index: 1000;
        transition: background-color 0.3s ease;
    }}
    .stChatInput textarea {{
        width: 100%;
        box-sizing: border-box;
    }}

    /* Lightモードのスタイル */
    .{theme}-mode .stChatInput {{
        background-color: #ffffff;
        border-top: 1px solid #ccc;
        box-shadow: 0 -2px 5px rgba(0, 0, 0, 0.1);
    }}

    /* Darkモードのスタイル */
    .dark-mode .stChatInput {{
        background-color: #1e1e1e;
        border-top: 1px solid #444;
        box-shadow: 0 -2px 5px rgba(0, 0, 0, 0.5);
    }}
    .dark-mode .stChatInput textarea {{
        color: #ffffff;
        background-color: #1e1e1e;
    }}
}}
</style>
""", unsafe_allow_html=True)

DEBUG_MODE=st.secrets['DEBUGMODE'].upper()=="TRUE"
OCI_CONFIG_PATH=st.secrets['oci']['CONFIG_PATH']
OCI_CONFIG=st.secrets['oci']['CONFIG']


# OCI認証情報
config = oci.config.from_file(OCI_CONFIG_PATH, OCI_CONFIG)
COMPARTMENT_ID = st.secrets['oci']['COMPARTMENT_ID']

#メディア状況
CANMOVIE = ["google.gemini-2.5-flash","google.gemini-2.5-pro","google.gemini-2.5-flash-lite",
            "openai.gpt-oss-120b","openai.gpt-oss-20b"]
CANAUDIO = ["google.gemini-2.5-flash","google.gemini-2.5-pro","google.gemini-2.5-flash-lite",
            "openai.gpt-oss-20b"]
CANIMAGE = ["google.gemini-2.5-flash","google.gemini-2.5-pro","google.gemini-2.5-flash-lite",
            "meta.llama-4-maverick-17b-128e-instruct-fp8","meta.llama-4-scout-17b-16e-instruct",
            "xai.grok-4-fast-non-reasoning","xai.grok-4-fast-reasoning","xai.grok-4"]

DEFAULT_MODEL = st.secrets['oci']['DEFAULT_MODEL']

# Microsoft認証
LOGINBTN_MS = "Microsoftでログイン"
AUTHSECTION_MS = "microsoft"
# Google認証
LOGINBTN_GOOGLE = "Googleでログイン"
AUTHSECTION_GOOGLE = "google"

# 認証ID識別子
def AUTHID(provider,user) :
    if provider == AUTHSECTION_MS :
        #Microsoft認証の場合
        return user.get("oid")
    elif provider == AUTHSECTION_GOOGLE :
        #Google認証の場合
        return user.get("sub")

# 許可確認する
def isContain(oid) :
    return True

# チャットDB
db = chatdb(config,COMPARTMENT_ID, st.secrets['CHAT_HISTORY_TABLENAME'])

# 動画入力機能有無
def hasMovieFunction(model:oci.generative_ai.models.Model):
    if model.display_name in CANMOVIE:
        return True
    return False

# 画像入力機能有無
def hasImageFunction(model:oci.generative_ai.models.Model):
    if model.display_name in CANIMAGE:
        return True
    return False

# 音声入力機能有無
def hasAudioFunction(model:oci.generative_ai.models.Model):
    if model.display_name in CANAUDIO:
        return True
    return False


# Generative AI クライアントの初期化
client = GenerativeAiInferenceClient(config=config)
generative_ai_client = GenerativeAiClient(config)

# 日本タイムゾーン
jst_timezone = pytz.timezone('Asia/Tokyo')

#日時変換->JST
def parseDateTime( tm ) :
    return datetime.datetime.fromisoformat(tm.replace('Z', '+00:00')).astimezone(jst_timezone)

# セッションID生成
def generate_unique_session_id() -> str:
    return hashlib.md5(str(uuid.uuid4()).encode('utf-8')).hexdigest()[:12]

# 最大出力トークン
def getMaxToken(modelid):
    match modelid:
        case "google.gemini-2.5-flash" | "google.gemini-2.5-pro" | "google.gemini-2.5-flash-lite": 
            return 65535,10000
        case "meta.llama-4-maverick-17b-128e-instruct-fp8" | "meta.llama-4-scout-17b-16e-instruct": 
            return 4000,4000
        case "xai.grok-4-fast-non-reasoning" | "xai.grok-4-fast-reasoning" : 
            return 256000,10000
        case "xai.grok-4" : 
            return 131000,10000
        case "openai.gpt-oss-120b" | "openai.gpt-oss-20b": 
            return 16000,10000
        
    return 4000,4000

# エキスポート関数群
def export_as_text(chat_history, session_id, title):
    """テキスト形式でエクスポート"""
    content = f"チャット履歴: {title}\nセッションID: {session_id}\n"
    content += f"エクスポート日時: {datetime.datetime.now(jst_timezone).strftime('%Y-%m-%d %H:%M:%S')}\n"
    content += "=" * 50 + "\n\n"
    
    for msg in chat_history:
        timestamp = parseDateTime(msg.get('timestamp', datetime.datetime.now().isoformat())) if 'timestamp' in msg else ""
        role_display = "ユーザー" if msg['role'].upper() == "USER" else "アシスタント"
        content += f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else 'N/A'}] {role_display}:\n"
        content += f"{msg['message']}\n\n"
    
    return content

def export_as_json(chat_history, session_id, title):
    """JSON形式でエクスポート"""
    export_data = {
        "session_id": session_id,
        "title": title,
        "export_datetime": datetime.datetime.now(jst_timezone).isoformat(),
        "messages": []
    }
    
    for msg in chat_history:
        timestamp = parseDateTime(msg.get('timestamp', datetime.datetime.now().isoformat())) if 'timestamp' in msg else None
        export_data["messages"].append({
            "role": msg['role'],
            "message": msg['message'],
            "timestamp": timestamp.isoformat() if timestamp else None
        })
    
    return json.dumps(export_data, ensure_ascii=False, indent=2)

def export_as_markdown(chat_history, session_id, title):
    """Markdown形式でエクスポート"""
    content = f"# {title}\n\n"
    content += f"**セッションID:** {session_id}  \n"
    content += f"**エクスポート日時:** {datetime.datetime.now(jst_timezone).strftime('%Y-%m-%d %H:%M:%S')}  \n\n"
    content += "---\n\n"
    
    for i, msg in enumerate(chat_history, 1):
        timestamp = parseDateTime(msg.get('timestamp', datetime.datetime.now().isoformat())) if 'timestamp' in msg else ""
        role_display = "🧑 ユーザー" if msg['role'].upper() == "USER" else "🤖 アシスタント"
        
        content += f"## {i}. {role_display}\n\n"
        if timestamp:
            content += f"*{timestamp.strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
        content += f"{msg['message']}\n\n"
        content += "---\n\n"
    
    return content

def import_from_json(json_content, oid):
    """JSON形式からチャット履歴をインポート"""
    try:
        import_data = json.loads(json_content)
        
        # 必須フィールドの検証
        if not all(key in import_data for key in ["session_id", "title", "messages"]):
            return False, "不正なJSONフォーマットです。必須フィールドが不足しています。"
        
        # 新しいセッションIDを生成（重複を避けるため）
        new_session_id = generate_unique_session_id()
        title = import_data.get("title", "インポートされたチャット")
        
        # メッセージの検証とインポート
        imported_count = 0
        for msg in import_data["messages"]:
            if "role" in msg and "message" in msg:
                role = msg["role"].upper()
                if role in ["USER", "CHATBOT", "ASSISTANT"]:
                    # ASSISTANTをCHATBOTに変換
                    if role == "ASSISTANT":
                        role = "CHATBOT"
                    
                    # メッセージの保存
                    db.save_chat_message(oid, new_session_id, role, msg["message"], title)
                    imported_count += 1

                    print(f"インポート: セッションID={new_session_id}, ロール={role}, カウント={imported_count}")
        
        if imported_count > 0:
            return True, f"正常にインポートされました。{imported_count}件のメッセージをインポートしました。"
        else:
            return False, "有効なメッセージが見つかりませんでした。"
            
    except json.JSONDecodeError:
        return False, "JSON形式が不正です。"
    except Exception as e:
        return False, f"インポート中にエラーが発生しました: {str(e)}"

def validate_json_format(json_content):
    """JSONファイルの形式を事前検証"""
    try:
        data = json.loads(json_content)
        
        # 基本構造の確認
        required_fields = ["session_id", "title", "messages"]
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return False, f"必須フィールドが不足しています: {', '.join(missing_fields)}"
        
        # メッセージの構造確認
        if not isinstance(data["messages"], list):
            return False, "messages は配列である必要があります。"
        
        valid_messages = 0
        for i, msg in enumerate(data["messages"]):
            if isinstance(msg, dict) and "role" in msg and "message" in msg:
                if msg["role"].upper() in ["USER", "CHATBOT", "ASSISTANT"]:
                    valid_messages += 1
        
        if valid_messages == 0:
            return False, "有効なメッセージが見つかりません。"
        
        return True, f"有効なJSONファイルです。{valid_messages}件のメッセージが含まれています。"
        
    except json.JSONDecodeError:
        return False, "JSON形式が不正です。"
    except Exception as e:
        return False, f"検証エラー: {str(e)}"


#モデル一覧
available_models = []
ret:oci.response.Response = generative_ai_client.list_models( compartment_id=COMPARTMENT_ID)
models:oci.generative_ai.models.ModelCollection = ret.data
model:oci.generative_ai.models.Model
for model in models.items:
    if model.time_on_demand_retired is None:
        if "FINE_TUNE" not in model.capabilities :
            if "CHAT" in model.capabilities :
                available_models.append(model)
                print(f"{model.display_name}")

BASE_DIR = Path(__file__).resolve().parent

#タイトル
st.title("AI Chat V.4.8")

# セッション切れ対策
st_autorefresh(interval=1000*60*10, limit=None, key="heartbeat")

if DEBUG_MODE:
    oid = "aaaaaaaaa"
else:
    
    if not st.user.is_logged_in:
        st.title("ログインしてください")
        
        if 'auth' in st.secrets is not None and 'microsoft' in st.secrets['auth'] is not None :
            if st.button(LOGINBTN_MS):
                st.login(AUTHSECTION_MS)
        if 'auth' in st.secrets is not None and 'google' in st.secrets['auth'] is not None :
            if st.button(LOGINBTN_GOOGLE):
                st.login(AUTHSECTION_GOOGLE)
            
        oid = "GUEST"
    else:
        provider = st.user.get('provider')
        oid = AUTHID(provider,st.user)

        # ログアウトボタン
        if st.button("ログアウト"):
            st.logout()

if 'nosql_table_checked' not in st.session_state:
    db.createtable()
    st.session_state.nosql_table_checked = True

if 'current_chat_session_id' not in st.session_state:
    st.session_state.current_chat_session_id = None

if 'messages_loaded_for_session' not in st.session_state:
    st.session_state.messages_loaded_for_session = None

if 'messages' not in st.session_state:
    st.session_state.messages = []

# 利用可能権限チェック
if( isContain(oid) == False ) :
    st.write("許可されていません")
else :
    #ロゴ
    st.sidebar.image(os.path.join(BASE_DIR,'logo.gif'))
    
    if DEBUG_MODE:
        None
    else:
        if oid != 'GUEST' and 'name' in st.user:
            provider = st.user.get('provider')
            st.sidebar.header(f"{provider}\nLogin: {st.user.name}")
        
    selected_model = st.sidebar.selectbox(
        "使用するモデルを選択",
        available_models,
        format_func = lambda model: f"{model.display_name}",
        index= [i for i, model in enumerate(available_models) if model.display_name == DEFAULT_MODEL][0])

    hasMovie = hasMovieFunction(selected_model)
    hasImage = hasImageFunction(selected_model)
    hasAudio = hasAudioFunction(selected_model)

    # max_tokens
    maxtoken = getMaxToken( selected_model.display_name )
    
    max_tokens_value = st.sidebar.slider(
        "トークン数上限",
        min_value=1,
        max_value=maxtoken[0],
        value=maxtoken[1],
        step=1,
        key="max_tokens_value",
        help="応答として生成されるトークンの最大値を設定します。"
    )
    # temperature
    temperature = st.sidebar.slider(
        "創造性",
        min_value=0.0,
        max_value=1.0,
        value=0.7,
        step=0.01,
        key="temperature",
        help="応答の独創性や創造性を設定します。"
    )

    # 過去履歴構築
    # ユーザーの全セッションIDを取得
    all_session_ids: list = []
    if oid != 'GUEST' :
        all_session_ids = db.get_user_session_ids(oid)
    # 新しいセッションを開始するためのオプションを追加
    NEWCHAT = "新しいチャットを開始"
    # 全セッション追加
    options = []
    options.append( ["-1", NEWCHAT, NEWCHAT] )
    for item in all_session_ids :
        session_id = item[0]
        jst_timestamp = parseDateTime(item[1])
        title = item[2]
        options.append([session_id,jst_timestamp,title])

    if oid != 'GUEST':
        
        #現セッションID探索
        sessionidx = 0
        try:
            sessionidx = [opt[0] for opt in options].index(st.session_state.current_chat_session_id)
            print(f"インデックス: {sessionidx}")
        except ValueError:
            print("見つかりませんでした")
        
        # サイドバーでセッションを選択
        selected_session_option = st.sidebar.selectbox(
            "過去チャットを選択", 
            options,
            index=sessionidx,
            format_func = lambda item: f"{item[2]}",
            key="session_select_session"
        )
        session_id = selected_session_option[0]
        message_timestamp = selected_session_option[1]
        title = selected_session_option[2]

        print(f"{selected_model.display_name}:{selected_model.vendor},[{session_id}:{message_timestamp}:{title}],{st.session_state.current_chat_session_id}")

        # 新しいセッションIDが既存のものと異なる場合のみリセット
        if session_id == "-1":
            if st.session_state.messages_loaded_for_session is None and st.session_state.current_chat_session_id is not None:
                #新規で継続中
                st.session_state.messages = db.load_chat_history_for_session(oid, st.session_state.current_chat_session_id)
            else :
                st.session_state.current_chat_session_id = generate_unique_session_id()
                st.session_state.messages = []
                st.session_state.messages_loaded_for_session = None
        else:
            print(f"履歴ロード {session_id}")
            # 選択された既存のセッションIDをロード
            if st.session_state.current_chat_session_id != session_id:
                st.session_state.current_chat_session_id = session_id
                st.session_state.messages = db.load_chat_history_for_session(oid, st.session_state.current_chat_session_id)
                st.session_state.messages_loaded_for_session = session_id

        # 選択されたセッション履歴を削除
        if session_id != "-1":
            if st.sidebar.button("削除"):
                db.delete_user_session(oid, st.session_state.current_chat_session_id)
                st.session_state.current_chat_session_id = None
                st.session_state.messages = []
                st.session_state.messages_loaded_for_session = None
                st.rerun()

        # セッションのリセットボタン
        if st.session_state.messages_loaded_for_session is None and st.session_state.current_chat_session_id is not None:
            if st.sidebar.button("リセット"):
                st.session_state.current_chat_session_id = None
                st.session_state.messages = []
                st.session_state.messages_loaded_for_session = None
                st.rerun()
    else:
        session_id = "-1"
        if st.sidebar.button("リセット"):
            st.session_state.current_chat_session_id = None
            st.session_state.messages = []
            st.session_state.messages_loaded_for_session = None
            st.rerun()

    # 拡張エキスポート機能
    st.sidebar.subheader("エクスポート")
    
    # エクスポート形式選択
    export_format = st.sidebar.selectbox(
        "形式選択",
        ["JSON", "Markdown", "テキスト"],
        key="export_format"
    )
    
    # 単一セッションのエクスポート
    if st.sidebar.button("エクスポート準備"):
        chat_history = db.load_chat_history_for_session(oid, st.session_state.current_chat_session_id)
        
        if export_format == "テキスト":
            content = export_as_text(chat_history, st.session_state.current_chat_session_id, title)
            filename = f"chat_{st.session_state.current_chat_session_id}.txt"
            mime_type = "text/plain"
        elif export_format == "JSON":
            content = export_as_json(chat_history, st.session_state.current_chat_session_id, title)
            filename = f"chat_{st.session_state.current_chat_session_id}.json"
            mime_type = "application/json"
        elif export_format == "Markdown":
            content = export_as_markdown(chat_history, st.session_state.current_chat_session_id, title)
            filename = f"chat_{st.session_state.current_chat_session_id}.md"
            mime_type = "text/markdown"
        
        st.sidebar.download_button(
            label=f"{export_format}形式でダウンロード",
            data=content,
            file_name=filename,
            mime=mime_type
        )

    # 履歴格納数調整
    MAXHISTORY = int(max_tokens_value / 100)
    if( MAXHISTORY < 100 ):
        MAXHISTORY = 100
    if( len(st.session_state.messages) > MAXHISTORY ):
        st.session_state.messages = st.session_state.messages[-MAXHISTORY:]

    # チャット履歴表示
    for message in st.session_state.messages:
        role = "assistant" if message.role == oci.generative_ai_inference.models.Message.ROLE_ASSISTANT else "user"
        
        with st.chat_message(role):
            for content in message.content:
                if content.type == oci.generative_ai_inference.models.TextContent.TYPE_TEXT:
                    if role == "assistant" :
                        st.markdown(content.text)
                    else:
                        st.text(content.text)
                if content.type == oci.generative_ai_inference.models.ImageContent.TYPE_IMAGE:
                    base64image = content.image_url.url.split('base64,')[1]
                    st.image(base64.b64decode(base64image))

    # チャット 入力待ち
    prompt = None
    promptattach = None
    if hasMovie == True or hasImage == True or hasAudio == True:
        MEDIA_FORMAT= []
        if(hasMovie ) :
            MEDIA_FORMAT = MEDIA_FORMAT + ["mp4", "mpeg", "mov", "avi", "flv", "mpg", "webm", "wmv", "3gp"]
        if(hasImage ) :
            MEDIA_FORMAT = MEDIA_FORMAT + ["png", "jpeg", "jpg", "webp"]
        if(hasAudio ) :
            MEDIA_FORMAT = MEDIA_FORMAT + ["wav", "mp3", "aiff", "aac", "ogg", "flac"]
            
        promptattach = st.chat_input("ここにメッセージを入力してください...",accept_file="multiple", file_type=MEDIA_FORMAT)
        if promptattach is not None:
            prompt = promptattach.text
    else:
        prompt = st.chat_input("ここにメッセージを入力してください...")

    if prompt is not None:

        with st.chat_message("user"):
            st.text(prompt)

            if (hasMovie == True or hasImage == True or hasAudio == True) and promptattach is not None and len(promptattach.files) > 0:
                # メディアファイル
                for file in promptattach.files:
                    print(f"{file.name},{file.type}")
                    if file.type.startswith("image/"):
                        st.image(file)
                    elif file.type.startswith("video/"):
                        st.video(file)
                    elif file.type.startswith("audio/"):
                        st.audio(file)

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):

                #チャットリクエスト作成
                chat_request = None
                if selected_model.vendor == 'cohere':

                    wrap_prompt = prompt + "\n" + "出力形式:markdown"

                    #過去履歴作成
                    #cohere用
                    chat_history = []
                    for message in st.session_state.messages:
                        talken = message.content[0].text
                        if message.role == oci.generative_ai_inference.models.Message.ROLE_USER:
                            chat_history.append({"role": "USER", "message": talken})
                        elif message.role == oci.generative_ai_inference.models.Message.ROLE_ASSISTANT:
                            chat_history.append({"role": "CHATBOT", "message": talken})

                    #cohere用
                    chat_request = CohereChatRequest(
                        api_format= oci.generative_ai_inference.models.BaseChatRequest.API_FORMAT_COHERE,
                        message=wrap_prompt,
                        chat_history=chat_history if chat_history else None,
                        max_tokens=max_tokens_value,
                        temperature=temperature,
                        is_echo=True,
                        is_stream=False
                    )
                else:
                    
                    wrap_prompt = prompt

                    #汎用
                    chat_history = []
                    for message in st.session_state.messages:
                        # Textだけにする
                        msg = Message()
                        msg.role = message.role
                        reqcnts = []
                        for cnt in message.content:
                            if cnt.type == ImageContent.TYPE_TEXT:
                                reqcnts.append(cnt)
                        msg.content = reqcnts

                        chat_history.append(msg)

                    #新規メッセージ
                    contents = []
                    txtcontent = TextContent()
                    txtcontent.type = oci.generative_ai_inference.models.TextContent.TYPE_TEXT
                    txtcontent.text = wrap_prompt
                    contents.append(txtcontent)

                    # 添付有
                    if hasImage == True and promptattach is not None and len(promptattach.files) > 0:
                        # 添付ファイル
                        for file in promptattach.files:
                            mime_type = file.type
                            if mime_type.startswith("image/"):
                                imgcontent = ImageContent()
                                imgcontent.type = ImageContent.TYPE_IMAGE
                                base64_image = base64.b64encode(file.getvalue()).decode("utf-8")
                                imgcontent.image_url = ImageUrl( url = f"data:{file.type};base64,"+base64_image )
                                contents.append(imgcontent)
                            elif mime_type.startswith("video/"):
                                videocontent = VideoContent()
                                base64_image = base64.b64encode(file.getvalue()).decode("utf-8")
                                videocontent.video_url = VideoUrl( url = f"data:{file.type};base64,"+base64_image )
                                contents.append(videocontent)
                            elif mime_type.startswith("audio/"):
                                audiocontent = AudioContent()
                                base64_image = base64.b64encode(file.getvalue()).decode("utf-8")
                                audiocontent.audio_url = AudioUrl( url = f"data:{file.type};base64,"+base64_image )
                                contents.append(audiocontent)

                    message = Message()
                    message.role = oci.generative_ai_inference.models.Message.ROLE_USER
                    message.content = contents
                    chat_history.append(message)

                    # 外部 URL参照対応
                    syscontents = []
                    webimgcontents = []
                    urls = re.findall(r"https?://\S+", prompt)
                    for url in urls:
                        fetcher = fetchmarkdown()
                        markdowncontent, webimages = fetcher.fetchurl(url)
                        if markdowncontent is not None :
                            nowdatestr = datetime.datetime.now(pytz.timezone('Asia/Tokyo')).strftime("%Y-%m-%d %H:%M:%S")
                            refcontent = TextContent()
                            refcontent.type = oci.generative_ai_inference.models.TextContent.TYPE_TEXT
                            refcontent.text = f""" Today is {nowdatestr}.
{url}

{markdowncontent}"""
                            syscontents.append(refcontent)
                            print(f"url:{url}")
                            
                        if hasImage == True and webimages is not None :
                            for webimage in webimages:
                                webimgcontent = ImageContent()
                                webimgcontent.type = ImageContent.TYPE_IMAGE
                                webimgcontent.image_url = webimage
                                webimgcontents.append(webimgcontent)

                    systxtcontent = TextContent()
                    systxtcontent.type = oci.generative_ai_inference.models.TextContent.TYPE_TEXT
                    systxtcontent.text = "Markdown形式で出力して下さい。"
                    syscontents.append(systxtcontent)

                    sysmessage = Message()
                    sysmessage.role = oci.generative_ai_inference.models.Message.ROLE_SYSTEM
                    sysmessage.content = syscontents
                    chat_history.append(sysmessage)

                    if hasImage == True and len(webimgcontents) > 0 :
                        webimgmessage = Message()
                        webimgmessage.role = oci.generative_ai_inference.models.Message.ROLE_USER
                        webimgmessage.content = webimgcontents
                        chat_history.append(webimgmessage)

                    chat_request = GenericChatRequest(
                        api_format=oci.generative_ai_inference.models.BaseChatRequest.API_FORMAT_GENERIC,
                        messages=chat_history,
                        max_tokens=max_tokens_value,
                        temperature=temperature
                    )

                #新規メッセージ チャット履歴追加(cohereと汎用の対応の為、冗長だが、作成しなおす)
                contents = []
                txtcontent = TextContent()
                txtcontent.type = oci.generative_ai_inference.models.TextContent.TYPE_TEXT
                txtcontent.text = prompt
                contents.append(txtcontent)

                # 画像有
                if (hasMovie == True or hasImage == True or hasAudio == True) and promptattach is not None and len(promptattach.files) > 0:
                    # 画像ファイル
                    for file in promptattach.files:
                        mime_type = file.type
                        if mime_type.startswith("image/"):
                            imgcontent = ImageContent()
                            imgcontent.type = ImageContent.TYPE_IMAGE
                            base64_image = base64.b64encode(file.getvalue()).decode("utf-8")
                            imgcontent.image_url = ImageUrl( url = f"data:{file.type};base64,"+base64_image )
                            contents.append(imgcontent)
                        elif mime_type.startswith("video/"):
                            videocontent = VideoContent()
                            videocontent.type = videocontent.TYPE_IMAGE
                            base64_image = base64.b64encode(file.getvalue()).decode("utf-8")
                            videocontent.video_url = VideoUrl( url = f"data:{file.type};base64,"+base64_image )
                            contents.append(videocontent)
                        elif mime_type.startswith("audio/"):
                            audiocontent = AudioContent()
                            audiocontent.type = AudioContent.TYPE_IMAGE
                            base64_image = base64.b64encode(file.getvalue()).decode("utf-8")
                            audiocontent.audio_url = AudioUrl( url = f"data:{file.type};base64,"+base64_image )
                            contents.append(audiocontent)

                newmessage = Message()
                newmessage.role = oci.generative_ai_inference.models.Message.ROLE_USER
                newmessage.content = contents

                st.session_state.messages.append(newmessage)
                
                if oid != 'GUEST':
                    # DB チャット履歴追加(文字列プロンプトだけ対象)
                    jstnow = datetime.datetime.now(jst_timezone).strftime('%Y-%m-%d %H時')
                    title = f"{jstnow} {prompt[:20]}"
                    db.save_chat_message(oid, st.session_state.current_chat_session_id, "USER", prompt, title)

                # チャット送信処理
                serving_mode = OnDemandServingMode(model_id=selected_model.id)
                chat_details = ChatDetails(
                    compartment_id=COMPARTMENT_ID,
                    chat_request=chat_request,
                    serving_mode=serving_mode
                )
                response:oci.response.Response = client.chat(chat_details)
                result:oci.generative_ai_inference.models.ChatResult = response.data

                if selected_model.vendor == 'cohere':
                    #cohere用
                    bot_reply = result.chat_response.text
                    
                    # 応答 チャット履歴追加
                    contents = []
                    txtcontent = TextContent()
                    txtcontent.type = oci.generative_ai_inference.models.TextContent.TYPE_TEXT
                    txtcontent.text = bot_reply
                    contents.append(txtcontent)

                    message = Message()
                    message.role = oci.generative_ai_inference.models.Message.ROLE_ASSISTANT
                    message.content = contents

                    st.session_state.messages.append(message)

                    if oid != 'GUEST':
                        # DB チャット履歴追加(文字列プロンプトだけ対象)
                        db.save_chat_message(oid, st.session_state.current_chat_session_id, "CHATBOT", bot_reply, title)
                    # 出力
                    st.markdown(bot_reply)
                    
                else:
                    #汎用
                    generic_response:oci.generative_ai_inference.models.generic_chat_response.GenericChatResponse = result.chat_response
                    chatchoice:oci.generative_ai_inference.models.ChatChoice = generic_response.choices[0]
                    msg:oci.generative_ai_inference.models.Message = chatchoice.message

                    contents = []

                    for cnt in msg.content:
                        if isinstance(cnt,oci.generative_ai_inference.models.TextContent):
                            txt:oci.generative_ai_inference.models.TextContent = cnt
                            bot_reply = txt.text
                            
                            # 応答 チャット履歴追加
                            contents.append(txt)

                            if oid != 'GUEST':
                                # DB チャット履歴追加(今のとこ、テキストのみ対応)
                                db.save_chat_message(oid, st.session_state.current_chat_session_id, "CHATBOT", bot_reply, title)
                            # 出力
                            st.markdown(bot_reply)
                            
                        elif isinstance(cnt,oci.generative_ai_inference.models.ImageContent):
                            img:oci.generative_ai_inference.models.ImageContent = cnt
                            bot_reply:ImageUrl = img.image_url

                            # 応答 チャット履歴追加
                            contents.append(img)
                            
                            base64image = bot_reply.url.split('base64,')[1]
                            st.image(base64.b64decode(base64image))
                            
                        elif isinstance(cnt,oci.generative_ai_inference.models.AudioContent):
                            audio:oci.generative_ai_inference.models.AudioContent = cnt
                            bot_reply = audio.audio_url
                        elif isinstance(cnt,oci.generative_ai_inference.models.VideoContent):
                            video:oci.generative_ai_inference.models.VideoContent = cnt
                            bot_reply = video.video_url

                    message = Message()
                    message.role = oci.generative_ai_inference.models.Message.ROLE_ASSISTANT
                    message.content = contents

                    st.session_state.messages.append(message)
