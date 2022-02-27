#!/bin/bash

# Requirements: jq and expect
# Before running this script first compile and run
#               "./monerod --testnet"       https://github.com/monero-project/monero#compiling-monero-from-source
# Before running this script first compile xmr2csv from https://github.com/moneroexamples/transactions-export
# Usage: ./collect.sh

while read dir; do  # Read in all directories in ./Wallets
  cd "$dir" || exit
  echo "$dir"
  while read walletAddrFile; do # Loop each .txt wallet addr file
    #  Gets the name of the current wallet file
    walletName=$(echo $walletAddrFile | cut -f 2 -d "." | cut -f 2 -d "/")
    #  Gets the address of the current wallet
    walletAddr=$(cat "$walletAddrFile")

    # Create script to export the current wallet transactions using the monero-wallet-cli
    cat >./Export_Wallet.exp <<EOL
#!/usr/bin/expect -f
set timeout -1
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

    #  Make the script executable and run it
    chmod 777 ./Export_Wallet.exp && ./Export_Wallet.exp
    date

    #  Check if there are any transactions
    if [[ "$(wc -l < cli_export_"$walletAddr".csv)" -ne "1" ]];then
      #  Get the minimum block height by sorting the blocks in exported transaction file from the cli
      min_block_height="$(cut -f 1 -d ',' < cli_export_"$walletAddr".csv | awk '{print $1}' | sort -u | head -n 1)"

      #  Kill any monero-wallet-rpc processes that are still lingering
      echo "Killing monero-wallet-rpc processes..."
      ps aux | grep monero-wallet-rpc | awk '{ print $2 }' | head -n +2 | xargs kill -9

      #  Start a new monero-wallet-rpc process for the current wallet
      echo "Starting a new monero-wallet-rpc process..."
      monero-wallet-rpc --rpc-bind-port 28088 --wallet-file "$walletName" --password '' --testnet --disable-rpc-login &

      echo "Waiting..."
      sleep 30 # Give the RPC server time to spin up

      #  Query the monero-wallet-rpc process and collect the view key
      view_key=$(curl http://127.0.0.1:28088/json_rpc -s -d '{"jsonrpc":"2.0","id":"0","method":"query_key","params":{"key_type":"view_key"}}' -H 'Content-Type: application/json' | jq '.result.key' -r)

      # Wait until the rpc server is giving a response
      while [ "$view_key" == "" ]; do
        echo "Monero-Wallet-RPC server failed to start, retrying..."
        #  Kill any monero-wallet-rpc processes that are still lingering
        ps aux | grep monero-wallet-rpc | awk '{ print $2 }' | head -n +2 | xargs kill -9
        monero-wallet-rpc --rpc-bind-port 28088 --wallet-file "$walletName" --password '' --testnet --disable-rpc-login &
        sleep 45 # Give the RPC server time to spin up
        #  Connect to the RPC server and get the view & spend key
        view_key=$(curl http://127.0.0.1:28088/json_rpc -s -d '{"jsonrpc":"2.0","id":"0","method":"query_key","params":{"key_type":"view_key"}}' -H 'Content-Type: application/json' | jq '.result.key' -r)
      done

      #  Query the monero-wallet-rpc process and collect the spend key
      spend_key=$(curl http://127.0.0.1:28088/json_rpc -s -d '{"jsonrpc":"2.0","id":"0","method":"query_key","params":{"key_type":"spend_key"}}' -H 'Content-Type: application/json' | jq '.result.key' -r)

      #  Kill the wallet rpc wallet
      ps aux | grep monero-wallet-rpc | awk '{ print $2 }' | head -n +2 | xargs kill -9
      echo
      #  Save the epoch time of when the scan started since Decoy_Output_Ring_Member_Frequency will depend on it
      date +%s > xmr2csv_start_time_"$walletAddr".csv
      #  Run xmr2csv using all the collected values
      xmr2csv --address "$walletAddr" --viewkey "$view_key" --spendkey "$spend_key" --testnet --start-height "$min_block_height" --ring-members --out-csv-file ./xmr_report_"$walletAddr".csv --out-csv-file2 xmr_report_ring_members_"$walletAddr".csv --out-csv-file3 xmr_report_ring_members_freq_"$walletAddr".csv --out-csv-file4 xmr_report_key_images_outputs_"$walletAddr".csv --out-csv-file5 xmr_report_outgoing_txs_"$walletAddr".csv
    fi # End error check

  done < <(find ./ -type f -name "*.txt" | sort -u) #  Find text files in each wallet directory
  cd - || exit
  #python3 create_dataset.py
done < <(find ./Wallets -mindepth 1 -type d | sort -u) #  Find wallet directories
