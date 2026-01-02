#!/usr/bin/python3

#
# 月費用通知スクリプト
#

import oci
import datetime
import argparse

topicid = "ocid1.onstopic.oc1.ap-osaka-1.hogehoge"
topictitle = "OCI 月費用"
nonotify = False

today = datetime.date.today()
sdate = datetime.datetime(today.year, today.month, 1,0,0,0)
edate = datetime.datetime(today.year, today.month, today.day, 0, 0, 0)

config = oci.config.from_file("~/.oci/config","DEFAULT")
TENANTID=config["tenancy"]
usageapicl:oci.usage_api.UsageapiClient = oci.usage_api.UsageapiClient(config)
notifydatacl = oci.ons.NotificationDataPlaneClient(config)

DEBUG=False

if DEBUG==False :
    parser = argparse.ArgumentParser(description="using \n \nex)\n costchk.py")
    parser.add_argument('--topicid', help='通知トピックID')
    parser.add_argument('--nonotify', action='store_true', help='通知無効')
    args = parser.parse_args()
    if args.topicid is not None:
        topicid = args.topicid
    if args.nonotify is not None:
        nonotify = args.nonotify

#通知
def notifyMessage(msg) :
    notifydatacl.publish_message(topicid,oci.ons.models.MessageDetails(
        title=topictitle,
        body=msg
        ),message_type="RAW_TEXT")

#コスト報告
def reportcost() :
    res:oci.response.Response = usageapicl.request_summarized_usages( oci.usage_api.models.RequestSummarizedUsagesDetails(
        tenant_id=TENANTID,
        time_usage_started=sdate,
        time_usage_ended=edate,
        granularity=oci.usage_api.models.RequestSummarizedUsagesDetails.GRANULARITY_MONTHLY,
        query_type=oci.usage_api.models.RequestSummarizedUsagesDetails.QUERY_TYPE_COST
    ))
    result:oci.usage_api.models.UsageAggregation=res.data

    for item in result.items:
        amount = item.computed_amount
        currency = item.currency
        if ( amount is not None ) :
            msg = " {0} {1} {2:%Y/%m/%d}-{3:%d} ".format(currency,round(amount,1),sdate,edate)
            print(msg)
            if nonotify == False:
                notifyMessage(msg)

reportcost()
