mkdir ../optimization_results/
mkdir ../optimization_results/temp_results/
mkdir ../optimization_results/$1/
mkdir ../optimization_results/$1/log/
sudo apt-get update
sudo apt-get install git
sudo apt install openjdk-21-jdk
# sudo apt install openjdk-17-jdk 
git clone --depth 1 https://github.com/cmu-db/benchbase.git ../benchbase
cd ../benchbase
./mvnw clean package -P $1
cd target
tar xvzf benchbase-$1.tgz
cd benchbase-$1
