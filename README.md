# Monero Dataset Pipeline
A pipeline that automates the creation and transaction of monero wallets used to collect a dataset suitable for supervised learning applications. 

# Installation
```
sudo apt update
sudo apt install vim git jq expect tmux parallel python3 python3-tk bc curl python3-pip -y
pip3 install numpy
cd ~ && wget https://downloads.getmonero.org/cli/monero-linux-x64-v0.17.3.0.tar.bz2
tar -xvf monero-linux-x64-v0.17.3.0.tar.bz2 && cd monero-x86_64-linux-gnu-v0.17.3.0 && sudo cp monero* /usr/bin/ && cd ..
git clone git@github.com:ACK-J/Monero-Dataset-Pipeline.git && cd XMR-Transaction-Automation
chmod +x ./run.sh && chmod 777 -R Funding_Wallets/
# Make sure global variables are set
./run.sh
```

# Problem Solving and Useful Commands
```
#  If collect.sh throws the error: Failed to create a read transaction for the db: MDB_READERS_FULL: Environment maxreaders limit reached
/home/user/monero/external/db_drivers/liblmdb/mdb_stat -rr ~/.bitmonero/testnet/lmdb/
```
### Check progress of collect.sh While it is Running
`find ./ -iname *.csv | cut -d '/' -f 2 | sort -u`
### After Running collect.sh Gather the Ring Positions
`find . -name "*outgoing*" | xargs cat | cut -f 6 -d ',' | grep -v Ring_no/Ring_size | cut -f 1 -d '/'`





# Data Collection Pipeline Flowcharts
## Run.sh
<p align="center">
  <img src="https://user-images.githubusercontent.com/60232273/181663123-2d0fb9c9-8787-42c8-8ec7-24b45c201bc5.png"/>
</p>

## Collect.sh
<p align="center">
  <img src="https://user-images.githubusercontent.com/60232273/181663094-ff823283-cf74-420a-b5db-f517489b9f31.png"/>
</p>

## Create_Dataset.py
<p align="center">
  <img src="https://user-images.githubusercontent.com/60232273/181663063-2c34dbc3-ce99-49c5-9807-b952c7f4fd68.png"/>
</p>



