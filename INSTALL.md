##### Notes for deploying on CentOS 7

Add the `epel` repository and install the `nginx`, `uwsgi`, `uwsgi-python36` packages.
Install the python dependencies `python36-numpy`, `python36-Pillow`, `python36-Flask`, `python36-sep`

Clone the repository to a useful location and edit `findingchart.service` to point to it
Copy `findingchart.service` to `/usr/lib/systemd/system/`

Create a directory `/srv/sockets` and `chown nginx:nginx` it.

Enable and start the `findingchart` service.

Add to the nginx config
```
location = /findingchart { rewrite ^ /findingchart/; }

location /findingchart/static {
    alias {{PROJECT_PATH}}/static;
}

location /findingchart/ {
    uwsgi_pass unix:/srv/sockets/findingchart.sock;
    uwsgi_param SCRIPT_NAME /findingchart;
    include uwsgi_params;
}
```

Enable and start the `nginx` service.
Open the firewall if needed `sudo firewall-cmd --permanent --zone=public --add-service=http && sudo firewall-cmd --reload`