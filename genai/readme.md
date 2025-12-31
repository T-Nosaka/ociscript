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
[oci]
config_path = "~/.oci/config"
config_name = "DEFAULT"
compartment = "ocid1.compartment.oc1..hogehogehogehogexxxxxxxxxxxxxxx"
```

# 起動
```
streamlit run chat1sso8.py --server.port 8501 --server.enableCORS false
```
