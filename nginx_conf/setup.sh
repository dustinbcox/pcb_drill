#!/bin/bash
set +eE

#NGINX_SITES_AVAILABLE=/etc/nginx/sites-available
#NGINX_SITES_ENABLED=/etc/nginx/sites-enabled
NGINX_CONFIGD=/etc/nginx/conf.d
SSL_DIR=/etc/nginx/ssl

# SSL Cert Stuff
CONFIG=dartfrog
COUNTRY_CODE=US
STATE=Florida
CITY=Orlando
COMPANY=DartFrog
SECTION="3d printing"
COMMON_NAME="www.dustinbcox.com"
EMAIL=dustin@dustinbcox.com

echo "Nginx Configuration for DartFrog"
echo "--------------------------------"
echo "This is the configuration for octoprint & pcb_drill under SSL with nginx"
echo "We assume sudo works"
echo

if [ "$FORCE" == "1" ] ; then
    echo "FORCE flag set!!!"
fi

echo "Let's install things"

sudo apt-get update

# Nginx Install
if ! dpkg-query -l nginx > /dev/null; then
    echo "Installing nginx"
    sudo apt-get -y install nginx
else
    echo "Nginx already installed"
fi

# Openssl install
if ! dpkg-query -l openssl > /dev/null; then
    echo "Installing openssl"
    sudo apt-get -y install openssl
else
    echo "openssl already installed"
fi


# SSL dir
if [ ! -d ${SSL_DIR} ] ; then
    echo "Creating ssl dir: $SSL_DIR"
    sudo mkdir -p ${SSL_DIR}
else
    echo "SSL dir already exists: ${SSL_DIR}"
fi

# SSL key
if [ ! -f ${SSL_DIR}/${CONFIG}.key ]; then
    sudo openssl genrsa -out ${SSL_DIR}/${CONFIG}.key 1024
    sudo chmod 640 ${SSL_DIR}/${CONFIG}.key
fi
# SSL CSR
if [ ! -f ${SSL_DIR}/${CONFIG}.csr ]; then
    sudo openssl req -new -key ${SSL_DIR}/${CONFIG}.key -out ${SSL_DIR}/${CONFIG}.csr <<EOD
$COUNTRY_CODE
$STATE
$CITY
$COMPANY
$SECTION
$COMMON_NAME
$EMAIL


EOD
    echo
    sudo chmod 640 ${SSL_DIR}/${CONFIG}.csr
else
    echo "CSR already exists"
fi

# SSL Sign Cert
if [ ! -f ${SSL_DIR}/${CONFIG}.crt ]; then
    sudo openssl x509 -req -days 365 -in ${SSL_DIR}/${CONFIG}.csr -signkey ${SSL_DIR}/${CONFIG}.key -out ${SSL_DIR}/${CONFIG}.crt
    sudo chmod 640 ${SSL_DIR}/${CONFIG}.crt 
else
    echo "Signed cert already exists"
fi


# Nginx Config
if [ ! -f ${NGINX_CONFIGD}/${CONFIG}.conf ] || [ "$FORCE" == "1" ] ; then
    echo "Copying over ${CONFIG}.conf config"
    sudo cp ${CONFIG}.conf ${NGINX_CONFIGD}
else
    echo "WARNING: ${NGINX_CONFIGD}/${CONFIG}.conf already exists"
    echo "Not overwriting... I hope this is what you want."
fi

# Remove default site
if [ -L ${NGINX_SITES_ENABLED}/default ]; then
    sudo rm ${NGINX_SITES_ENABLED}/default
    echo "Removing default site"
fi

# Activate config
#if [ ! -f ${NGINX_SITES_ENABLED}/${CONFIG} ] || [ "$FORCE" == "1" ] ; then
#    sudo ln -fs ${NGINX_CONFIGD}/${CONFIG} ${NGINX_SITES_ENABLED}/${CONFIG}
sudo service nginx restart
#else
#    echo "Seems config is already activated, nothing to do"
#fi

