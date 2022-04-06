# Frodo: XMR-Transaction-Automation
A script which will automate the creation of monero wallets and send transactions back and forth between them. The main purpose of this script is to create as many transactions as possible to later extract wallet information into a dataset


# Installation
- Add machine sshkey to github
```
sudo apt update
sudo apt install jq expect parallel python3 python3-tk bc curl -y
sudo apt install python3-pip -y
pip3 install numpy
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

# During collect.sh running check on progress
`find ./ -iname *.csv | cut -d '/' -f 2 | sort -u`

# After Running ./collect Gather the Ring Positions
`find . -name "*outgoing*" | xargs cat | cut -f 6 -d ',' | grep -v Ring_no/Ring_size | cut -f 1 -d '/'`

`find . -name "*cli_export*.csv" | xargs cat | wc -l`

# Sample from Gamma Distribution
```
from math import exp
import numpy as np
for i in range(100000):
	x = int(exp(np.random.gamma(19.28, 1.0/1.61, 1))) + 1200
	with open("gamma.txt","a") as fp:
		fp.write(str(x) + "\n")
```

# Problem Solving
```
#  If collect.sh throws the error: Failed to create a read transaction for the db: MDB_READERS_FULL: Environment maxreaders limit reached
/home/user/monero/external/db_drivers/liblmdb/mdb_stat -rr ~/.bitmonero/testnet/lmdb/
```

# Testnet Nodes
```
testnet.xmr-tw.org:28081
testnet.community.rino.io:28081
```
# Stagenet Nodes
```
stagenet.community.rino.io
```

# Diagrams

![run](https://user-images.githubusercontent.com/60232273/159022433-a8f371fc-2a5d-4d97-a8ec-88aa6eba759f.png)
![collect](https://user-images.githubusercontent.com/60232273/159022449-a2f0506c-7423-4283-82a5-98d54463175e.png)
![create](https://user-images.githubusercontent.com/60232273/159022486-56a2647d-2b2e-42e5-98bb-2fe583cd28e8.png)
