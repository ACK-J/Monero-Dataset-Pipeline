#!/bin/bash

# Requirements: jq
# Before running this script first compile and run 
#               "./monerod --testnet"       https://github.com/monero-project/monero#compiling-monero-from-source
# Before running this script first compile xmr2csv from https://github.com/moneroexamples/transactions-export
# Usage: ./collect.sh

while read dir; do 
    cd "$dir" || exit
    echo "$dir"
    while read walletAddrFile; do  # Loop each .txt wallet addr file
        #  Gets the name of the current wallet file
	      walletName=$(echo $walletAddrFile | cut -f 2 -d "." | cut -f 2 -d "/")
	      #  Gets the address of the curent wallet
	      walletAddr=$(cat "$walletAddrFile")
	    
	    
cat > ./Export_Wallet.exp <<EOL 
#!/usr/bin/expect -f
set timeout 300
spawn monero-wallet-cli --testnet --wallet ./$walletName --daemon-address testnet.melo.tools:28081 --log-file /dev/null --trusted-daemon
match_max 100000
expect "Wallet password: "
send -- "\r"

expect "wallet*]:*"
send -- "export_transfers all output=cli_export_$walletAddr.csv\r"

expect "wallet*]:*"
send -- "exit\r"

expect eof
EOL

          chmod 777 ./Export_Wallet.exp && ./Export_Wallet.exp
          date
                
          min_block_height=$(cat cli_export_"$walletAddr".csv | cut -f 1 -d ',' | awk '{print $1}' | sort -u | head -n 1)
          
          echo "Killing monero-wallet-rpc processes..."
          ps aux | grep monero-wallet-rpc | awk '{ print $2 }' | head -n +2 | xargs kill -9
          
          echo "Starting a new monero-wallet-rpc process..."
          #  Start a RPC server for the current wallet
          monero-wallet-rpc --rpc-bind-port 28088 --wallet-file "$walletName" --password '' --testnet --disable-rpc-login & 
          
          echo "Waiting..."
          sleep 30  # Give the RPC server time to spin up
          
          view_key=$(curl http://127.0.0.1:28088/json_rpc -s -d '{"jsonrpc":"2.0","id":"0","method":"query_key","params":{"key_type":"view_key"}}' -H 'Content-Type: application/json' | jq '.result.key' -r)
          
          # Wait until the rpc server is giving a response
          while [ "$view_key" == "" ]; do
             echo "Monero-Wallet-RPC server failed to start, retrying..."
             ps aux | grep monero-wallet-rpc | awk '{ print $2 }' | head -n +2 | xargs kill -9
             monero-wallet-rpc --rpc-bind-port 28088 --wallet-file "$walletName" --password '' --testnet --disable-rpc-login & 
             sleep 15  # Give the RPC server time to spin up
             #  Connect to the RPC server and get the view & spend key
             view_key=$(curl http://127.0.0.1:28088/json_rpc -s -d '{"jsonrpc":"2.0","id":"0","method":"query_key","params":{"key_type":"view_key"}}' -H 'Content-Type: application/json' | jq '.result.key' -r)
          done	
          
          spend_key=$(curl http://127.0.0.1:28088/json_rpc -s -d '{"jsonrpc":"2.0","id":"0","method":"query_key","params":{"key_type":"spend_key"}}' -H 'Content-Type: application/json' | jq '.result.key' -r)

         
          # Kill the wallet rpc wallet
          ps aux | grep monero-wallet-rpc | awk '{ print $2 }' | head -n +2 | xargs kill -9
          echo
          xmr2csv --address "$walletAddr" --viewkey "$view_key" --spendkey "$spend_key"  --testnet --start-height "$min_block_height" --ring-members --out-csv-file ./xmr_report_"$walletAddr".csv --out-csv-file2 xmr_report_ring_members_"$walletAddr".csv --out-csv-file3 xmr_report_ring_members_freq_"$walletAddr".csv --out-csv-file4 xmr_report_key_images_outputs_"$walletAddr".csv --out-csv-file5 xmr_report_outgoing_txs_"$walletAddr".csv
          

    done < <(find ./ -type f -name "*.txt" | sort -u)
    cd - || exit
    #python3 create_dataset.py
done < <(find ./Wallets -mindepth 1 -type d | sort -u)
