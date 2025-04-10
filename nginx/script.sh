#!/bin/bash

cd /etc/nginx/conf.d

# envsubst < /etc/nginx/conf.d/envvar.template > /etc/nginx/conf.d/myproxies.conf

findnginx="_NGINX_URL_"
finder2api="_ER2_API_"
findweb="_WEB_"

find ./ -type f -exec sed -i -e "s@$findnginx@$NGINX_URL@g" {} \;
find ./ -type f -exec sed -i -e "s@$finder2api@$ER2_API@g" {} \;
find ./ -type f -exec sed -i -e "s@$findweb@$WEB@g" {} \;