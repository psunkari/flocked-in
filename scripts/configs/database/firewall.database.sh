#!/bin/bash

#
# Set variables
#

IPTABLES="/sbin/iptables"
MY_ADDRS=(`ifconfig | grep 'inet addr:' | cut -d: -f2 | awk '{print $1}' | xargs`)

CASSANDRA_CLIENTS="10.182.5.140 10.182.5.36"
CASSANDRA_NODES="10.182.5.142 10.182.5.250 10.182.4.64"
MIRAGE_UID=`id -u mirage`

#
# Kernel Tuning: Set the necessary kernel parameters
#

# Disable response to icmp broadcasts [avoid being bad guy in smurf attacks]
echo "1" > /proc/sys/net/ipv4/icmp_echo_ignore_broadcasts

# Don't accept source routed packets
echo "0" > /proc/sys/net/ipv4/conf/all/accept_source_route

# Disable ICMP redirects
# ICMP redirecting can be used to alter our routing table
echo "0" > /proc/sys/net/ipv4/conf/all/accept_redirects

# Prevent spoofing.
# Interfaces on which a packet arrives should match our routing table
echo "1" > /proc/sys/net/ipv4/conf/all/rp_filter
echo "1" > /proc/sys/net/ipv4/ip_forward

#
# Set the default policies
#

$IPTABLES -P INPUT DROP
$IPTABLES -P OUTPUT DROP
$IPTABLES -P FORWARD DROP
$IPTABLES -X
$IPTABLES -F
$IPTABLES -F INPUT
$IPTABLES -F OUTPUT
$IPTABLES -F FORWARD
$IPTABLES -F POSTROUTING -t nat
$IPTABLES -F PREROUTING -t nat
$IPTABLES -X


###############################################################################
# Access to this Computer
#

# Don't allow user 'mirage' to connect outside
$IPTABLES -t filter -A OUTPUT -m owner --uid-owner $MIRAGE_UID -p tcp -m state --state NEW -j DROP
$IPTABLES -t filter -A OUTPUT -m owner --uid-owner $MIRAGE_UID -p tcp -m state --state NEW -j DROP

for myIP in ${MY_ADDRS[*]}; do
  $IPTABLES -A INPUT  -i lo -s $myIP -j ACCEPT
  $IPTABLES -A OUTPUT -o lo -d $myIP -j ACCEPT
done

# Allowed TCP Services
#while read dport source comment; do
#  $IPTABLES -A INPUT -p tcp -m tcp -s $source --dport $dport -j ACCEPT
#done <<EOF
#  22  122.169.252.102     # (Prasad) SSH from Synovel
#EOF

# Services for cassandra clients
for client in ${CASSANDRA_CLIENTS[*]}; do
  #$IPTABLES -A INPUT -p tcp -m tcp -s $client --dport 7199 -j ACCEPT  # JMX
  $IPTABLES -A INPUT -p tcp -m tcp -s $client --dport 9160 -j ACCEPT  # Thrift
done

# Services for other servers in the cluster
for client in ${CASSANDRA_NODES[*]}; do
  $IPTABLES -A INPUT -p tcp -m tcp -s $client --dport 7000 -j ACCEPT  # Gossip
  #$IPTABLES -A INPUT -p tcp -m tcp -s $client --dport 7199 -j ACCEPT  # JMX
  $IPTABLES -A INPUT -p tcp -m tcp -s $client --dport 9160 -j ACCEPT  # Thrift
done

# Related/Established
$IPTABLES -t filter -A INPUT -m state --state RELATED,ESTABLISHED -j ACCEPT
$IPTABLES -t filter -A OUTPUT -m state --state RELATED,ESTABLISHED -j ACCEPT

# ICMP
$IPTABLES -t filter -A INPUT -p icmp -m icmp --icmp-type 8 -j ACCEPT

# Accept all output
$IPTABLES -t filter -A OUTPUT -j ACCEPT

