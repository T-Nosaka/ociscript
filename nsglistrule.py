#!/usr/bin/python3

import oci
import argparse
import re

nsgid='ocid1.networksecuritygroup.oc1.ap-osaka-1.hogehoge'

#デバッグ用
DEBUG=False
isdeleteyes=False
isdelete=False
keyword=None

parser = argparse.ArgumentParser(description="using \n [nsgid] \nex)\n nsglistrule.py 'ocid1..' ")
parser.add_argument('nsgid', help='nsgid')
parser.add_argument('-delete', help='delete', action='store_true')
parser.add_argument('-y', '--yes', help='delete yes', action='store_true')
parser.add_argument('--keyword', help='keyword')

if DEBUG==False:
    args = parser.parse_args()
    nsgid = args.nsgid
    isdelete = args.delete
    isdeleteyes = args.yes
    if args.keyword is not None:
        keyword = args.keyword

#VNCクライアント
config = oci.config.from_file("~/.oci/config","DEFAULT")
core_client:oci.core.VirtualNetworkClient = oci.core.VirtualNetworkClient(config)

#全リスト
res:oci.response.Response = core_client.list_network_security_group_security_rules(nsgid)
srlist = res.data

ids = []
sr:oci.core.models.SecurityRule
for sr in res.data :

    STATEENV="STATEFUL"
    if sr.is_stateless == True:
        STATEENV="STATELESS"

    #Protocol
    PRT=sr.protocol
    PORT="Any"
    if sr.protocol == '6' :
        PRT = "TCP"
        tcpops:oci.core.models.TcpOptions = sr.tcp_options
        if tcpops is not None and tcpops.destination_port_range is not None:
            if tcpops.destination_port_range.max == tcpops.destination_port_range.min:
                PORT = tcpops.destination_port_range.max
            else:
                PORT = "{0}-{1}".format(tcpops.destination_port_range.min,tcpops.destination_port_range.max)
        
    if sr.protocol == '17' :
        PRT = "UDP"
        udpops:oci.core.models.UdpOptions = sr.udp_options
        if udpops is not None and udpops.destination_port_range is not None:
            if udpops.destination_port_range.max == udpops.destination_port_range.min:
                PORT = udpops.destination_port_range.max
            else:
                PORT = "{0}-{1}".format(udpops.destination_port_range.min,udpops.destination_port_range.max)

    if sr.direction == "EGRESS" :
        outputstr="{0}\t{1}\t{2}\t{3}\tDEST={4}\t{5}\t{6}".format(sr.direction, STATEENV, PRT, sr.destination_type ,sr.destination, PORT, sr.description )
    else :
        outputstr="{0}\t{1}\t{2}\t{3}\tSRC={4}\t{5}\t{6}".format(sr.direction, STATEENV, PRT, sr.source_type, sr.source, PORT, sr.description)

    if keyword != None:
        mc = re.search(keyword, outputstr )
        if mc == None:
            continue

    print(outputstr)
    
    if isdelete == True:
        yesno = 'N'
        if isdeleteyes == False:
            yesno = input("Delete Files. OK? [y/N]: ").lower()
        else:
            yesno = 'y'
        
        if yesno in ['y', 'yes']:
            ids.append(sr.id)

if isdelete == True:
    #削除
    res:oci.response.Response = core_client.remove_network_security_group_security_rules(
        nsgid, 
        remove_network_security_group_security_rules_details = oci.core.models.RemoveNetworkSecurityGroupSecurityRulesDetails(
                        security_rule_ids=ids) )

    print("Deleted.")
