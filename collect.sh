#!/bin/bash

# Requirements: jq, parallel and expect
# Before running this script first compile and run
#               "./monerod --testnet"       https://github.com/monero-project/monero#compiling-monero-from-source
# Before running this script first compile xmr2csv from https://github.com/moneroexamples/transactions-export
# Usage: ./collect.sh


# Global variables
REMOTE_NODE="127.0.0.1"   # testnet.community.rino.io
NETWORK="testnet"  # Case-sensitive (make all lowercase) (Options: "testnet" or "stagenet")

#############################################################################
#            You shouldn't need to edit anything below this line            #
#############################################################################

if [[ "$NETWORK" == "stagenet" ]];then REMOTE_RPC_PORT="38081"; else REMOTE_RPC_PORT="28081"; fi
if [[ "$NETWORK" == "stagenet" ]];then LOCAL_RPC_PORT="38088"; else LOCAL_RPC_PORT="28088"; fi

parent_dir=$(pwd)

#  Check to see if the xmr2csv_commands file exists and if it does does ask the user to delete it before preceding
if [ -f "${parent_dir}/xmr2csv_commands.txt" ];then
  while true; do
    read -p "xmr2csv_commands.txt exists from a previous run. Would you like to proceed with the deletion? " answer
    case $answer in
      [Yy]* ) rm -f "${parent_dir}"/xmr2csv_commands.txt; break;;
      [Nn]* ) break;;
      * ) echo "Please answer yes or no.";;
    esac
  done
fi

while read dir; do  # Read in all directories that contain a .txt file in the current directory
  cd "$dir" || exit
  echo "$dir"
  working_dir=$(pwd)
  while read walletAddrFile; do # Loop each .txt wallet addr file
    #  Gets the name of the current wallet file
    walletName=$(echo $walletAddrFile | cut -f 2 -d "." | cut -f 2 -d "/")
    #  Gets the address of the current wallet
    walletAddr=$(cat "$walletAddrFile")

    # Create script to export the current wallet transactions using the monero-wallet-cli
    cat >./Export_Wallet.exp <<EOL
#!/usr/bin/expect -f
set timeout -1
spawn monero-wallet-cli --$NETWORK --wallet ./$walletName --daemon-address $REMOTE_NODE:$REMOTE_RPC_PORT --log-file /dev/null --trusted-daemon
match_max 100000
expect "Wallet password: "
send -- "\r"

expect "wallet*]:*"
send -- "export_transfers out output=cli_export_$walletAddr.csv\r"

expect "wallet*]:*"
send -- "exit\r"

expect eof
EOL

    #  Make the script executable and run it
    chmod 777 ./Export_Wallet.exp && ./Export_Wallet.exp
    date

    #  Check if there are any transactions ( if len() = 1 then its just the csv header)
    if [[ $(wc -l < cli_export_"$walletAddr".csv) -gt 1 ]];then
      #  Get the minimum block height by sorting the blocks in exported transaction file from the cli
      min_block_height="$(cut -f 1 -d ',' < cli_export_"$walletAddr".csv | awk '{print $1}' | sort -u | head -n 1)"

      #  Kill any monero-wallet-rpc processes that are still lingering
      echo -en '\033[34mKilling monero-wallet-rpc processes... \033[0m';echo;
      procs=$(ps aux | grep monero-wallet-rpc | grep -v grep | awk '{ print $2 }')
      if [ "$procs" != "" ];then
        echo "$procs" | xargs -I{} kill -9 {}
      fi

      #  Start a new monero-wallet-rpc process for the current wallet
      echo -en '\033[34mStarting a new monero-wallet-rpc process... \033[0m';echo;
      monero-wallet-rpc --rpc-bind-port $LOCAL_RPC_PORT --wallet-file "$walletName" --password '' --$NETWORK --disable-rpc-login &

      echo -en '\033[34mWaiting... \033[0m';echo;
      sleep 8 # Give the RPC server time to spin up

      #  Query the monero-wallet-rpc process and collect the view key
      view_key=$(curl http://127.0.0.1:$LOCAL_RPC_PORT/json_rpc -s -d '{"jsonrpc":"2.0","id":"0","method":"query_key","params":{"key_type":"view_key"}}' -H 'Content-Type: application/json' | jq '.result.key' -r)

      # Wait until the rpc server is giving a response
      while [ "$view_key" == "" ]; do
        echo -en '\033[31mMonero-Wallet-RPC server failed to start, retrying... \033[0m';echo;
        #  Kill any monero-wallet-rpc processes that are still lingering
        procs=$(ps aux | grep monero-wallet-rpc | grep -v grep | awk '{ print $2 }')
        if [ "$procs" != "" ];then
          echo "$procs" | xargs -I{} kill -9 {}
        fi
        monero-wallet-rpc --rpc-bind-port $LOCAL_RPC_PORT --wallet-file "$walletName" --password '' --$NETWORK --disable-rpc-login &
        sleep 30 # Give the RPC server time to spin up
        #  Connect to the RPC server and get the view & spend key
        view_key=$(curl http://127.0.0.1:$LOCAL_RPC_PORT/json_rpc -s -d '{"jsonrpc":"2.0","id":"0","method":"query_key","params":{"key_type":"view_key"}}' -H 'Content-Type: application/json' | jq '.result.key' -r)
      done

      #  Query the monero-wallet-rpc process and collect the spend key
      spend_key=$(curl http://127.0.0.1:$LOCAL_RPC_PORT/json_rpc -s -d '{"jsonrpc":"2.0","id":"0","method":"query_key","params":{"key_type":"spend_key"}}' -H 'Content-Type: application/json' | jq '.result.key' -r)

      #  Kill the wallet rpc wallet
      procs=$(ps aux | grep monero-wallet-rpc | grep -v grep | awk '{ print $2 }')
      if [ "$procs" != "" ];then
        echo "$procs" | xargs -I{} kill -9 {}
      fi
      echo
      #  Save the epoch time of when the scan started since Decoy_Output_Ring_Member_Frequency will depend on it
      date +%s > xmr2csv_start_time_"$walletAddr".csv
      #  Make xmr2csv command using all the collected values and save the command to a text file to be run in parallel later on
      echo xmr2csv --address "$walletAddr" --viewkey "$view_key" --spendkey "$spend_key" --"$NETWORK" --start-height "$min_block_height" --ring-members --out-csv-file "$working_dir"/xmr_report_"$walletAddr".csv --out-csv-file2 "$working_dir"/xmr_report_ring_members_"$walletAddr".csv --out-csv-file3 "$working_dir"/xmr_report_ring_members_freq_"$walletAddr".csv --out-csv-file4 "$working_dir"/xmr_report_key_images_outputs_"$walletAddr".csv --out-csv-file5 "$working_dir"/xmr_report_outgoing_txs_"$walletAddr".csv >> "$parent_dir"/xmr2csv_commands.txt
      echo -en "\033[34mXMR2CSV command constructed and saved to ${parent_dir}/xmr2csv_commands.txt\033[0m";echo;
    fi # End error check

  done < <(find ./ -type f -name "*.txt" | sort -u) #  Find text files in each wallet directory
  cd - || exit
#  Find wallet directories that contain a .txt file also remove any python venv libraries
done < <(find . -mindepth 2 -type f -name '*.txt' | sed -r 's|/[^/]+$||' | sort -u | grep -v "venv")

echo;echo;echo;
echo -en '\033[34mStarting multiprocessing of xmr2csv exports... \033[0m';echo;
num_processors=$(nproc --all)
cat "$parent_dir"/xmr2csv_commands.txt | parallel --bar --jobs "$num_processors" {}




