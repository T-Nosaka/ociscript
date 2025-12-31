import oci

import datetime
import time
import pytz

from oci.generative_ai_inference.models import (
    TextContent,
    Message
)

class chatdb:

    tablename = "ChatHistory2"
    childtablename = "messages"
    nosqlcl = None
    compartmentid = None
    retry_count = 5
    sleep_time = 5

    def __init__(self, config, compid ):
        self.nosqlcl : oci.nosql.nosql_client.NosqlClient = oci.nosql.nosql_client.NosqlClient(config)
        self.compartmentid = compid

    # 索引作成
    def _create_table_index(self ):
        print(f"NoSQL インデックス 'message' を確認・作成中...")
        try:
            index_name = "message"
            create_index_details = oci.nosql.models.CreateIndexDetails(
                name=index_name,
                compartment_id=self.compartmentid,
                keys=[
                    oci.nosql.models.IndexKey(column_name="user_id"),
                    oci.nosql.models.IndexKey(column_name="message_timestamp")
                ],
                is_if_not_exists = True
            )
            response: oci.response.Response = self.nosqlcl.create_index(table_name_or_id=self.tablename ,create_index_details=create_index_details)

            oci.wait_until(
                self.nosqlcl,
                self.nosqlcl.get_index(table_name_or_id=self.tablename, index_name=index_name, compartment_id=self.compartmentid),
                'lifecycle_state',
                'ACTIVE'
            )
            print(f"インデックス '{index_name}' が ACTIVE 状態になりました。")

        except oci.exceptions.ServiceError as e:
            if e.code == 'IndexAlreadyExists':
                print(f"インデックス '{index_name}' は既に存在します。")
            else:
                print(f"インデックス作成中にエラーが発生しました: {e}")
                print(f"詳細エラーメッセージ: {e.message}")
        except Exception as e:
            print(f"予期せぬエラー: {e}")

    # 親テーブル作成
    def _create_table(self ):
        print(f"NoSQL テーブル '{self.tablename}' を確認・作成中...")
        try:

            try:
                print(f"NoSQL テーブル '{self.tablename}' を確認中...")

                # テーブルが既に存在するか確認
                response: oci.response.Response = self.nosqlcl.get_table(table_name_or_id=self.tablename, compartment_id=self.compartmentid)
                tbl : oci.nosql.models.Table = response.data
                if tbl.lifecycle_state == oci.nosql.models.Table.LIFECYCLE_STATE_ACTIVE:
                    print(f"テーブル '{self.tablename}' は既に存在します。")
                    return
            except oci.exceptions.ServiceError as e:
                if e.message.startswith('Table not found') == False:
                    print(f"テーブル確認中にエラーが発生しました: {e.message}")
                    return

            print(f"NoSQL テーブル '{self.tablename}' を作成中...")

            # TableLimitsを定義 (プロビジョニング容量の例)
            table_limits = oci.nosql.models.TableLimits(
                max_read_units=8,
                max_write_units=8,
                max_storage_in_g_bs=1,
                capacity_mode = oci.nosql.models.TableLimits.CAPACITY_MODE_PROVISIONED
            )        

            ddl_statement = f"""
            CREATE TABLE {self.tablename} (
                user_id STRING,
                session_id STRING,
                message_timestamp TIMESTAMP(3),
                title STRING,
                PRIMARY KEY (SHARD(user_id), session_id)
            ) USING TTL 90 days
            """

            create_table_details = oci.nosql.models.CreateTableDetails(
                name=self.tablename,
                compartment_id=self.compartmentid,
                ddl_statement=ddl_statement,
                table_limits=table_limits
            )

            response: oci.response.Response = self.nosqlcl.create_table(create_table_details)
            print(f"テーブル作成リクエスト送信済み。ワークリクエストID: {response.request_id}")

            oci.wait_until(
                self.nosqlcl,
                self.nosqlcl.get_table(table_name_or_id=self.tablename, compartment_id=self.compartmentid),
                'lifecycle_state',
                'ACTIVE'
            )
            print(f"テーブル '{self.tablename}' が ACTIVE 状態になりました。")

        except oci.exceptions.ServiceError as e:
            if e.code == 'TableAlreadyExists':
                print(f"テーブル '{self.tablename}' は既に存在します。")
            else:
                print(f"テーブル作成中にエラーが発生しました: {e}")
                print(f"詳細エラーメッセージ: {e.message}")
        except Exception as e:
            print(f"予期せぬエラー: {e}")

    # 子テーブル作成
    def _create_child_table( self):
        fulltablename = self.tablename + "." + self.childtablename
        print(f"NoSQL 子テーブル '{fulltablename}' を確認・作成中...")
        try:

            try:
                print(f"NoSQL 子テーブル '{fulltablename}' を確認中...")

                # テーブルが既に存在するか確認
                response: oci.response.Response = self.nosqlcl.get_table(table_name_or_id=fulltablename, compartment_id=self.compartmentid)
                tbl : oci.nosql.models.Table = response.data
                if tbl.lifecycle_state == oci.nosql.models.Table.LIFECYCLE_STATE_ACTIVE:
                    print(f"子テーブル '{fulltablename}' は既に存在します。")
                    return
            except oci.exceptions.ServiceError as e:
                if e.message.startswith('Table not found') == False:
                    print(f"テーブル確認中にエラーが発生しました: {e.message}")
                    return

            print(f"NoSQL 子テーブル '{fulltablename}' を作成中...")

            ddl_statement = f"""
            CREATE TABLE {fulltablename} (
                message_timestamp TIMESTAMP(3),
                role STRING,
                message STRING,
                PRIMARY KEY (message_timestamp)
            ) USING TTL 90 days
            """

            create_table_details = oci.nosql.models.CreateTableDetails(
                name=fulltablename,
                compartment_id=self.compartmentid,
                ddl_statement=ddl_statement
            )

            response: oci.response.Response = self.nosqlcl.create_table(create_table_details)
            print(f"子テーブル作成リクエスト送信済み。ワークリクエストID: {response.request_id}")

            oci.wait_until(
                self.nosqlcl,
                self.nosqlcl.get_table(table_name_or_id=fulltablename, compartment_id=self.compartmentid),
                'lifecycle_state',
                'ACTIVE'
            )
            print(f"子テーブル '{fulltablename}' が ACTIVE 状態になりました。")

        except oci.exceptions.ServiceError as e:
            if e.code == 'TableAlreadyExists':
                print(f"子テーブル '{fulltablename}' は既に存在します。")
            else:
                print(f"子テーブル作成中にエラーが発生しました: {e}")
                print(f"詳細エラーメッセージ: {e.message}")
        except Exception as e:
            print(f"予期せぬエラー: {e}")


    # チャット履歴保存
    def save_chat_message(self, user_id: str, session_id: str, role: str, message: str, title: str):

        fulltablename = self.tablename + "." + self.childtablename
        timestamp = datetime.datetime.now(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        # 親テーブル記録
        for i in range(self.retry_count):
            try:

                row_data = {
                    'user_id': user_id,
                    'session_id': session_id,
                    'message_timestamp': timestamp,
                    'title': title
                }
                put_row_details = oci.nosql.models.UpdateRowDetails(
                    compartment_id=self.compartmentid,
                    value=row_data
                )
                self.nosqlcl.update_row(
                    table_name_or_id=self.tablename,
                    update_row_details=put_row_details
                )
                break  # 成功したらループを抜ける

            except oci.exceptions.ServiceError as e:
                if e.status == 429:
                    print(f"NoSQL: 要求が多すぎるようだ")
                    time.sleep(self.sleep_time)
                else:
                    break
            except Exception as e:
                print(f"NoSQL: メッセージ保存中にエラーが発生しました: {e}")
                break  # エラーが発生したらループを抜ける

        # メッセージ記録
        for i in range(self.retry_count):
            try:

                row_data = {
                    'user_id': user_id,
                    'session_id': session_id,
                    'message_timestamp': timestamp,
                    'role': role,
                    'message': message
                }
                put_row_details = oci.nosql.models.UpdateRowDetails(
                    compartment_id=self.compartmentid,
                    value=row_data
                )
                self.nosqlcl.update_row(
                    table_name_or_id=fulltablename,
                    update_row_details=put_row_details
                )
                break  # 成功したらループを抜ける

            except oci.exceptions.ServiceError as e:
                if e.status == 429:
                    print(f"NoSQL: 要求が多すぎるようだ")
                    time.sleep(self.sleep_time)
                else:
                    break
            except Exception as e:
                print(f"NoSQL: メッセージ保存中にエラーが発生しました: {e}")
                break  # エラーが発生したらループを抜ける

    # チャット履歴ロード (特定のセッションIDを指定)
    def load_chat_history_for_session(self, user_id: str, session_id: str):

        fulltablename = self.tablename + "." + self.childtablename

        print(f"NoSQL: ユーザー {user_id}, セッション {session_id} の履歴を読み込み中...")

        for i in range(self.retry_count):
            history = []
            try:
                query_statement = f"""
                SELECT role, message, message_timestamp
                FROM {fulltablename}
                WHERE user_id = '{user_id}' AND session_id = '{session_id}'
                ORDER BY user_id ASC, session_id ASC, message_timestamp ASC
                """
                query_details = oci.nosql.models.QueryDetails(
                    compartment_id=self.compartmentid,
                    statement=query_statement
                )
                response: oci.response.Response = self.nosqlcl.query(query_details)
                result: oci.nosql.models.QueryResultCollection = response.data

                for item in result.items:
                    contents = []
                    txtcontent = TextContent()
                    txtcontent.type = oci.generative_ai_inference.models.TextContent.TYPE_TEXT
                    txtcontent.text = item['message']
                    contents.append(txtcontent)

                    message = Message()
                    message.role = oci.generative_ai_inference.models.Message.ROLE_ASSISTANT if item['role'] == "CHATBOT" else oci.generative_ai_inference.models.Message.ROLE_USER
                    message.content = contents

                    history.append(message)

                print(f"NoSQL: {len(history)} 件の履歴を読み込みました。")

            except oci.exceptions.ServiceError as e:
                if e.status == 429:
                    print(f"NoSQL: 要求が多すぎるようだ")
                    time.sleep(self.sleep_time)
                    continue
                else:
                    break
            except Exception as e:
                print(f"NoSQL: 履歴読み込み中にエラーが発生しました: {e}")
                break

            return history

    # ユーザーの指定セッションを削除する
    def delete_user_session(self, user_id: str, session_id: str):

        fulltablename = self.tablename + "." + self.childtablename

        print(f"NoSQL: ユーザー {user_id}, セッション {session_id} を削除中...")

        # メッセージ削除
        for i in range(self.retry_count):
            try:
                query_statement = f"""
                SELECT role, message, message_timestamp
                FROM {fulltablename}
                WHERE user_id = '{user_id}' AND session_id = '{session_id}'
                """
                query_details = oci.nosql.models.QueryDetails(
                    compartment_id=self.compartmentid,
                    statement=query_statement
                )
                response: oci.response.Response = self.nosqlcl.query(query_details)
                result: oci.nosql.models.QueryResultCollection = response.data

                for item in result.items:
                    response: oci.response.Response = self.nosqlcl.delete_row(
                        compartment_id=self.compartmentid,
                        table_name_or_id=fulltablename,
                        key=[f"user_id:{user_id}",f"session_id:{session_id}", f"message_timestamp:{item['message_timestamp']}"]
                        )
                    drr:oci.nosql.models.DeleteRowResult = response.data
                print(f"NoSQL: セッション {session_id} の削除が完了しました。")

                break  # 成功したらループを抜ける
            except oci.exceptions.ServiceError as e:
                if e.status == 429:
                    print(f"NoSQL: 要求が多すぎるようだ")
                    time.sleep(self.sleep_time)
                else:
                    break
            except Exception as e:
                print(f"NoSQL: セッション削除中にエラーが発生しました: {e}")
                break  # エラーが発生したらループを抜ける

        # 親テーブル削除
        for i in range(self.retry_count):
            try:
                query_statement = f"""
                SELECT title
                FROM {self.tablename}
                WHERE user_id = '{user_id}' AND session_id = '{session_id}'
                """
                query_details = oci.nosql.models.QueryDetails(
                    compartment_id=self.compartmentid,
                    statement=query_statement
                )
                response: oci.response.Response = self.nosqlcl.query(query_details)
                result: oci.nosql.models.QueryResultCollection = response.data

                for item in result.items:
                    response: oci.response.Response = self.nosqlcl.delete_row(
                        compartment_id=self.compartmentid,
                        table_name_or_id=self.tablename,
                        key=[f"user_id:{user_id}",f"session_id:{session_id}"]
                        )
                    drr:oci.nosql.models.DeleteRowResult = response.data
                print(f"NoSQL: セッション {session_id} の削除が完了しました。")

                break  # 成功したらループを抜ける
            except oci.exceptions.ServiceError as e:
                if e.status == 429:
                    print(f"NoSQL: 要求が多すぎるようだ")
                    time.sleep(self.sleep_time)
                else:
                    break
            except Exception as e:
                print(f"NoSQL: セッション削除中にエラーが発生しました: {e}")
                break  # エラーが発生したらループを抜ける

    # ユーザーの全セッションIDを取得する新しい関数
    def get_user_session_ids(self, user_id: str):

        print(f"NoSQL: ユーザー {user_id} のセッションIDを検索中...")

        for i in range(self.retry_count):
            session_ids = []
            try:
                # DISTINCTキーワードを使用して、重複しないsession_idを取得
                query_statement = f"""
                SELECT session_id, message_timestamp, title
                FROM {self.tablename}
                WHERE user_id = '{user_id}'
                ORDER BY user_id DESC, message_timestamp DESC
                """
                query_details = oci.nosql.models.QueryDetails(
                    compartment_id=self.compartmentid,
                    statement=query_statement
                )
                response: oci.response.Response = self.nosqlcl.query(query_details)
                result: oci.nosql.models.QueryResultCollection = response.data

                for item in result.items:
                    s_id = item['session_id']
                    message_timestamp = item['message_timestamp']
                    title = item['title']
                    session_ids.append( [s_id, message_timestamp, title] )

                print(f"NoSQL: {len(session_ids)} 件のセッションIDを検出しました。")

            except oci.exceptions.ServiceError as e:
                if e.status == 429:
                    print(f"NoSQL: 要求が多すぎるようだ")
                    time.sleep(self.sleep_time)
                    continue
                else:
                    break
            except Exception as e:
                print(f"NoSQL: セッションID取得中にエラーが発生しました: {e}")
                break

            return session_ids

    def createtable( self ) :
        self._create_table()
        self._create_child_table()
        self._create_table_index()

