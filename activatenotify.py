#!/bin/python3
#
# 通知サブスクリプション アクティベート催促 スクリプト
#
# activatenotify.py
#

import oci
import argparse

TOPICID = "ocid1.onstopic.oc1.ap-osaka-1.hogehoge"

#デバッグ用
DEBUG=False

parser = argparse.ArgumentParser(description="using \n [topicid]\nex)\n activatenotify.py 'ocid1.onstopic.oc1.ap-osaka-1.hogehoge' ")
parser.add_argument('topicid', help='topicid')
if DEBUG==False:
    args = parser.parse_args()
    TOPICID = args.topicid

#認証
config = oci.config.from_file("~/.oci/config","DEFAULT")
notificationClient:oci.ons.NotificationDataPlaneClient = oci.ons.NotificationDataPlaneClient(config)
notifycntClient:oci.ons.NotificationControlPlaneClient = oci.ons.NotificationControlPlaneClient(config)

res:oci.response.Response = notifycntClient.get_topic( TOPICID )
topic:oci.ons.models.NotificationTopic = res.data

res:oci.response.Response = notificationClient.list_subscriptions(topic.compartment_id,topic_id=TOPICID , limit=100)
summary:oci.ons.models.SubscriptionSummary
for summary in res.data:
    if summary.lifecycle_state == 'PENDING':
        print("Resend:{0}".format(summary.endpoint))

        res:oci.response.Response = notificationClient.resend_subscription_confirmation(summary.id)
