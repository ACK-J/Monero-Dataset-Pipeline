# XMR-Transaction-Automation
A script which will automate the creation of monero wallets and send transactions back and forth between them. The main purpose of this script is to create as many transactions as possible to later extract wallet information into a dataset

# Setting up directories
`for i in {1..100}; do mkdir $i; done`

# Installation
```
sudo apt install jq expect -y
cd ~ && wget https://downloads.getmonero.org/cli/monero-linux-x64-v0.17.3.0.tar.bz2
tar -xvf monero-linux-x64-v0.17.3.0.tar.bz2 && cd monero-x86_64-linux-gnu-v0.17.3.0 && sudo cp monero* /usr/bin/
git clone git@github.com:ACK-J/XMR-Transaction-Automation.git && cd XMR-Transaction-Automation
chmod +x ./run.sh && ./run.sh
```
