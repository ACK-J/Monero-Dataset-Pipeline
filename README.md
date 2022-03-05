# XMR-Transaction-Automation
A script which will automate the creation of monero wallets and send transactions back and forth between them. The main purpose of this script is to create as many transactions as possible to later extract wallet information into a dataset

# Desktop Environment Configuration
If you are not using the gnome desktop environment you will have to change [this line.](https://github.com/ACK-J/XMR-Transaction-Automation/blob/acae08b4724688da0d33e7f544eee1f73e2abbaf/run.sh#L117)

# Installation
- Add machine sshkey to github
```
sudo apt update
sudo apt install jq expect python3 -y
cd ~ && wget https://downloads.getmonero.org/cli/monero-linux-x64-v0.17.3.0.tar.bz2
tar -xvf monero-linux-x64-v0.17.3.0.tar.bz2 && cd monero-x86_64-linux-gnu-v0.17.3.0 && sudo cp monero* /usr/bin/ && cd ..
git clone git@github.com:ACK-J/XMR-Transaction-Automation.git && cd XMR-Transaction-Automation
chmod +x ./run.sh && sudo chmod 777 ./FundingWallet*
monero-wallet-cli --testnet --wallet FundingWallet --daemon-address testnet.xmr-tw.org:28081 --trusted-daemon
rescan_bc soft
# Make sure terminal and sleep value for funding is correct
./run.sh
```

# Check how many terminal tabs are open
`ps --ppid $(pgrep xfce4-terminal)  | wc -l`

# Testnet Nodes
```
testnet.xmr-tw.org:28081
testnet.community.rino.io:28081
```
# Stagenet Nodes
```
stagenet.community.rino.io
```
