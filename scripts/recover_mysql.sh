ps aux | grep mysql | grep -v grep | grep -v python | grep -v recover_mysql| awk '{print $2}' | xargs kill -9
sleep 5
/usr/bin/mysqld_safe &