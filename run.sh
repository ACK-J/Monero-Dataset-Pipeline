#!/bin/bash
# This script will create pairs of wallets which will transact between eachother.
# This script automates the wallet creation, funding and will transact between them
# in the background until the specified stop time. The only manual setup is to have a wallet with a
# large amount of coins within ./Funding_Wallets/, and it must be named ${NETWORK^}-Funding.

# Usage: chmod +x ./run.sh && ./run.sh
# Dependencies: tmux, expect, monero-wallet-cli, curl, jq (I think that's everything...)



# Global variables of anything that would need to be changed in this file
NETWORK="stagenet"  # Case-sensitive, Make sure it is all lowercase (testnet, stagenet, mainnet)
if [[ "$NETWORK" == "stagenet" ]];then PORT="38081"; else PORT="28081"; fi
REMOTE_NODE="community.rino.io" # Remote node to send transactions to the network
FUNDING_DELAY="1" # Time inbetween funding wallets ( If this value is too low your funding wallet could have issues with the 20 minute lock)
FUNDING_AMOUNT=".01" # The amount to send to each wallet created
TMUX_WINDOW_DELAY="10" # The delay inbetween launching a new wallet
END_COLLECTION_EPOCH_DATE="1656637261"   # Must be in epoch time (July 1st) The time when collection should stop





#############################################################################
#            You shouldn't need to edit anything below this line            #
#############################################################################
export RUN_SH_NETWORK=${NETWORK}
export END_COLLECTION_EPOCH_DATE=${END_COLLECTION_EPOCH_DATE}
ulimit -n 10240
BLOCKCHAIN_HEIGHT=$(curl -H 'Content-Type: application/json' -X GET "https://community.rino.io/explorer/$NETWORK/api/transactions?page=1&limit=1" -s | jq '.data.blocks[].height' -r)

# Ask the user for a number of wallets to make
read -p "How many wallets would you like (ex. 10)? " numwallets
cd "./Wallets" || exit
# Create the directories which will store 2 wallets each
for i in `seq $(($numwallets / 2))`; do mkdir $i; done
cd - || exit







# Generate the two scripts that will make wallets 1 and 2 respectively
cat > ./Wallets/MakeWallet.exp <<EOL
#!/usr/bin/expect -f
if {[llength \$argv] != 1} {
  puts stderr "Usage: Pass a wallet name!"
  exit 1
}
set name [lindex \$argv 0];   # wallet name
set timeout -1
spawn monero-wallet-cli --$NETWORK --generate-new-wallet \$name --create-address-file --password "" --log-file /dev/null --trusted-daemon
match_max 10000
expect "language of your choice"
send -- "1\r"

expect "Do you want to do it now? (Y/Yes/N/No):*"
send -- "N\r"

expect "wallet*]:*"
send -- "set ask-password 0\r"
expect "*Wallet password:*"
send -- "\r"

expect "wallet*]:*"
send -- "set inactivity-lock-timeout 0\r"
expect "*Wallet password:*"
send -- "\r"

expect "wallet*]:*"
send -- "set store-tx-info 1\r"
expect "Wallet password:*"
send -- "\r"

expect "wallet*]:*"
send -- "set refresh-from-block-height $BLOCKCHAIN_HEIGHT\r"
expect "Wallet password:*"
send -- "\r"

expect "wallet*]:*"
send -- "exit\r"
expect eof
EOL

chmod 777 ./Wallets/MakeWallet.exp

# Make 2 wallets per folder
while read dir
do
	cd "$dir" || exit
	#  Run the scripts to make the two wallets
	../MakeWallet.exp "Wallet1"
	../MakeWallet.exp "Wallet2"
	cd - || exit
done < <(find ./Wallets -mindepth 1 -type d | sort -u)








#  Refresh the funding wallet before use
cat > ./$NETWORK-FundWallet.exp <<EOL
#!/usr/bin/expect -f
set timeout -1
spawn monero-wallet-cli --$NETWORK --wallet ./Funding_Wallets/${NETWORK^}-Funding --daemon-address $NETWORK.$REMOTE_NODE:$PORT --log-file /dev/null --trusted-daemon
match_max 10000
expect "Wallet password: "
send -- "\r"
expect "wallet*]:*"
send -- "set refresh-from-block-height 1038000\r"
expect "Wallet password:*"
send -- "\r"
expect "wallet*]:*"
send -- "rescan_bc soft\r"
expect "wallet*]:"
send -- "exit\r"
expect eof
EOL
#  Run the script
chmod 777 ./$NETWORK-FundWallet.exp && ./$NETWORK-FundWallet.exp









# Fund the wallets (This part is slow but no real way around it)
while read walletFile; do
  walletAddr=$(cat "$walletFile") #  Get the wallet addr from the txt file
  # Make a new expect script substituting the addr to fund the wallet
  cat > ./${NETWORK}-FundWallet.exp <<EOL
#!/usr/bin/expect -f
if {[llength \$argv] != 1} {
  puts stderr "Usage: Pass a wallet address!"
  exit 1
}
set timeout -1
set sendAddr [lindex \$argv 0];   # wallet addr to send to
spawn monero-wallet-cli --$NETWORK --wallet $(pwd)/Funding_Wallets/${NETWORK^}-Funding --daemon-address $NETWORK.$REMOTE_NODE:$PORT --log-file /dev/null --trusted-daemon
match_max 10000
expect "Wallet password: "
send -- "\r"

expect "wallet*]:*"
send -- "transfer \$sendAddr $FUNDING_AMOUNT\r"

expect {

        "Transaction successfully submitted*wallet*]:*" {send "exit\r"}

        "Error: *\[wallet*" {sleep 10;send "transfer \$sendAddr $FUNDING_AMOUNT\r";exp_continue}

        "(out of sync)]: *" {send "refresh\r";exp_continue}

        "(Y/Yes/N/No): *"  {send "y\r";exp_continue}

	timeout {send "transfer \$sendAddr $FUNDING_AMOUNT\r";exp_continue}

}
expect eof
EOL
  #  Run the script
  chmod 777 ./$NETWORK-FundWallet.exp && ./$NETWORK-FundWallet.exp "$walletAddr"
  echo -e "\033[34mWallet $walletFile Funded!" && date && echo -e 'Sleeping for ' $FUNDING_DELAY ' seconds\033[0m'
  sleep $FUNDING_DELAY
  echo ""
done < <(find ./Wallets/ -type f -name "*.txt" | sort -u)
echo ""








# Kill any previous sessions
tmux kill-session -t run-sh &> /dev/null
sleep 1
# Start a tmux server
tmux new-session -d -s run-sh
# Reduce RAM usage
tmux set-option -g history-limit 50

# Start Transfers
while read dir ;do  # Loop each directory
	cd "$dir" || exit
	while read walletAddrFile; do  # Loop each .txt wallet addr file
		#  Gets the name of the current wallet file
		walletName=$(echo $walletAddrFile | cut -f 2 -d "." | cut -f 2 -d "/")
		#  Since we want to transfer to the other wallet we need to switch the numbers
		#  Wallet1 transfers to Wallet2 and Wallet2 transfers to Wallet1
		if [ "${walletName: -1}" -eq "2" ];then  # check if the last number of the wallet is a 2
			recvWalletFile="${walletAddrFile//[2]/1}"  # Swap it with a 1
		else  # The last num is a 1 -> swap it to a 2
			recvWalletFile="${walletAddrFile//[1]/2}"
		fi
		walletAddr=$(cat "$recvWalletFile")

    # Write an expect script substituting the wallet name and addr
    cat > ./$walletName-spend.exp <<EOL
#!/usr/bin/expect -f
if {[llength \$argv] != 2} {
  puts stderr "Usage: Pass an amount and priority as arguments!"
  exit 1
}
set timeout 10800
set amount [lindex \$argv 0];     # 0.0001 -> .000000000001
set priority [lindex \$argv 1];   # 1 -> 4
spawn monero-wallet-cli --$NETWORK --wallet ./${walletName} --daemon-address $NETWORK.$REMOTE_NODE:$PORT --log-file /dev/null --trusted-daemon
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

        "Error: *\[wallet*" {sleep 25;send "transfer $walletAddr \$amount\r";exp_continue}

        "(out of sync)]: *" {send "refresh\r";exp_continue}

        "(Y/Yes/N/No): *"  {send "y\r";exp_continue}

	timeout {send "transfer $walletAddr \$amount\r";exp_continue}

}
expect eof
EOL
		chmod 777 ./$walletName-spend.exp
    #  https://unix.stackexchange.com/questions/515935/tmux-how-to-specify-session-in-new-window
    echo -e '\033[34mSpawned new tmux window: \033[0m' "${walletAddr}"
    tmux new-window -t run-sh: "python3 ../../spawn.py ${walletName}"
    #  A delay of opening a new tab to not overload the server. Most wallets will have to scan the network for a while before transacting
    echo -e '\033[34mSleeping for: \033[0m\t\t ' $TMUX_WINDOW_DELAY ' seconds'
		sleep $TMUX_WINDOW_DELAY
	done < <(find ./ -type f -name "*.txt" | sort -u)
	cd - || exit # Reset the directory
done < <(find ./Wallets -mindepth 1 -type d | sort -u) 
