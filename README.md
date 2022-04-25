# XMR-Transaction-Automation
A script which will automate the creation of monero wallets and send transactions back and forth between them. The main purpose of this script is to create as many transactions as possible to later extract wallet information into a dataset


# Installation
- Add machine sshkey to github
```
sudo apt update
sudo apt install vim git jq expect tmux parallel python3 python3-tk bc curl python3-pip -y
pip3 install numpy
cd ~ && wget https://downloads.getmonero.org/cli/monero-linux-x64-v0.17.3.0.tar.bz2
tar -xvf monero-linux-x64-v0.17.3.0.tar.bz2 && cd monero-x86_64-linux-gnu-v0.17.3.0 && sudo cp monero* /usr/bin/ && cd ..
git clone git@github.com:ACK-J/XMR-Transaction-Automation.git && cd XMR-Transaction-Automation
chmod +x ./run.sh && chmod 777 -R Funding_Wallets/
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

# Debugging Large Amounts of Wallets (too many open files)
```
ulimit -a
# Add this to .bashrc
ulimit -n 10240
```

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
![Ring Members](https://user-images.githubusercontent.com/60232273/165125319-eb7f7181-b9a2-4c77-8d79-5a332de9e8c3.png)
![run.sh](https://user-images.githubusercontent.com/60232273/165125440-dcd45d20-e4a6-401d-a9d0-57b56a90cb68.png)
![collect.sh](https://user-images.githubusercontent.com/60232273/165125464-a08958b8-140c-4fa8-af29-67fa39613d65.png)
![creat_dataset.py](https://user-images.githubusercontent.com/60232273/165125480-fbf94b36-a8bc-4255-bb78-259b542712f2.png)



