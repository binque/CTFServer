Start Command
nohup python socket_server.py >/dev/null 2>&1 &

ReStart Command
kill -9 `ps -ef|grep socket_server.py|head -n1 |awk '{print $2}'` && nohup python socket_server.py >/dev/null 2>&1 &


