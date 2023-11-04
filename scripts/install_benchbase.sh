sudo apt-get update
sudo apt-get install git
git clone --depth 1 https://github.com/cmu-db/benchbase.git ../benchbase
cd ../benchbase
./mvnw clean package -P $1
cd target
tar xvzf benchbase-$1.tgz
cd benchbase-$1