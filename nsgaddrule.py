#!/usr/bin/python3

import oci
import argparse

nsgid='ocid1.networksecuritygroup.oc1.ap-osaka-1.hogehoge'
direction = 'INGRESS'
protocol = None
port = 22
portend = 22
protocolnum = 'all'
source="192.168.1.0/24"
source_type="CIDR_BLOCK"
description = None

#デバッグ用
DEBUG=False

parser = argparse.ArgumentParser(description="using \n [nsgid] [protocol] [port] [ingress..IN, egress..OUT] [source or destination] [source_type or destination_type]  \nex)\n nsgaddrule.py 'ocid1..' 'TCP' 22 IN '192.168.1.0/24' --description 'ssh' ")
parser.add_argument('nsgid', help='nsgid')
parser.add_argument('protocol', help='TCP UDP all')
parser.add_argument('port', help='22 or 80 or 443')
parser.add_argument('direction', help='IN or OUT')
parser.add_argument('source', help='192.168.1.0/24')
parser.add_argument('--description', help='説明')

if DEBUG==False:
    args = parser.parse_args()
    nsgid = args.nsgid
    protocol = args.protocol.upper()
    if args.direction.upper() == 'IN' :
        direction = 'INGRESS'
    else:
        direction = 'EGRESS'
    source = args.source
    if args.description is not None:
        description = args.description
    try:
        port = int(args.port)
        portend = port
    except ValueError as e:
        if '-' in args.port:
            port, portend = map(int, args.port.split('-'))

tcp_options = None
udp_options = None

if protocol == 'TCP':
    protocolnum = '6'
    
    if port > 0 :
        tcp_options = oci.core.models.TcpOptions(
            destination_port_range=oci.core.models.PortRange(
                    max=portend,
                    min=port))
elif protocol == 'UDP':
    protocolnum = '17'

    if port > 0 :
        udp_options = oci.core.models.UdpOptions(
            destination_port_range=oci.core.models.PortRange(
                    max=portend,
                    min=port))
elif protocol == 'all':
    protocolnum = 'all'
else:
    protocolnum = protocol

# ルール
if direction == 'INGRESS':
    #イングレス
    ruledetail :oci.core.models.AddSecurityRuleDetails = oci.core.models.AddSecurityRuleDetails(
        direction=direction,
        protocol=protocolnum,
        is_stateless=False,
        source=source,
        source_type=source_type)
else :
    #エグレス
    ruledetail :oci.core.models.AddSecurityRuleDetails = oci.core.models.AddSecurityRuleDetails(
        direction=direction,
        protocol=protocolnum,
        is_stateless=False,
        destination=source,
        destination_type=source_type)
    

#説明
if description != None :
    ruledetail.description = description

#TCP
if tcp_options != None :
    ruledetail.tcp_options = tcp_options
#UDP
if udp_options != None :
    ruledetail.udp_options = udp_options

#VNCクライアント
config = oci.config.from_file("~/.oci/config","DEFAULT")
core_client:oci.core.VirtualNetworkClient = oci.core.VirtualNetworkClient(config)

#追加
res:oci.response.Response = core_client.add_network_security_group_security_rules(
    network_security_group_id=nsgid,
    add_network_security_group_security_rules_details=oci.core.models.AddNetworkSecurityGroupSecurityRulesDetails(
        security_rules=[ ruledetail ]))

print(res.data)
