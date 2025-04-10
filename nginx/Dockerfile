FROM nginx
COPY static-html-directory /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
COPY script.sh /etc/nginx/script.sh
COPY conf.d /etc/nginx/conf.d
#COPY myproxies.conf /etc/nginx/myproxies.conf
COPY error.html /usr/share/nginx/html

CMD /etc/nginx/script.sh && exec nginx -g 'daemon off;'