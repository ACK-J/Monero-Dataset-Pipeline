#!/bin/bash
# This script will create pairs of wallets which will transact between eachother. Due to
# monero's 20 minute lockout period, creating a large amount of simulated transactions is
# difficult. This script automates the wallet creation, funding and will transact between
# wallets infinitely. The only manual setup is to have a wallet with a large amount of testnet
# coins within the root directory, and it must be named "FundingWallet". 

# Usage: chmod +x ./run.sh && ./run.sh





# Ask the user for a number of wallets to make
read -p "How many wallets would you like (ex. 10)? " numwallets
cd "./Wallets"
# Create the directories which will store 2 wallets each
for i in `seq $(($numwallets / 2))`; do mkdir $i; done
cd -



# Make 2 wallets per folder
while read dir 
do 
	cd "$dir"
	../MakeWallet1.exp
	../MakeWallet2.exp
	cd -
	
done < <(find ./Wallets -mindepth 1 -type d | sort -u)





# Fund the wallets (This part is slow but no real way around it)
while read walletFile; do 
walletAddr=`cat "$walletFile"`
cat > ./FundWallet.exp <<EOL 
#!/usr/bin/expect -f
set timeout -1 
spawn monero-wallet-cli --testnet --wallet ./FundingWallet --daemon-address testnet.melo.tools:28081 --log-file /dev/null --trusted-daemon
match_max 10000
expect "Wallet password: "
send -- "\r"

expect "wallet*]:*"
send -- "transfer $walletAddr 0.35\r"

expect {

        "Transaction successfully submitted*wallet*]:*" {send "exit\r"}

        "Error: *\[wallet*" {sleep 1;send "transfer $walletAddr 0.35\r";exp_continue}
	
        "(out of sync)]: *" {send "refresh\r";exp_continue}
                               
        "Is this okay?  (Y/Yes/N/No): *"  {send "y\r";exp_continue}
	
	timeout {send "transfer $walletAddr \$amount\r";exp_continue} 
              
}
expect eof
EOL

chmod 777 ./FundWallet.exp && ./FundWallet.exp
echo "Wallet $walletFile Funded!" && date
sleep 600 # Wait 10 minutes instead of 20
	
done < <(find ./Wallets/ -type f -name "*.txt" | sort -u)





# Start Transfers
while read dir ;do  # Loop each directory
	cd "$dir"
	while read walletAddrFile; do  # Loop each .txt wallet addr file
	
		#  Gets the name of the current wallet file
		walletName=`echo $walletAddrFile | cut -f 2 -d "." | cut -f 2 -d "/"`
		#  Since we want to transfer to the other wallet we need to switch the numbers
		
		if [ "${walletName: -1}" -eq "2" ];then  # check if the last number of the wallet is a 2
			recvWalletFile="${walletAddrFile//[2]/1}"  # Swap it with a 1
		else  # The last num is a 1 -> swap it to a 2
			recvWalletFile="${walletAddrFile//[1]/2}"
		fi
		walletAddr=`cat "$recvWalletFile"`

# Write an expect script
cat > ./$walletName-spend.exp <<EOL 
#!/usr/bin/expect -f
if {[llength \$argv] != 2} {
  puts stderr "Usage: Pass an amount and a priority as arguments!"
  exit 1
}
set timeout 90
set amount [lindex \$argv 0];   # 0.0001 -> .000000000001
set priority [lindex \$argv 1];   # 0 -> 4
spawn monero-wallet-cli --testnet --wallet ./$walletName --daemon-address testnet.melo.tools:28081 --log-file /dev/null --trusted-daemon
match_max 10000
expect "Wallet password: "
send -- "\r"
expect "wallet*]:*"
send -- "set priority \$priority\r"
expect "Wallet password: "
send -- "\r"
expect "wallet*]:*"
send -- "transfer $walletAddr \$amount\r"

expect {

        "Transaction successfully submitted*wallet*]:*" {send "exit\r"}
	
        "Error: *\[wallet*" {sleep 15;send "transfer $walletAddr \$amount\r";exp_continue}
	
        "(out of sync)]: *" {send "refresh\r";exp_continue}
                               
        "Is this okay?  (Y/Yes/N/No): *"  {send "y\r";exp_continue}
	
	timeout {send "transfer $walletAddr \$amount\r";exp_continue}
        
}
expect eof
EOL
		chmod 777 ./$walletName-spend.exp
		#  Open a new terminal tab -> Run the expect script to send a transaction of a random amount -> print time / transaction # -> sleep a random time selected from gamma distribution
		xfce4-terminal --tab -x /bin/bash -c "i=1; while : ;do ./${walletName}-spend.exp $(python3 -c "import random;sci=random.uniform(0.0001, 0.000000000001);print(format(sci, \".12f\"))") $(python3 -c "import random;print(random.randrange(0,5))"); date; echo -en '\033[34mNumber of successful transactions: \033[0m'; echo \$i; ((i++)); python3 ../../Gamma.py;done"
		sleep 60
	done < <(find ./ -type f -name "*.txt" | sort -u)
	cd - # Reset the directory
done < <(find ./Wallets -mindepth 1 -type d | sort -u) 
