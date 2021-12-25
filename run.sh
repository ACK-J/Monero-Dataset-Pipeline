#!/bin/bash



# Make 2 wallets per instance
while read dir 
do 
	cd "$dir"
	../MakeWallet1.exp
	../MakeWallet2.exp
	cd -
	
done < <(find ./Wallets -mindepth 1 -type d)




# Fund the wallets
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
send -- "transfer $walletAddr .1\r"
expect "*Is this okay?  (Y/Yes/N/No): *"
send -- "y\r"
expect "*wallet*]:*"
send -- "exit\r"
expect eof
EOL

chmod 777 ./FundWallet.exp && ./FundWallet.exp
sleep 1260
	
done < <(find ./Wallets/ -type f -name "*.txt")





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
send -- "transfer $walletAddr .003\r"
expect "*Is this okay?  (Y/Yes/N/No): *"
send -- "y\r"
expect "*wallet*]:*"
send -- "exit\r"
expect eof
EOL
		chmod 777 ./$walletName-spend.exp
		#  Open a new terminal tab to run the loop
		gnome-terminal --tab --command="bash -c 'while : ;do ./$walletName-spend.exp; sleep 1500;done'"
	done < <(find ./ -type f -name "*.txt")
	cd -
done < <(find ./Wallets -mindepth 1 -type d) 

