# コンフィグ
* .streamlit
  * secrets.toml
```
# .streamlit/secrets.toml
[auth]
cookie_secret = "randomstring"
redirect_uri = "https://hogehoge.genai.site/oauth2callback"
[auth.google]
client_id = "9999999999-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.apps.googleusercontent.com"
client_secret = "ZZZZZZZZ-xxxxxxxxxxxxxxxxx_yyyyyyyyyyyy"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
[auth.microsoft]
client_id = "xxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
client_secret = "randomstring"
server_metadata_url = "https://login.microsoftonline.com/tenantid/v2.0/.well-known/openid-configuration"
scopes = ["openid", "profile", "email"]
[oci]
DEBUGMODE="False"
CONFIG_PATH="~/.oci/config"
CONFIG="DEFAULT"
COMPARTMENT_ID="ocid1.compartment.oc1..aaaaaaahogehoge"
CHAT_HISTORY_TABLENAME="ChatHistory2"

```

# 起動
```
streamlit run chat1sso8.py --server.port 8501 --server.enableCORS false
```

