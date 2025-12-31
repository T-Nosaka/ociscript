import streamlit as st
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

from chatdb import chatdb

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

# OCI認証情報
config = oci.config.from_file(st.secrets["oci"]["config_path"], st.secrets["oci"]["config_name"])
COMPARTMENT_ID = st.secrets["oci"]["compartment"]

#メディア状況
CANMOVIE = ["google.gemini-2.5-flash","google.gemini-2.5-pro","google.gemini-2.5-flash-lite"]
CANAUDIO = ["google.gemini-2.5-flash","google.gemini-2.5-pro","google.gemini-2.5-flash-lite"]
CANIMAGE = ["google.gemini-2.5-flash","google.gemini-2.5-pro","google.gemini-2.5-flash-lite",
            "meta.llama-4-maverick-17b-128e-instruct-fp8","meta.llama-4-scout-17b-16e-instruct",
            "xai.grok-4-fast-non-reasoning","xai.grok-4-fast-reasoning","xai.grok-4"]

DEBUG_MODE=False

# Google認証
LOGINBTN = "Googleでログイン"
AUTHSECTION = "google"
# 認証ID識別子
def AUTHID(user) :
    return user.get("sub")
# 許可確認する
def isContain(oid) :
    return True


# チャットDB
db = chatdb(config,COMPARTMENT_ID)

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

# 最大トークン数
def getMaxToken( model:oci.generative_ai.models.Model):
    if model.display_name in ["google.gemini-2.5-flash","google.gemini-2.5-pro","google.gemini-2.5-flash-lite"]:
        return 65536
    if model.display_name in ["xai.grok-3","xai.grok-3-fast","xai.grok-3-mini","xai.grok-3-mini-fast"]:
        return 16000
    if model.display_name in ["xai.grok-4","xai.grok-code-fast-1"]:
        return 131000
    if model.display_name in ["xai.grok-4-fast-non-reasoning","xai.grok-4-fast-reasoning"]:
        return 256000
    return 4000


# Generative AI クライアントの初期化
DEFAULT_MODEL = "google.gemini-2.5-flash"
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
#                print(f"{model.display_name}")

#タイトル
st.title("OCI AI Chat")

oid=""
if DEBUG_MODE:
    oid = "aaaaaaaaa"
else:
    if not st.user.is_logged_in:
        st.title("ログインしてください")
        if st.button(LOGINBTN):
            st.login(AUTHSECTION)
            st.stop()
    else:
        oid = AUTHID(st.user)

if 'nosql_table_checked' not in st.session_state:
    db.createtable()
    st.session_state.nosql_table_checked = True

if 'current_chat_session_id' not in st.session_state:
    st.session_state.current_chat_session_id = None

if 'messages_loaded_for_session' not in st.session_state:
    st.session_state.messages_loaded_for_session = None

# ログアウトボタン
if st.button("ログアウト"):
    st.logout()

# 利用可能権限チェック
if( isContain(oid) == False ) :
    st.write("許可されていません")
else :
    if DEBUG_MODE:
        None
    else:
        st.sidebar.header(f"Login: {st.user.name}")
    selected_model = st.sidebar.selectbox(
        "使用するモデルを選択",
        available_models,
        format_func = lambda model: f"{model.display_name}",
        index= [i for i, model in enumerate(available_models) if model.display_name == DEFAULT_MODEL][0])

    hasMovie = hasMovieFunction(selected_model)
    hasImage = hasImageFunction(selected_model)
    hasAudio = hasAudioFunction(selected_model)

    # max_tokens
    max_tokens_value = st.sidebar.slider(
        "トークン数上限",
        min_value=1,
        max_value=getMaxToken(selected_model),
        value=int(getMaxToken(selected_model)*0.5),
        step=1,
        key="max_tokens_value",
        help="応答として生成されるトークンの最大値を設定します。"
    )
    # temperature
    temperature = st.sidebar.slider(
        "創造性",
        min_value=0.0,
        max_value=2.0,
        value=0.7,
        step=0.01,
        key="temperature",
        help="応答の独創性や創造性を設定します。"
    )

    # 過去履歴構築
    # ユーザーの全セッションIDを取得
    all_session_ids: list = db.get_user_session_ids(oid)
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

    # サイドバーでセッションを選択
    selected_session_option = st.sidebar.selectbox(
        "過去チャットを選択", 
        options,
        index=0,
        format_func = lambda item: f"{item[2]}",
        key="session_select_box"
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

    # セッションのリセットボタン
    if st.session_state.messages_loaded_for_session is None and st.session_state.current_chat_session_id is not None:
        if st.sidebar.button("リセット"):
            st.session_state.current_chat_session_id = None
            st.session_state.messages = []
            st.session_state.messages_loaded_for_session = None
            st.rerun()

    # 選択されたセッション履歴を削除
    if session_id != "-1":
        if st.sidebar.button("削除"):
            db.delete_user_session(oid, st.session_state.current_chat_session_id)
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
    else :
        st.sidebar.subheader("インポート")

        # ファイルアップローダー
        uploaded_file = st.sidebar.file_uploader(
            "JSONファイルを選択",
            type=['json'],
            help="エクスポートしたJSONファイルをアップロードしてください"
        )

        if uploaded_file is not None:
            # ファイル内容を読み込み
            json_content = uploaded_file.read().decode('utf-8')
            
            # プレビュー表示
            with st.sidebar.expander("ファイル内容プレビュー"):
                try:
                    preview_data = json.loads(json_content)
                    st.write(f"**タイトル:** {preview_data.get('title', 'N/A')}")
                    st.write(f"**セッションID:** {preview_data.get('session_id', 'N/A')}")
                    st.write(f"**メッセージ数:** {len(preview_data.get('messages', []))}")
                    
                    # 形式検証
                    is_valid, validation_message = validate_json_format(json_content)
                    if is_valid:
                        st.success(validation_message)
                    else:
                        st.error(validation_message)
                        
                except Exception as e:
                    st.error(f"プレビューエラー: {str(e)}")
            
            # インポートボタン
            if st.sidebar.button("インポート実行", type="primary"):
                with st.spinner("インポート中..."):
                    success, message = import_from_json(json_content, oid)
                    
                    if success:
                        st.sidebar.success(message)
                        # セッション状態をリセットして新しいチャット一覧を表示
                        time.sleep(1)  # ユーザーが成功メッセージを見る時間を与える
                        st.rerun()
                    else:
                        st.sidebar.error(message)


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
            MEDIA_FORMAT = MEDIA_FORMAT + ["png", "jpeg", "jpg"]
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
                        None
                    elif file.type.startswith("audio/"):
                        None

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):

                wrap_prompt = prompt 

                chat_request = None
                if selected_model.vendor == 'cohere':

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
                        message=wrap_prompt + "\n" + "出力形式:markdown",
                        chat_history=chat_history if chat_history else None,
                        max_tokens=max_tokens_value,
                        temperature=temperature,
                        is_echo=True,
                        is_stream=False
                    )
                else:

                    #汎用
                    chat_history = []
                    for message in st.session_state.messages:
                        # 画像は、1個までのようだ
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

                    # 画像有
                    if hasImage == True and promptattach is not None and len(promptattach.files) > 0:
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

                    chat_final = []
                    for msg in chat_history:
                        chat_final.append(msg)

                    # システムメッセージ 追加
                    sysmessage = Message()
                    sysmessage.role = oci.generative_ai_inference.models.Message.ROLE_SYSTEM
                    syscontents = []
                    txtcontent = TextContent()
                    txtcontent.type = oci.generative_ai_inference.models.TextContent.TYPE_TEXT
                    txtcontent.text = "出力形式:markdown"
                    syscontents.append(txtcontent)

                    sysmessage.content = syscontents
                    chat_final.append(sysmessage)

                    chat_request = GenericChatRequest(
                        api_format=oci.generative_ai_inference.models.BaseChatRequest.API_FORMAT_GENERIC,
                        messages=chat_final,
                        max_tokens=max_tokens_value,
                        temperature=temperature
                    )

                #新規メッセージ チャット履歴追加
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
                # DB チャット履歴追加
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

                bot_reply = ""
                if selected_model.vendor == 'cohere':
                    #cohere用
                    bot_reply = result.chat_response.text

                    if bot_reply:
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

                        # DB チャット履歴追加
                        db.save_chat_message(oid, st.session_state.current_chat_session_id, "CHATBOT", bot_reply, title)
                        # 出力
                        st.markdown(bot_reply)

                else:
                    #汎用
                    generic_response:oci.generative_ai_inference.models.generic_chat_response.GenericChatResponse = result.chat_response

                    for chatchoice in generic_response.choices:

                        msg:oci.generative_ai_inference.models.Message = chatchoice.message

                        for cnt in msg.content:
                            if isinstance(cnt,oci.generative_ai_inference.models.TextContent):
                                txt:oci.generative_ai_inference.models.TextContent = cnt
                                bot_reply = txt.text
                            elif isinstance(cnt,oci.generative_ai_inference.models.ImageContent):
                                img:oci.generative_ai_inference.models.ImageContent = cnt
                                bot_reply = img.image_url
                            elif isinstance(cnt,oci.generative_ai_inference.models.AudioContent):
                                audio:oci.generative_ai_inference.models.AudioContent = cnt
                                bot_reply = audio.audio_url
                            elif isinstance(cnt,oci.generative_ai_inference.models.VideoContent):
                                video:oci.generative_ai_inference.models.VideoContent = cnt
                                bot_reply = video.video_url

                        if bot_reply:
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

                            # DB チャット履歴追加
                            db.save_chat_message(oid, st.session_state.current_chat_session_id, "CHATBOT", bot_reply, title)
                            # 出力
                            st.markdown(bot_reply)
