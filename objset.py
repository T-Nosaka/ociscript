#!/usr/bin/python3

#
# 標準入力からOBSへPutする
# 使用例)
# cat hogehoge.tgz | /objset.py namespace bucketname hogehoge.tgz
#

import io
import sys
import oci
import argparse
import asyncio

namespace='namespace'
bucket='bucketname'
objectname = 'test.txt'
binarymode = False
buffer_size = 1024 * 1024 * 50

#デバッグ用
DEBUG=False

parser = argparse.ArgumentParser(description="using \n [namespace] [bucketname] [objectname]\nex)\n objset.py 'namespace' 'bucketname' 'test.txt'")
parser.add_argument('namespace', help='namespace')
parser.add_argument('bucketname', help='bucketname')
parser.add_argument('objectname', help='objectname')
parser.add_argument('--binary',action='store_true', help='binary')

if DEBUG==False:
    args = parser.parse_args()
    namespace = args.namespace
    bucket = args.bucketname
    objectname = args.objectname
    if (args.binary is not None ):
        binarymode = args.binary

config = oci.config.from_file("~/.oci/config","DEFAULT")
objstragecl:oci.object_storage.ObjectStorageClient = oci.object_storage.ObjectStorageClient(config)

limitcount = 1000

#ロード
def write(buffer) :
    try:
        res:oci.response.Response = objstragecl.put_object(namespace_name=namespace,bucket_name=bucket, object_name=objectname, 
                               put_object_body = buffer )

    except Exception as e :
        print('Exception {0} '.format(e))

class MultiUploader:
    totallen = 0
    def __init__(self):
        None

    #サイズを良い感じに表現する
    def format_size(self, totallen):
        # 単位の定義
        units = ["Bytes", "KB", "MB", "GB", "TB"]
        size = totallen
        unit_index = 0

        # 適切な単位を見つける
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        # 結果を文字列でフォーマット
        return f"{size:.2f} {units[unit_index]}"

    #非同期Upload
    def async_task(self,chunk:bytes, mudata:oci.object_storage.models.MultipartUpload, part_details_list:list):
        
            partnum = 0    

            partnum=len(part_details_list)+1
            
            # パートに出力する
            part_details:oci.response.Response = objstragecl.upload_part( namespace_name=namespace,bucket_name=bucket, object_name=objectname, 
                                                upload_id=mudata.upload_id, 
                                                upload_part_num=partnum,
                                    upload_part_body=io.BytesIO(chunk) )

            part_details_list.append(oci.object_storage.models.CommitMultipartUploadPartDetails(
                part_num=partnum,
                etag=part_details.headers["ETag"]
            ))
                
            self.totallen=self.totallen+len(chunk)
            print("upload part {0}:{1}".format( len(part_details_list), self.format_size(self.totallen)) )

    #マルチパートUpload
    def upload( self ):
        #バイナリは、巨大ファイル対応としておく
        res:oci.response.Response = objstragecl.create_multipart_upload(namespace_name=namespace,bucket_name=bucket, 
                                            create_multipart_upload_details=oci.object_storage.models.CreateMultipartUploadDetails(
                                                object = objectname
                                            ) )
        mudata: oci.object_storage.models.MultipartUpload = res.data
        
        part_details_list = []
        
        tasks = []
        while True:
            # 標準入力 読み込む
            chunk:bytes = sys.stdin.buffer.read(buffer_size)
            if not chunk:
                break

            # パートに出力する
            task = self.async_task(chunk, mudata, part_details_list )
            tasks.append(task)

        #コミット
        objstragecl.commit_multipart_upload(namespace_name=namespace,bucket_name=bucket, object_name=objectname,upload_id=mudata.upload_id,
                    commit_multipart_upload_details=oci.object_storage.models.CommitMultipartUploadDetails(
                                    parts_to_commit=part_details_list) )

    def start(self):
        self.upload()

if( binarymode == False ) :
    buffer=""
    for line in sys.stdin:
        buffer+=line
    sys.stdout.write( buffer )
    write(buffer)

else :
    
    multiuploader = MultiUploader()
    multiuploader.start()

