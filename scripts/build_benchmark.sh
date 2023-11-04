cd ../benchbase/target/benchbase-$1
java -jar benchbase.jar -b $2 -c config/$1/sample_$2_config.xml --create=true --load=true --clear=true --execute=false