##### Notes for deploying on OpenSUSE

Install nginx, uwsgi, uwsgi-python3 packages (need server repo enabled).

Clone the repository to /srv/findingchart/appdata/ and chown -R nginx:nginx
Move config/findingchart.ini to /etc/uwsgi/vassals/ (uWSGI Emperor config file)
Move config/findingchart.conf to /etc/nginx/conf.d/ (nginx config file)

Open port 80 in the firewall by setting `FW_SERVICES_EXT_TCP="80"` in /etc/sysconfig/SuSEfirewall2

Enable and start services

```
systemctl enable nginx uwsgi
systemctl start nginx uwsgi
systemctl restart SuSEfirewall2
```

