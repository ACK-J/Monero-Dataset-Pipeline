#!/bin/bash

# Requirements: jq
# Before running this script first compile and run ./monerod --testnet --prune-blockchain       https://github.com/monero-project/monero#compiling-monero-from-source
# Before running this script first compile xmr2csv from                                         https://github.com/moneroexamples/transactions-export
# Usage: ./collect.sh <starting block>
s
while read dir; do 
    while read walletAddrFile; do  # Loop each .txt wallet addr file
	    cd "$dir"
            #  Gets the name of the current wallet file
	    walletName=`echo $walletAddrFile | cut -f 2 -d "." | cut -f 2 -d "/"`
	    #  Gets the address of the curent wallet
	    walletAddr=`cat "$walletAddrFile"`
	    #  Start a RPC server for the current wallet
            nohup monero-wallet-rpc --rpc-bind-port 28088 --wallet-file $walletName --password '' --testnet --disable-rpc-login &
            #  Connect to the RPC server and get the view & spend key
            view_key=`curl http://127.0.0.1:28088/json_rpc -s -d '{"jsonrpc":"2.0","id":"0","method":"query_key","params":{"key_type":"view_key"}}' -H 'Content-Type: application/json' | jq '.result.key' -r`
            spend_key=`curl http://127.0.0.1:28088/json_rpc -s -d '{"jsonrpc":"2.0","id":"0","method":"query_key","params":{"key_type":"spend_key"}}' -H 'Content-Type: application/json' | jq '.result.key' -r`
            # Get all in and out transactions
            # curl http://127.0.0.1:28088/json_rpc -d '{"jsonrpc":"2.0","id":"0","method":"get_transfers","params":{"in":true,"out":true}}' -H 'Content-Type: application/json'
            # Starting block 1880000
            ./xmr2csv --address $walletAddr --viewkey $view_key --spendkey $spend_key --out-csv-file ./transactions.csv --testnet --start-height $1 --ring-members
            # Kill the rpc wallet
            killall monero-wallet-rpc
	    cd -
	done < <(find ./ -type f -name "*.txt" | sort -u)
done < <(find ./Wallets -mindepth 1 -type d | sort -u)
