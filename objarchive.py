#!/usr/bin/python3

import sys
import oci
import argparse

namespace='namespace'
bucket='bucketname'
startmatchstr=None
dryrun=False
limitcount=1000
restore=None

#デバッグ用
DEBUG=False
#startmatchstr='chkbackup'
#restore=24
#dryrun=True

parser = argparse.ArgumentParser(description="using \n [namespace] [bucketname] \nex)\n objarchive.py 'namespace' 'bucketname'")
parser.add_argument('namespace',help='Bucket namespace')
parser.add_argument('bucketname',help='Bucket Name')
parser.add_argument('--restore',type=int , help='Restore hours')
parser.add_argument('--startmatch',help='Name start match')
parser.add_argument('--dryrun', action='store_true', help='Dryrun')
parser.add_argument('--limit', type=int ,help='Count limit', default=1000)

if DEBUG==False:
    args = parser.parse_args()
    namespace = args.namespace
    bucket = args.bucketname
    restore = args.restore
    startmatchstr = args.startmatch
    dryrun = args.dryrun
    limitcount = args.limit

config = oci.config.from_file("~/.oci/config","DEFAULT")
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
    
    if( restore is not None):
        if( summary.storage_tier==oci.object_storage.models.ObjectSummary.STORAGE_TIER_ARCHIVE and summary.archival_state == oci.object_storage.models.ObjectSummary.ARCHIVAL_STATE_ARCHIVED ):
            if ( dryrun==False):
                #リストア
                res:oci.response.Response = objstragecl.restore_objects(namespace,bucket_name=bucket,restore_objects_details=oci.object_storage.models.RestoreObjectsDetails(
                    object_name=summary.name,
                    hours=restore
                ))
#            print(res.status)
            print("{0}\t[{1},{2}]->Restore".format(summary.name,summary.storage_tier,summary.archival_state))
        else:
            if( summary.archival_state!=oci.object_storage.models.ObjectSummary.ARCHIVAL_STATE_RESTORED):
                print("{0}\t[{1},{2}]->Restoring".format(summary.name,summary.storage_tier,summary.archival_state))
    else:
        if( summary.storage_tier==oci.object_storage.models.ObjectSummary.STORAGE_TIER_STANDARD ):
            if ( dryrun==False):
                #アーカイブ
                res:oci.response.Response = objstragecl.update_object_storage_tier(namespace,bucket_name=bucket,update_object_storage_tier_details=oci.object_storage.models.UpdateObjectStorageTierDetails(
                    object_name=summary.name,
                    storage_tier=oci.object_storage.models.UpdateObjectStorageTierDetails.STORAGE_TIER_ARCHIVE
                ))
#            print(res.status)
            print("{0}\t[{1},{2}]->Archive".format(summary.name,summary.storage_tier,summary.archival_state))

load(OnTarget)

