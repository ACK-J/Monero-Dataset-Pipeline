#!/bin/bash

# Requirements: jq
# Before running this script first compile and run 
#               "./monerod --testnet --prune-blockchain"       https://github.com/monero-project/monero#compiling-monero-from-source
# Before running this script first compile xmr2csv from https://github.com/moneroexamples/transactions-export
# Usage: ./collect.sh

while read dir; do 
    cd "$dir"
    echo "$dir"
    while read walletAddrFile; do  # Loop each .txt wallet addr file
            #  Gets the name of the current wallet file
	    walletName=`echo $walletAddrFile | cut -f 2 -d "." | cut -f 2 -d "/"`
	    #  Gets the address of the curent wallet
	    walletAddr=`cat "$walletAddrFile"`
	    
	    echo "Killing monero-Wallet-RPC processes..."
	    killall monero-wallet-rpc
	    
	    echo "Starting a new monero-wallet-rpc process..."
	    #  Start a RPC server for the current wallet
            monero-wallet-rpc --rpc-bind-port 28088 --wallet-file $walletName --password '' --testnet --disable-rpc-login >/dev/null 2>&1 & 
            
            echo "Waiting..."
            sleep 60  # Give the RPC server time to spin up
            
            view_key=`curl http://127.0.0.1:28088/json_rpc -s -d '{"jsonrpc":"2.0","id":"0","method":"query_key","params":{"key_type":"view_key"}}' -H 'Content-Type: application/json' | jq '.result.key' -r`
            
            # Wait until the rpc server is giving a response
            while [ "$view_key" == "" ]; do
               echo "Monero-Wallet-RPC server failed to start, retrying..."
               killall monero-wallet-rpc
               monero-wallet-rpc --rpc-bind-port 28088 --wallet-file $walletName --password '' --testnet --disable-rpc-login >/dev/null 2>&1 & 
            	sleep 60  # Give the RPC server time to spin up
            	#  Connect to the RPC server and get the view & spend key
            	view_key=`curl http://127.0.0.1:28088/json_rpc -s -d '{"jsonrpc":"2.0","id":"0","method":"query_key","params":{"key_type":"view_key"}}' -H 'Content-Type: application/json' | jq '.result.key' -r`
            done	
            
            spend_key=`curl http://127.0.0.1:28088/json_rpc -s -d '{"jsonrpc":"2.0","id":"0","method":"query_key","params":{"key_type":"spend_key"}}' -H 'Content-Type: application/json' | jq '.result.key' -r`
            
            # Get all in and out transactions
            # curl http://127.0.0.1:28088/json_rpc -d '{"jsonrpc":"2.0","id":"0","method":"get_transfers","params":{"in":true,"out":true}}' -H 'Content-Type: application/json'

	    starting_block_out=`curl http://127.0.0.1:28088/json_rpc -d '{"jsonrpc":"2.0","id":"0","method":"get_transfers","params":{"in":true,"out":true}}' -H 'Content-Type: application/json' -s | jq '.result.out[0].height'`
	    starting_block_in=`curl http://127.0.0.1:28088/json_rpc -d '{"jsonrpc":"2.0","id":"0","method":"get_transfers","params":{"in":true,"out":true}}' -H 'Content-Type: application/json' -s | jq '.result.in[0].height'`
	    
	    # Kill the wallet rpc wallet
            killall monero-wallet-rpc
            
            if [ "null" == "$starting_block_out" ] && [ "null" == "$starting_block_in" ]; then 
            		# Both wallets return null for block height
            		Wallet $(pwd) $walletName is Empty!; 
            else # At least one is not null
            		# if neither are null and out < in
            		if  [ ! "null" == "$starting_block_out" ] && [ ! "null" == "$starting_block_in" ] && [ $starting_block_out -le $starting_block_in ]; then
            				xmr2csv --address $walletAddr --viewkey $view_key --spendkey $spend_key  --testnet --start-height $starting_block_out --ring-members --out-csv-file ./xmr_report_"$walletAddr".csv --out-csv-file2 xmr_report_ring_members_"$walletAddr".csv --out-csv-file3 xmr_report_ring_members_freq_"$walletAddr".csv --out-csv-file4 xmr_report_key_images_outputs_"$walletAddr".csv
            		# if neither are null and in < out	
            		elif [ ! "null" == "$starting_block_out" ] && [ ! "null" == "$starting_block_in" ] && [ $starting_block_in -le $starting_block_out ]; then
            				xmr2csv --address $walletAddr --viewkey $view_key --spendkey $spend_key --testnet --start-height $starting_block_in --ring-members --out-csv-file ./xmr_report_"$walletAddr".csv --out-csv-file2 xmr_report_ring_members_"$walletAddr".csv --out-csv-file3 xmr_report_ring_members_freq_"$walletAddr".csv --out-csv-file4 xmr_report_key_images_outputs_"$walletAddr".csv
            		# one of them is null 
            		# Check if out is not null
            		elif [ ! "null" == "$starting_block_out" ]; then
            				xmr2csv --address $walletAddr --viewkey $view_key --spendkey $spend_key --testnet --start-height $starting_block_out --ring-members --out-csv-file ./xmr_report_"$walletAddr".csv --out-csv-file2 xmr_report_ring_members_"$walletAddr".csv --out-csv-file3 xmr_report_ring_members_freq_"$walletAddr".csv --out-csv-file4 xmr_report_key_images_outputs_"$walletAddr".csv
            		else # in must not be null
            				xmr2csv --address $walletAddr --viewkey $view_key --spendkey $spend_key --testnet --start-height $starting_block_in --ring-members --out-csv-file ./xmr_report_"$walletAddr".csv --out-csv-file2 xmr_report_ring_members_"$walletAddr".csv --out-csv-file3 xmr_report_ring_members_freq_"$walletAddr".csv --out-csv-file4 xmr_report_key_images_outputs_"$walletAddr".csv
            		fi
            				
            fi
            
cat > ./Export_Wallet.exp <<EOL 
#!/usr/bin/expect -f
set timeout 60 
spawn monero-wallet-cli --testnet --wallet ./$walletName --daemon-address testnet.melo.tools:28081 --log-file /dev/null --trusted-daemon
match_max 100000
expect "*Wallet password: "
send -- "\r"

expect "wallet*]:*"
send -- "export_transfers all output=cli-export-$walletAddr.csv\r"

expect "wallet*]:*"
send -- "exit\r"

expect eof
EOL
chmod 777 ./Export_Wallet.exp && ./Export_Wallet.exp
echo "Wallet $walletAddr Exported!" && date
	    
	done < <(find ./ -type f -name "*.txt" | sort -u)
	cd -
	#python3 process_exported.py
done < <(find ./Wallets -mindepth 1 -type d | sort -u)
