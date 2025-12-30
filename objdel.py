#!/usr/bin/python3

import sys
import oci
import argparse
from dateutil import tz
from datetime import datetime
from datetime import timedelta

namespace='namespace'
bucket='bucketname'
dryrun=True
elapsedday=None
limitday=None

#デバッグ用
DEBUG=False

parser = argparse.ArgumentParser(description="using \n [namespace] [bucketname] \nex)\n objdel.py 'namespace' 'bucketname' ")
parser.add_argument('namespace', help='namespace')
parser.add_argument('bucketname', help='bucketname')
parser.add_argument('--elapsedday', type=int, help='経過日数削除対象')
parser.add_argument('--dryrun', action='store_true', help='Dryrun')

if DEBUG==False:
    args = parser.parse_args()
    namespace = args.namespace
    bucket = args.bucketname
    dryrun = args.dryrun
    if (args.elapsedday is not None ):
        elapsedday = args.elapsedday

config = oci.config.from_file("~/.oci/config","DEFAULT")
objstragecl:oci.object_storage.ObjectStorageClient = oci.object_storage.ObjectStorageClient(config)

if elapsedday is not None :
    UTC = tz.gettz("UTC")
    limitday = datetime.now(UTC) - timedelta(days=elapsedday)


#ロード
def load():
    limitcount = 1000

    try:
        start_after=None
        while True:
            if start_after is None :
                res:oci.response.Response = objstragecl.list_objects(namespace,bucket_name=bucket,limit=limitcount,fields="name,size,timeCreated,timeModified")
            else :
                res:oci.response.Response = objstragecl.list_objects(namespace,bucket_name=bucket,start=start_after,limit=limitcount,fields="name,size,timeCreated,timeModified")
            listobjs:oci.object_storage.models.ListObjects = res.data
            for obj in listobjs.objects:
                summary:oci.object_storage.models.ObjectSummary = obj
                
                hit = True
                if limitday is not None :
                    if summary.time_modified <= limitday :
                        hit = True
                    else:
                        hit = False
                
                if hit == True :
                    if dryrun == False:
                        objstragecl.delete_object(namespace, bucket_name=bucket, object_name=obj.name )
                        
                    print("{0}:{1}".format(summary.time_modified,summary.name))
                
            start_after = listobjs.next_start_with
            if start_after is None:
                break

    except Exception as e :
        print('load エラー {0} '.format(e));

load()

