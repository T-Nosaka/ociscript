#!/usr/bin/python3

import sys
import oci
import argparse

namespace='namespace'
bucket='bucketname'
destbucket='copytest'
startmatchstr=None
dryrun=False
limitcount=1000
destregion=None

#デバッグ用
DEBUG=False
#startmatchstr='chkbackup'
#dryrun=False

parser = argparse.ArgumentParser(description="using \n [namespace] [bucketname] \nex)\n objcopy.py 'namespace' 'bucketname' 'destcopy'")
parser.add_argument('namespace',help='Bucket namespace')
parser.add_argument('bucketname',help='Src Bucket Name')
parser.add_argument('destbucketname',help='Dest Bucket Name')
parser.add_argument('--destregion',help='Dest Region')
parser.add_argument('--startmatch',help='Name start match')
parser.add_argument('--dryrun', action='store_true', help='Dryrun')
parser.add_argument('--limit', type=int ,help='Count limit', default=1000)

if DEBUG==False:
    args = parser.parse_args()
    namespace = args.namespace
    bucket = args.bucketname
    destbucket = args.destbucketname
    startmatchstr = args.startmatch
    dryrun = args.dryrun
    limitcount = args.limit
    if (args.destregion is not None ):
        destregion = args.destregion

config = oci.config.from_file("~/.oci/config","DEFAULT")
if (destregion is None) :
    destregion = config['region']
objstragecl:oci.object_storage.ObjectStorageClient = oci.object_storage.ObjectStorageClient(config)

#ロード
def load(callback) :
    try:
        start_after=None
        
        while True:
            #オブジェクト一覧
            if start_after is None :
                res:oci.response.Response = objstragecl.list_objects(namespace,bucket_name=bucket,start=startmatchstr,limit=limitcount, fields="name,storageTier,archivalState")
            else :
                res:oci.response.Response = objstragecl.list_objects(namespace,bucket_name=bucket,start=start_after,limit=limitcount, fields="name,storageTier,archivalState")
            listobjs:oci.object_storage.models.ListObjects = res.data

            for obj in listobjs.objects:
                summary:oci.object_storage.models.ObjectSummary = obj
                
                #条件ヒット
                if( startmatchstr is not None ):
                    idx = summary.name.startswith(startmatchstr)
                    if idx == False :
                        continue

                callback(summary)

            start_after = listobjs.next_start_with
            if start_after is None:
                break

    except Exception as e :
        print('Exception {0} '.format(e))
        
#OnTarget
def OnTarget(summary:oci.object_storage.models.ObjectSummary) :
    
    if( (summary.storage_tier==oci.object_storage.models.ObjectSummary.STORAGE_TIER_STANDARD) or 
        (summary.storage_tier==oci.object_storage.models.ObjectSummary.STORAGE_TIER_INFREQUENT_ACCESS) or 
        ( summary.storage_tier==oci.object_storage.models.ObjectSummary.STORAGE_TIER_ARCHIVE and summary.archival_state == oci.object_storage.models.ObjectSummary.ARCHIVAL_STATE_RESTORED )):
        if ( dryrun==False):
            #コピー
            res:oci.response.Response = objstragecl.copy_object(namespace,bucket_name=bucket,copy_object_details=oci.object_storage.models.CopyObjectDetails(
                source_object_name=summary.name,
                destination_region=destregion,
                destination_namespace=namespace,
                destination_bucket=destbucket,
                destination_object_name=summary.name
            ))
#            print(res.status)
        print("{0}\t[{1},{2}]->Copy({3})".format(summary.name,summary.storage_tier,summary.archival_state,destbucket))

load(OnTarget)

