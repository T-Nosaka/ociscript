#!/usr/bin/python3

import http.client
import sys
import http
import oci
import argparse

namespace='namespace'
bucket='bucketname'
objectname = 'test.tgz'
binarymode = False
chunk_size = 1024*1024*50

#デバッグ用
DEBUG=False

parser = argparse.ArgumentParser(description="using \n [namespace] [bucketname] [objectname]\nex)\n objget.py 'namespace' 'bucketname' 'test.txt'")
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

#サイズを良い感じに表現する
def format_size(totallen):
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

#ロード
def load() :
    try:
        pos=0
        while(True):
            res:oci.response.Response = objstragecl.get_object(namespace_name=namespace,bucket_name=bucket, object_name=objectname, range="bytes={0}-{1}".format(pos,pos+chunk_size))
            if( res is not None and (res.status == 200 or res.status == 206) ):
                st:bytes = res.data.content
                if( binarymode == True ) :
                    sys.stdout.buffer.write(st)
                else :
                    #切れ目で化けるので、binary指定しnkfでデコードすべき
                    sys.stdout.write(st.decode('utf8'))
                    
                print("Progress: {0}".format(format_size(pos)), file=sys.stderr)
                
                pos = pos + len(st)
            else :
                break

    except oci.exceptions.ServiceError as e :
        if e.code == 'ObjectNotFound' :
            exit(2)
        else:
            exit(1)

load()
