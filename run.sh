#!/bin/bash
# This script will create pairs of wallets which will transact between eachother. Due to
# monero's 20 minute lockout period, creating a large amount of simulated transactions is
# difficult. This script automates the wallet creation, funding and will transact between
# wallets infinitely. The only manual setup is to have a wallet with a large amount of testnet
# coins within the root directory, and it must be named "FundingWallet". 

# Usage: chmod +x ./run.sh && ./run.sh





# Ask the user for a number of wallets to make
read -p "About how many wallet pairs would you like (ex. 10)?" numwallets
cd "./Wallets"
# Create the directories which will store 2 wallets each
for i in {1..$(($numwallets / 2))}; do mkdir $i; done
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
spawn monero-wallet-cli --testnet --wallet ./FundingWallet --daemon-address testnet.xmr-tw.org:28081 --log-file /dev/null
match_max 100000
expect "*Wallet password: "
send -- "\r"

expect "*wallet*]:*"
send -- "transfer $walletAddr .004\r"

expect {

        "*Error: Not enough money in unlocked balance*\[wallet*" {send "transfer $walletAddr .004\r";exp_continue}
        
        "*Error: transaction cancelled*wallet*]:*" {send "transfer $walletAddr .004\r";exp_continue}
                                
        "*(out of sync)*" {send "refresh\r";exp_continue}
	
        "*Is this okay?  (Y/Yes/N/No): *"  {send "y\r";exp_continue}
        
        "*Transaction successfully submitted*wallet*]:*" {send ""}
        
}

expect "*wallet*]:*"
send -- "unspent_outputs\r"
expect "*wallet*]:*"
send -- "exit\r"
expect eof
EOL

chmod 777 ./FundWallet.exp && ./FundWallet.exp
echo "Wallet $walletFile Funded!"
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
set timeout -1
spawn monero-wallet-cli --testnet --wallet ./$walletName --daemon-address testnet.xmr-tw.org:28081 --log-file /dev/null
match_max 100000
expect "*Wallet password: "
send -- "\r"
expect "*wallet*]:*"
send -- "transfer $walletAddr .0001\r"

expect {

        "*Error: Not enough money in unlocked balance*\[wallet*" {send "transfer $walletAddr .0001\r";exp_continue}
        
        "*Error: transaction cancelled*wallet*]:*" {send "transfer $walletAddr .0001\r";exp_continue}
                                
        "*(out of sync)*" {send "refresh\r";exp_continue}
	
        "*Is this okay?  (Y/Yes/N/No): *"  {send "y\r";exp_continue}
        
        "*Transaction successfully submitted*wallet*]:*" {send ""}
        
}

expect "*wallet*]:*"
send -- "exit\r"
expect eof
EOL
		chmod 777 ./$walletName-spend.exp
		#  Open a new terminal tab to loop the transactions
		gnome-terminal --tab --command="bash -c 'while : ;do ./$walletName-spend.exp; sleep 1200;done'"
	done < <(find ./ -type f -name "*.txt" | sort -u)
	cd - # Reset the directory
done < <(find ./Wallets -mindepth 1 -type d | sort -u) 
