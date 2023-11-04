sudo rm /var/lib/postgresql/14/main/postgresql.auto.conf
sleep 2
su - postgres -c '/usr/lib/postgresql/14/bin/pg_ctl restart -D /var/lib/postgresql/14/main/ -o "-c config_file=/etc/postgresql/14/main/postgresql.conf"'