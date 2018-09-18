Start Command
nohup python manage.py >/dev/null 2>&1 &

ReStart Command
kill -9 `ps -ef|grep manage.py|head -n1 |awk '{print $2}'` && nohup python manage.py >/dev/null 2>&1 &


