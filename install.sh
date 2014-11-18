#!/bin/bash
source ./ssl_config

set -e 

update_packages() {
    sudo apt-get update
}

install_packages() {
    for package in "$@"
    do
        if ! dpkg-query -l $package 1>&2 > /dev/null; then
            echo "Installing $package"
            sudo apt-get -y install "$package"
        else
            echo "$package already installed"
        fi
    done
}

is_raspbian() {
    if [ -e /etc/os-release ] && [ $(grep '^ID=' /etc/os-release) == 'ID=raspbian' ]; then
        return 0
    else
        return 1
    fi
}

update_pi_firmware() {
    if is_raspbian; then
        sudo rpi-update
    else
        echo "Doesn't appear to be raspbian"
    fi
}

create_dir_as_root() {
    for dir in "$@"
    do
        if [ ! -d ${dir} ] ; then
            echo "Creating dir: $dir"
            sudo mkdir -p ${dir}
        else
            echo "Dir already exists: ${SSL_DIR}"
        fi
    done
}

install_pcb_web() {
    echo "Copying over pcb_drill_web over into /etc/init.d"
    sudo cp pcb_drill_web/initd/raspbian/pcb_drill_web /etc/init.d
    # Moving away from virtualenv
    sudo pip install -r requirements.txt
}

install_pcb_drilld() {
    echo "Copying over pcb_drilld over into /etc/init.d"
    echo "You will be able to use the service pcb_drilld to start/stop the daemon"
    sudo cp pcb_drilld/initd/raspbian/pcb_drilld /etc/init.d
    install_packages python-pip python-virtualenv
    install_packages python-opencv python-scipy python-numpy python-setuptools
    sudo pip install https://github.com/sightmachine/SimpleCV/zipball/master
    sudo pip install svgwrite
}

install_nginx_with_self_signed_ssl() {
    #NGINX_SITES_AVAILABLE=/etc/nginx/sites-available
    #NGINX_SITES_ENABLED=/etc/nginx/sites-enabled
    NGINX_CONFIGD=/etc/nginx/conf.d
    SSL_DIR=/etc/nginx/ssl
    if [ -z "$CONFIG" ] || [ -z "$COUNTRY_CODE" ] || [ -z "$STATE" ] || [ -z "$CITY" ]\
        || [ -z "$COMPANY" ] || [ -z "$SECTION" ] || [ -z "$COMMON_NAME" ] \
        || [ -z "$EMAIL" ]; then
        echo "ERROR: please configure ./ssl_config"
        exit 2
    fi
    echo "Nginx Configuration for DartFrog"
    echo "--------------------------------"
    echo "This is the configuration for octoprint & pcb_drill under SSL with nginx"
    echo "We assume sudo works"
    echo
    install_packages nginx openssl
    if [ "$config_force" == "1" ] ; then
        echo "Forcing things!!!"
    fi
    create_dir_as_root ${SSL_DIR}

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
    if [ ! -f ${NGINX_CONFIGD}/${CONFIG}.conf ] || [ "$config_force" == "1" ] ; then
        echo "Copying over ${CONFIG}.conf config"
        sudo cp nginx_conf/${CONFIG}.conf ${NGINX_CONFIGD}
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
    #if [ ! -f ${NGINX_SITES_ENABLED}/${CONFIG} ] || [ "$config_force" == "1" ] ; then
    #    sudo ln -fs ${NGINX_CONFIGD}/${CONFIG} ${NGINX_SITES_ENABLED}/${CONFIG}
    sudo service nginx restart
    #else
    #    echo "Seems config is already activated, nothing to do"
    #fi
}


show_usage() {
    cat << EOD
Usage: ${0##*/} [-hwfdD]
Install pcb_drill.
    -h, --help          help (this output)
    -n, --nginx         Install & configure nginx to use self-signed cert
    -w, --web           Install pcb_drill_web
    -f, --firmware      Update Raspberry pi firmware
    -F, --force         Force things
    -d, --daemon        Install pcb_drilld daemon
    -D, --development   Install development packages
    -i, --install       Install it all
EOD
}


# Args
config_web=0
config_nginx=0
config_daemon=0
config_firmware=0
config_development=0
config_force=0
verbose=0


while :; do
    case $1 in
        -h|-\?|--help)
            show_usage
            exit
            ;;
        -n|--nginx)
            config_nginx=1
            ;;
        -w|--web)
            config_web=1
            ;;
        -d|--daemon)
            config_daemon=1
            ;;
        -F|--force)
            config_force=1
            ;;
        -D|--development)
            config_development=1
            ;;
        -f|--firmware)
            config_firmware=1
            ;;
        -i|--install)
            config_nginx=1
            config_web=1
            config_daemon=1
            config_development=1
            config_firmware=1
            ;;
        --)
            shift
            break
            ;;
        -?*)
            echo "Unknown option $1"
            ;;
        *)
            break
    esac
    shift
done

echo "pcb_drill configuration for DartFrog"
echo "--------------------------------"
echo "We assume sudo works"
echo

if [ "$config_web" == 0 ] && [ "$config_daemon" == 0 ] \
     && [ "$config_firmware" == 0 ] && [ "$config_nginx" == 0 ] \
     && [ "$config_development" == 0 ]; then
    echo 'Nothing to do'
    show_usage
    exit 1
else
    echo "Let's do things"
    echo "-=-=-=-=-=-=-=-"
fi

if [ "$config_nginx" == 1 ]; then
    install_nginx_with_self_signed_ssl
fi

if [ "$config_web" == 1 ]; then
   install_pcb_web 
fi

if [ "$config_daemon" == 1 ]; then
    install_pcb_drilld
fi

if [ "$config_firmware" == 1 ] ; then
    update_pi_firmware
fi

if [ "$config_development" == 1 ] ; then
    install_packages mc vim cowsay
fi
