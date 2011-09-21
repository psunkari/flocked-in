#!/bin/bash

#
# Set variables
#

IPTABLES="/sbin/iptables"
MY_ADDRS=(`ifconfig | grep 'inet addr:' | cut -d: -f2 | awk '{print $1}' | xargs`)

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

for myIP in ${MY_ADDRS[*]}; do
  $IPTABLES -A INPUT  -i lo -s $myIP -j ACCEPT
  $IPTABLES -A OUTPUT -o lo -d $myIP -j ACCEPT
done

# Allowed TCP Services
while read dport source comment; do
  $IPTABLES -A INPUT -p tcp -m tcp -s $source --dport $dport -j ACCEPT
done <<EOF
  22  122.169.252.102     # (Prasad) SSH from Synovel
  80  0/0                 # (Prasad) HTTP
  443 0/0                 # (Prasad) HTTPS
EOF

# Related/Established
$IPTABLES -t filter -A INPUT -m state --state RELATED,ESTABLISHED -j ACCEPT
$IPTABLES -t filter -A OUTPUT -m state --state RELATED,ESTABLISHED -j ACCEPT

# ICMP
$IPTABLES -t filter -A INPUT -p icmp -m icmp --icmp-type 8 -j ACCEPT

# Accept all output
$IPTABLES -t filter -A OUTPUT -j ACCEPT

