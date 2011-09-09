#!/bin/bash
# A quick script to set up a jetty environment ++
#
# These commands mimic the ones that are used with debians jetty package. They also use the same
# paths (!)
#
# Packages needed:
# java (preferably sun-java5-jdk)
#
#
#apt-get install sun-java5-jdk
#apt-get install libregexp-java libsablevm-classlib1-java libservlet2.4-java libtomcat5.5-java libxerces2-java

#COPY solr/examples to /usr/share/jetty

JETTY_HOME=/usr/share/jetty
mkdir -p /var/cache/jetty /var/log/jetty $JETTY_HOME/g20 /etc/jetty
if ! id jetty > /dev/null 2>&1 ; then
            adduser --system --home /usr/share/jetty --no-create-home \
                --ingroup nogroup --disabled-password --shell /bin/false \
                jetty
fi
chown jetty:adm /var/cache/jetty /var/log/jetty 
chmod 750 /var/log/jetty 

cp jetty.default /etc/default/jetty
cp jetty.init /etc/init.d/jetty
#cp start.config /etc/jetty/
chmod 755 /etc/init.d/jetty

chown  -R jetty $JETTY_HOME/solr/

# copy in the Midcom schema file
#cp ./schema.xml $JETTY_HOME/solr/conf/
